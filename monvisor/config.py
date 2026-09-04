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
OLLAMA_MODEL       = "gemma4:latest"          # last-resort default (see ollama_model())
OLLAMA_EMBED_MODEL = "nomic-embed-text:latest"

# ── User config file (source of truth for user settings) ──────────────────────
# $HOME/.config/MonVisor/mv.config (YAML). Holds user-facing settings such as
# ollama-model, ollama-url, grafana-url, blackbox-url. Secret/internal state
# (auth password hash, knowledge_version) stays in the SQLite settings table.
USER_CONFIG_DIR  = Path.home() / ".config" / "MonVisor"
USER_CONFIG_FILE = USER_CONFIG_DIR / "mv.config"


def load_user_config() -> dict:
    """Read the YAML user-config file; empty dict if absent or unreadable."""
    import yaml
    try:
        with open(USER_CONFIG_FILE) as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        # A malformed file must not crash the tool; treat as empty.
        return {}


def get_user_setting(key: str, default=None):
    """Read one key from the user-config file."""
    return load_user_config().get(key, default)


def set_user_setting(key: str, value: str):
    """Write one key to the user-config file, creating it if needed."""
    import yaml
    data = load_user_config()
    data[key] = value
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(USER_CONFIG_FILE, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=True)


def ollama_model() -> str:
    """Resolve the LLM model: user config file, else documented default."""
    return get_user_setting("ollama-model") or OLLAMA_MODEL


def ollama_url() -> str:
    """Resolve the Ollama URL: MONVISOR_OLLAMA_URL env, else file, else default."""
    env = os.environ.get("MONVISOR_OLLAMA_URL")
    if env:
        return env
    return get_user_setting("ollama-url") or "http://localhost:11434"


# ── Ollama call bounds ────────────────────────────────────────────────────────
OLLAMA_TIMEOUT_S   = 180    # wall-clock cap per LLM call (httpx read timeout)
OLLAMA_NUM_PREDICT = 1024   # max tokens generated — bounds runaway generation


def ollama_chat(prompt: str, *, system: str = None, think: bool = False,
                temperature: float = 0.0, num_predict: int = OLLAMA_NUM_PREDICT,
                timeout: int = OLLAMA_TIMEOUT_S) -> str:
    """Single-shot chat with bounded generation and a wall-clock timeout.

    Thinking is disabled by default (think=False): the reference models are
    reasoning-capable and, left unbounded on CPU, spend many minutes generating a
    reasoning block before any answer — which is what makes `generate` hang. The
    num_predict cap and the client timeout are backstops. Raises on timeout or
    transport error; the caller decides how to surface it.
    """
    import ollama
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    client = ollama.Client(host=ollama_url(), timeout=timeout)
    opts = {"temperature": temperature, "num_predict": num_predict}
    try:
        resp = client.chat(model=ollama_model(), messages=messages,
                           think=think, options=opts)
    except TypeError:
        # Older ollama-python without the `think` kwarg — still bounded by opts.
        resp = client.chat(model=ollama_model(), messages=messages, options=opts)
    return (resp["message"]["content"] if isinstance(resp, dict)
            else resp.message.content)


def ollama_status() -> tuple:
    """Return (reachable: bool, detail: str) for the Ollama daemon.

    API is primary — an HTTP GET on /api/tags proves it is actually usable.
    ps is the fallback: it matches the daemon process 'ollama serve', NOT
    'llama-server' (the per-model runner only exists while a model is loaded,
    so matching it would report an idle-but-running daemon as down).
    """
    url = ollama_url()
    try:
        import httpx
        httpx.get(f"{url}/api/tags", timeout=3.0).raise_for_status()
        return True, f"reachable at {url}"
    except Exception as api_err:
        try:
            import subprocess
            out = subprocess.run(
                ["ps", "ax"], capture_output=True, text=True, timeout=3
            ).stdout
            if "ollama serve" in out:
                return False, (
                    f"Ollama daemon is running but its API is unreachable at "
                    f"{url} ({api_err})"
                )
        except Exception:
            pass
        return False, f"Ollama not running (API unreachable at {url})"

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
