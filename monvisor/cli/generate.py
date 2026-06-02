# MonVisor — AI-assisted monitoring configuration for Prometheus/Grafana.
# Copyright (C) 2026 James Sparenberg
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
monvisor/cli/generate.py
Phase 3 — config generation.

Deterministically builds prometheus.yml scrape_configs from monitored services,
then uses RAG + Ollama to draft alerting rules per service type. Validates with
promtool when available. Persists to SQLite and ~/.monvisor/configs/.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from rich.console import Console

from monvisor import config
from monvisor.db import queries
from monvisor.db.schema import init_db

console = Console()

# Service types that expose a Prometheus /metrics endpoint and should become
# scrape targets. Plain services (mysql, redis) are scraped via their exporter,
# so only exporter/native-metrics types are included here.
_SCRAPEABLE = {
    "prometheus", "alertmanager", "pushgateway", "node_exporter",
    "mysqld_exporter", "nginx_exporter", "elasticsearch_exporter",
    "blackbox_exporter", "snmp_exporter", "redis_exporter",
    "postgres_exporter", "mongodb_exporter", "kafka_exporter",
    "rabbitmq_exporter", "haproxy_exporter", "statsd_exporter", "grafana",
}


def _build_scrape_configs(scrape_services: list[dict],
                          blackbox_services: list[dict] | None = None,
                          blackbox_addr: str = "127.0.0.1:9115") -> dict:
    """Group monitored services into Prometheus scrape_configs.

    Direct exporter targets become one job per service type. 'Not installable'
    services (monitor_mode='blackbox') become blackbox_exporter probe jobs.
    """
    by_type: dict[str, list[str]] = defaultdict(list)
    for s in scrape_services:
        st = s["service_type"]
        if st in _SCRAPEABLE:
            by_type[st].append(f"{s['host']}:{s['port']}")

    jobs = []
    for st, targets in sorted(by_type.items()):
        jobs.append({
            "job_name": st,
            "static_configs": [{"targets": sorted(targets)}],
        })

    jobs.extend(_build_blackbox_jobs(blackbox_services or [], blackbox_addr))

    return {
        "global": {"scrape_interval": "15s", "evaluation_interval": "15s"},
        "rule_files": ["rules.yml"],
        "alerting": {
            "alertmanagers": [
                {"static_configs": [{"targets": ["localhost:9093"]}]}
            ]
        },
        "scrape_configs": jobs,
    }


def _bb_module(port: int) -> str:
    """Pick a blackbox module by port. Modules must exist in blackbox.yml."""
    if port in (443, 8443):
        return "https_2xx"
    if port in (80, 8080):
        return "http_2xx"
    return "tcp_connect"


def _bb_target(host: str, port: int, module: str) -> str:
    if module == "http_2xx":
        return f"http://{host}:{port}"
    if module == "https_2xx":
        return f"https://{host}:{port}"
    return f"{host}:{port}"


def _build_blackbox_jobs(services: list[dict], blackbox_addr: str) -> list[dict]:
    """One scrape job per blackbox module, relabelled to probe via the
    blackbox_exporter at blackbox_addr."""
    by_module: dict[str, list[str]] = defaultdict(list)
    for s in services:
        module = _bb_module(s["port"])
        by_module[module].append(_bb_target(s["host"], s["port"], module))

    jobs = []
    for module, targets in sorted(by_module.items()):
        jobs.append({
            "job_name": f"blackbox_{module}",
            "metrics_path": "/probe",
            "params": {"module": [module]},
            "static_configs": [{"targets": sorted(targets)}],
            "relabel_configs": [
                {"source_labels": ["__address__"], "target_label": "__param_target"},
                {"source_labels": ["__param_target"], "target_label": "instance"},
                {"target_label": "__address__", "replacement": blackbox_addr},
            ],
        })
    return jobs


def _resolve_blackbox_addr(monitored: list[dict]) -> tuple[str, bool]:
    """Find a blackbox_exporter address: discovered instance, then setting,
    then default. Returns (addr, found_real)."""
    for s in monitored:
        if s["service_type"] == "blackbox_exporter":
            return f"{s['host']}:{s['port']}", True
    setting = queries.get_setting("blackbox-url")
    if setting:
        return setting.replace("http://", "").replace("https://", "").rstrip("/"), True
    return "127.0.0.1:9115", False


def _generate_rules(service_types: list[str]) -> Optional[str]:
    """Use RAG + Ollama to draft alerting rules for the given service types."""
    try:
        import ollama
        from monvisor.rag.query import build_context
    except Exception as e:
        console.print(f"  [yellow]\u26a0[/yellow]  Rules generation unavailable ({e})")
        return None

    context = build_context(
        "prometheus alerting rules for " + ", ".join(service_types),
        n_pairs=4, n_exemplars=2,
    )
    prompt = (
        "You are a Prometheus monitoring expert. Using the reference knowledge "
        "below, output a single valid Prometheus rules file (YAML) with practical "
        "alerting rules for these service types: "
        f"{', '.join(service_types)}.\n\n"
        "Output ONLY YAML — no markdown fences, no commentary. The top-level key "
        "must be 'groups'.\n\n"
        f"{context}"
    )
    try:
        client = ollama.Client(host=config.OLLAMA_URL)
        resp = client.chat(
            model=config.OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp["message"]["content"] if isinstance(resp, dict) else resp.message.content
    except Exception as e:
        console.print(f"  [yellow]\u26a0[/yellow]  Ollama call failed ({e})")
        return None

    return _strip_fences(text)


def _strip_fences(text: str) -> str:
    """Remove ```yaml / ``` fences a model may add despite instructions."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines)
    return t.strip()


def _validate_yaml(content: str) -> bool:
    try:
        yaml.safe_load(content)
        return True
    except yaml.YAMLError as e:
        console.print(f"  [yellow]\u26a0[/yellow]  YAML parse warning: {e}")
        return False


def _promtool_check(kind: str, path: Path) -> None:
    """Best-effort promtool validation; silent skip if promtool is absent."""
    if not shutil.which("promtool"):
        return
    cmd = ["promtool", "check", "config" if kind == "prometheus" else "rules", str(path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            console.print(f"  [green]\u2713[/green] promtool check {kind}: OK")
        else:
            console.print(f"  [yellow]\u26a0[/yellow]  promtool {kind}: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else 'failed'}")
    except Exception:
        pass


def _write(env: str, config_type: str, content: str, env_id: int) -> Path:
    config.CONFIGS_PATH.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "yml"
    path = config.CONFIGS_PATH / f"{env}-{config_type}-{ts}.{suffix}"
    path.write_text(content, encoding="utf-8")
    queries.save_config(env_id, config_type, content)
    return path


def run_generate(environment: str) -> None:
    init_db()
    env = queries.get_environment(environment)
    if not env:
        console.print(f"[red]Environment '{environment}' not found.[/red]")
        return

    services = queries.get_monitored_services(env["id"])
    if not services:
        console.print(f"[yellow]No services marked for monitoring. Run: monvisor review {environment}[/yellow]")
        return

    scrapeable = [s for s in services
                  if s["service_type"] in _SCRAPEABLE and s.get("monitor_mode") != "blackbox"]
    blackbox = [s for s in services if s.get("monitor_mode") == "blackbox"]

    if not scrapeable and not blackbox:
        console.print(
            "[yellow]None of the monitored services expose Prometheus metrics.[/yellow]\n"
            "  Install an exporter (e.g. node_exporter, mysqld_exporter), or mark a\n"
            "  host 'blackbox' during review to probe it remotely."
        )
        return

    bb_addr, bb_real = ("127.0.0.1:9115", False)
    if blackbox:
        bb_addr, bb_real = _resolve_blackbox_addr(services)
        if not bb_real:
            console.print(
                f"  [yellow]\u26a0[/yellow]  No blackbox_exporter found; defaulting to {bb_addr}.\n"
                "     Deploy blackbox_exporter (or: monvisor config set blackbox-url host:9115)\n"
                "     with http_2xx/https_2xx/tcp_connect modules defined in blackbox.yml."
            )

    service_types = sorted({s["service_type"] for s in scrapeable})
    _msg = f"Generating configs for {len(scrapeable)} exporter target(s)"
    if blackbox:
        _msg += f" + {len(blackbox)} blackbox target(s)"
    console.print(_msg + "...")

    # 1. prometheus.yml (deterministic)
    prom = yaml.dump(
        _build_scrape_configs(scrapeable, blackbox, bb_addr),
        sort_keys=False, default_flow_style=False,
    )
    p_path = _write(environment, "prometheus", prom, env["id"])
    _validate_yaml(prom)
    _promtool_check("prometheus", p_path)
    console.print(f"  [green]\u2713[/green] prometheus.yml \u2192 {p_path}")

    # 2. rules.yml (RAG + Ollama) — skip if blackbox-only (no exporter types).
    if service_types:
        rules = _generate_rules(service_types)
        if rules and _validate_yaml(rules):
            r_path = _write(environment, "rules", rules, env["id"])
            _promtool_check("rules", r_path)
            console.print(f"  [green]\u2713[/green] rules.yml \u2192 {r_path}")
        else:
            console.print("  [dim]rules.yml skipped (generation unavailable or invalid).[/dim]")
    else:
        console.print("  [dim]rules.yml skipped (blackbox-only — no exporter types).[/dim]")

    console.print(f"\n[green]\u2713[/green] Done. Configs saved under {config.CONFIGS_PATH}")
