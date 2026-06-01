"""
monvisor/config.py
Central configuration — paths, defaults, environment variables.
"""

import os
from pathlib import Path

# ── Data directory ────────────────────────────────────────────────────────────
MONVISOR_HOME = Path(os.environ.get("MONVISOR_HOME", Path.home() / ".monvisor"))

DB_PATH        = MONVISOR_HOME / "state.db"
CHROMA_PATH    = MONVISOR_HOME / "chroma"
REPORTS_PATH   = MONVISOR_HOME / "reports"
CONFIGS_PATH   = MONVISOR_HOME / "configs"
KNOWLEDGE_PATH = MONVISOR_HOME / "knowledge"
CONFIG_FILE    = MONVISOR_HOME / "config.yml"

# ── Ollama defaults ───────────────────────────────────────────────────────────
OLLAMA_URL         = os.environ.get("MONVISOR_OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL       = "gemma4:latest"
OLLAMA_EMBED_MODEL = "nomic-embed-text:latest"

# ── Web UI ────────────────────────────────────────────────────────────────────
WEB_PORT = int(os.environ.get("MONVISOR_PORT", 7373))
WEB_HOST = "127.0.0.1"

# ── Knowledge ─────────────────────────────────────────────────────────────────
KNOWLEDGE_VERSION = "1.0"

# Default knowledge ships *inside* the package (monvisor/knowledge/v<ver>/) so a
# fresh install is self-contained. A developer checkout may override with
# MONVISOR_CORPUS / MONVISOR_EXEMPLARS, and we fall back to a sibling
# MonVisor-Corpus checkout if the bundle is somehow absent.
_PKG_DIR       = Path(__file__).resolve().parent
_BUNDLED_KB    = _PKG_DIR / "knowledge" / f"v{KNOWLEDGE_VERSION}"
_DEV_CORPUS    = _PKG_DIR.parent.parent / "MonVisor-Corpus" / "corpus" / "combined.jsonl"
_DEV_EXEMPLARS = _PKG_DIR.parent.parent / "MonVisor-Corpus" / "exemplars"


def _first_existing(*candidates) -> Path:
    """Return the first candidate path that exists, else the first non-None one."""
    fallback = None
    for c in candidates:
        if c is None:
            continue
        if fallback is None:
            fallback = c
        if c.exists():
            return c
    return fallback


CORPUS_SOURCE = _first_existing(
    Path(os.environ["MONVISOR_CORPUS"]) if os.environ.get("MONVISOR_CORPUS") else None,
    _BUNDLED_KB / "corpus.jsonl",
    _DEV_CORPUS,
)
EXEMPLARS_SOURCE = _first_existing(
    Path(os.environ["MONVISOR_EXEMPLARS"]) if os.environ.get("MONVISOR_EXEMPLARS") else None,
    _BUNDLED_KB / "exemplars",
    _DEV_EXEMPLARS,
)

# ── Scanning ─────────────────────────────────────────────────────────────────
# Ports to always scan regardless of range
STANDARD_PORTS = "1-1024"
EXTRA_PORTS    = "1883,2379,2380,3000,3306,5432,5672,6379,6443,7473,8080,8443," \
                 "8500,9090,9091,9093,9100,9101,9102,9103,9104,9113,9114,9115," \
                 "9116,9121,9187,9200,9216,9308,9419,15672,27017"
ALL_PORTS      = f"{STANDARD_PORTS},{EXTRA_PORTS}"

# ── Service fingerprints (port → service type) ────────────────────────────────
FINGERPRINTS = {
    9090:  "prometheus",
    9093:  "alertmanager",
    9091:  "pushgateway",
    9100:  "node_exporter",
    9101:  "haproxy_exporter",
    9102:  "statsd_exporter",
    9104:  "mysqld_exporter",
    9113:  "nginx_exporter",
    9114:  "elasticsearch_exporter",
    9115:  "blackbox_exporter",
    9116:  "snmp_exporter",
    9121:  "redis_exporter",
    9187:  "postgres_exporter",
    9200:  "elasticsearch",
    9216:  "mongodb_exporter",
    9308:  "kafka_exporter",
    9419:  "rabbitmq_exporter",
    3000:  "grafana",
    3306:  "mysql",
    5432:  "postgresql",
    6379:  "redis",
    6443:  "kubernetes_api",
    8080:  "http_generic",
    8443:  "https_generic",
    8500:  "consul",
    1883:  "mqtt",
    2379:  "etcd",
    2380:  "etcd_peer",
    5672:  "rabbitmq",
    7473:  "neo4j",
    15672: "rabbitmq_management",
    27017: "mongodb",
}


def ensure_dirs():
    """Create all required data directories."""
    for path in [MONVISOR_HOME, REPORTS_PATH, CONFIGS_PATH, KNOWLEDGE_PATH, CHROMA_PATH]:
        path.mkdir(parents=True, exist_ok=True)
