"""
monvisor/cli/scan.py
Phase 2 — Discovery.

CIDR scanning via python-nmap, port→service fingerprinting, secondary HTTP
probing for confirmation/version, persistence to SQLite, and report dispatch.
"""

from __future__ import annotations

import shutil
from typing import Optional

import httpx
from rich.console import Console

from monvisor import config
from monvisor.db import queries
from monvisor.db.schema import init_db

console = Console()

# nmap arguments — connect scan (-sT) so root is not required, version
# detection (-sV), open ports only, fast timing, bounded per-host timeout.
NMAP_ARGS = f"-sT -sV --open -T4 --host-timeout 90s -p {config.ALL_PORTS}"

# HTTP probe definitions per fingerprinted service type.
#   path            — endpoint to GET
#   expect          — substring expected in body to confirm the type
#   version_metric  — Prometheus *_build_info metric to pull a version from
HTTP_PROBES = {
    "prometheus":       {"path": "/-/healthy",   "expect": "Prometheus", "version_metric": "prometheus_build_info"},
    "alertmanager":     {"path": "/-/healthy",   "expect": "Alertmanager", "version_metric": "alertmanager_build_info"},
    "grafana":          {"path": "/api/health",  "expect": "database",   "version_metric": None},
    "node_exporter":    {"path": "/metrics",     "expect": "node_",      "version_metric": "node_exporter_build_info"},
    "mysqld_exporter":  {"path": "/metrics",     "expect": "mysql",      "version_metric": "mysqld_exporter_build_info"},
    "postgres_exporter":{"path": "/metrics",     "expect": "pg_",        "version_metric": "postgres_exporter_build_info"},
    "redis_exporter":   {"path": "/metrics",     "expect": "redis",      "version_metric": "redis_exporter_build_info"},
    "nginx_exporter":   {"path": "/metrics",     "expect": "nginx",      "version_metric": "nginx_exporter_build_info"},
    "blackbox_exporter":{"path": "/metrics",     "expect": "probe_",     "version_metric": "blackbox_exporter_build_info"},
    "pushgateway":      {"path": "/metrics",     "expect": "push",       "version_metric": "pushgateway_build_info"},
}

# Service types that are HTTP-reachable and worth probing.
_HTTP_TYPES = set(HTTP_PROBES.keys())


def _check_nmap() -> bool:
    """Return True if the nmap binary is on PATH."""
    return shutil.which("nmap") is not None


def _fingerprint(port: int, nmap_service: Optional[str], nmap_product: Optional[str]) -> str:
    """Map a port (with nmap hints as tiebreakers) to a MonVisor service type."""
    st = config.FINGERPRINTS.get(port)
    if st:
        return st
    # Fall back to nmap's own identification when the port is unknown.
    if nmap_product:
        return nmap_product.lower().replace(" ", "_")
    if nmap_service and nmap_service not in ("unknown", "tcpwrapped"):
        return nmap_service
    return "unknown"


def _http_probe(host: str, port: int, service_type: str) -> tuple[str, Optional[str]]:
    """
    Secondary fingerprint via HTTP. Returns (confirmed_type, version|None).
    Tries https then http. Best-effort; never raises.
    """
    probe = HTTP_PROBES.get(service_type)
    if not probe:
        return service_type, None

    for scheme in ("http", "https"):
        base = f"{scheme}://{host}:{port}"
        try:
            with httpx.Client(timeout=4.0, verify=False, follow_redirects=True) as c:
                r = c.get(base + probe["path"])
                if r.status_code >= 400:
                    continue
                body = r.text

                # Confirmation only — leaves type unchanged, just validates.
                # Version: scrape the build_info metric if /metrics is available.
                version = None
                metric = probe.get("version_metric")
                if metric and "/metrics" in probe["path"]:
                    version = _parse_build_info(body, metric)
                elif metric:
                    # Pull /metrics separately for the version.
                    try:
                        rm = c.get(base + "/metrics")
                        if rm.status_code < 400:
                            version = _parse_build_info(rm.text, metric)
                    except httpx.HTTPError:
                        pass
                return service_type, version
        except httpx.HTTPError:
            continue
    return service_type, None


def _parse_build_info(metrics_body: str, metric: str) -> Optional[str]:
    """Extract version="x.y.z" from a Prometheus *_build_info metric line."""
    for line in metrics_body.splitlines():
        if line.startswith(metric) and 'version="' in line:
            try:
                return line.split('version="', 1)[1].split('"', 1)[0]
            except IndexError:
                return None
    return None


def _scan_targets(scanner, target: str) -> dict:
    """Run nmap against any nmap target spec (CIDR, single IP, or space-separated
    list of hosts). Returns a raw_findings dict."""
    scanner.scan(hosts=target, arguments=NMAP_ARGS)
    hosts = []
    for host in scanner.all_hosts():
        if scanner[host].state() != "up":
            continue
        ports = []
        tcp = scanner[host].get("tcp", {})
        for port, pdata in tcp.items():
            if pdata.get("state") != "open":
                continue
            ports.append({
                "port": port,
                "nmap_service": pdata.get("name"),
                "nmap_product": pdata.get("product"),
                "nmap_version": pdata.get("version"),
            })
        if ports:
            hosts.append({"host": host, "ports": ports})
    return {"cidr": target, "hosts": hosts}


# Backwards-compatible alias.
def _scan_cidr(scanner, cidr: str) -> dict:
    return _scan_targets(scanner, cidr)


def _persist_findings(env_id, raw, new_only, existing, counters) -> None:
    """Upsert services from one raw_findings dict. Mutates counters in place."""
    discovery_id = queries.create_discovery(env_id, raw["cidr"], raw)
    for host_entry in raw["hosts"]:
        host = host_entry["host"]
        host_had_service = False
        for p in host_entry["ports"]:
            port = p["port"]
            if new_only and (host, port) in existing:
                continue
            service_type = _fingerprint(port, p.get("nmap_service"), p.get("nmap_product"))
            version = p.get("nmap_version") or None
            if service_type in _HTTP_TYPES:
                service_type, probed_version = _http_probe(host, port, service_type)
                version = probed_version or version
            queries.upsert_service(discovery_id, env_id, host, port, service_type, version)
            counters["services"] += 1
            host_had_service = True
            counters["types"][service_type] = counters["types"].get(service_type, 0) + 1
        if host_had_service:
            counters["hosts"] += 1


def run_scan(environment: str, new_only: bool = False,
             hosts: Optional[list[str]] = None) -> Optional[dict]:
    """
    Scan an environment and persist results.

    If `hosts` is given, scan only those specific hosts (a targeted re-scan,
    e.g. after installing an exporter) instead of sweeping every CIDR.
    Returns a summary dict, or None on a hard failure.
    """
    init_db()

    env = queries.get_environment(environment)
    if not env:
        console.print(f"[red]Environment '{environment}' not found.[/red]")
        console.print(f"  Create it: monvisor env add {environment} <cidr>")
        return None

    targeted = bool(hosts)
    cidrs = queries.get_cidrs(env["id"])
    if not targeted and not cidrs:
        console.print(f"[red]Environment '{environment}' has no CIDRs.[/red]")
        return None

    if not _check_nmap():
        console.print("[red]nmap binary not found on PATH.[/red]")
        console.print("  Install it: sudo dnf install nmap   (Fedora)")
        return None

    import nmap
    scanner = nmap.PortScanner()

    existing = set()
    if new_only:
        for s in queries.get_services(env["id"]):
            existing.add((s["host"], s["port"]))

    counters = {"services": 0, "hosts": 0, "types": {}}

    if targeted:
        target = " ".join(hosts)
        console.print(f"  Re-scanning [bold]{len(hosts)} target(s)[/bold]: {', '.join(hosts)} ...")
        try:
            raw = _scan_targets(scanner, target)
            _persist_findings(env["id"], raw, new_only, existing, counters)
        except nmap.PortScannerError as e:
            console.print(f"  [red]nmap error: {e}[/red]")
            return None
    else:
        for c in cidrs:
            cidr = c["cidr"]
            console.print(f"  Scanning [bold]{cidr}[/bold] ...")
            try:
                raw = _scan_targets(scanner, cidr)
            except nmap.PortScannerError as e:
                console.print(f"  [red]nmap error on {cidr}: {e}[/red]")
                continue
            _persist_findings(env["id"], raw, new_only, existing, counters)

    return {
        "environment": environment,
        "env_id": env["id"],
        "hosts": counters["hosts"],
        "services": counters["services"],
        "types": counters["types"],
        "new_only": new_only,
        "targeted": targeted,
    }
