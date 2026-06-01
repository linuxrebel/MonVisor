"""
monvisor/recommend.py
Exporter recommendation logic shared by report and review.

For each host, works out which Prometheus exporters are missing given the
plain services discovered there (e.g. mysql present but no mysqld_exporter),
and always recommends node_exporter for host-level metrics when absent.
"""

from __future__ import annotations

from collections import defaultdict

# Plain service type -> the exporter that exposes its metrics.
EXPORTER_FOR = {
    "mysql":         "mysqld_exporter",
    "postgresql":    "postgres_exporter",
    "redis":         "redis_exporter",
    "nginx":         "nginx_exporter",
    "elasticsearch": "elasticsearch_exporter",
    "mongodb":       "mongodb_exporter",
    "rabbitmq":      "rabbitmq_exporter",
}

# Human-friendly install hints (kept short; not install instructions).
EXPORTER_HINT = {
    "node_exporter":          "host CPU/mem/disk metrics",
    "mysqld_exporter":        "MySQL/MariaDB metrics",
    "postgres_exporter":      "PostgreSQL metrics",
    "redis_exporter":         "Redis metrics",
    "nginx_exporter":         "nginx stub_status metrics",
    "elasticsearch_exporter": "Elasticsearch metrics",
    "mongodb_exporter":       "MongoDB metrics",
    "rabbitmq_exporter":      "RabbitMQ metrics",
}


def host_recommendations(types_on_host: set[str]) -> list[str]:
    """Return ordered, de-duplicated exporter recommendations for one host."""
    recs: list[str] = []
    for st in sorted(types_on_host):
        exp = EXPORTER_FOR.get(st)
        if exp and exp not in types_on_host and exp not in recs:
            recs.append(exp)
    if "node_exporter" not in types_on_host and "node_exporter" not in recs:
        recs.append("node_exporter")
    return recs


def recommendations(services: list[dict]) -> dict[str, list[str]]:
    """
    Map host -> [recommended exporters] for every host that is missing one.
    Hosts whose exporters are all present are omitted.
    """
    by_host: dict[str, set[str]] = defaultdict(set)
    for s in services:
        if s.get("service_type"):
            by_host[s["host"]].add(s["service_type"])

    out: dict[str, list[str]] = {}
    for host, types in by_host.items():
        recs = host_recommendations(types)
        if recs:
            out[host] = recs
    return out
