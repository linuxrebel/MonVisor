# MonVisor — Engineering Product Map

## Overview

MonVisor is a locally-deployed, AI-augmented monitoring configuration tool
built on Prometheus, Grafana, and Alertmanager. It combines network discovery,
RAG-based AI advisory, and config generation into a single installable binary.
This document describes the full technical architecture, component breakdown,
data model, and build roadmap.

---

## Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Language | Python 3.11+ | Ecosystem fit, RAG/ML libraries, packaging |
| LLM runtime | Ollama (Gemma4 default) | Local, model-agnostic, no API cost |
| RAG vector store | ChromaDB | Local-first, no server, LlamaIndex-ready |
| Embedding model | nomic-embed-text (via Ollama) | No extra download, good quality |
| API layer | FastAPI | Async, Pydantic, on-demand only |
| Web templates | Jinja2 + vanilla CSS/JS | No framework dependency, lightweight |
| State persistence | SQLite | Single file, portable, no server |
| Auth (now) | bcrypt + session tokens | Simple, secure, no dependencies |
| Auth (later) | Pluggable interface | LDAP, Duo, AWS IAM, SAML |
| Reverse proxy | Nginx (auto-configured) | TLS termination, path routing |
| Packaging | AppImage (Linux), PyInstaller (Mac/Win) | Single binary, no Python required |
| Port scanning | python-nmap | Reliable, well-maintained |

---

## Repository Structure

```
/mnt/data/git/AI/MonVisor/
├── monvisor/
│   ├── cli/
│   │   ├── main.py              # Entry point, Click command routing
│   │   ├── scan.py              # CIDR scan, port detection, service fingerprinting
│   │   ├── report.py            # Rich terminal report + HTML report generation
│   │   ├── generate.py          # Config/dashboard generation via RAG + Ollama
│   │   ├── deploy.py            # SSH push, Grafana API provisioning (Paid)
│   │   └── update.py            # Knowledge package installer
│   ├── api/
│   │   ├── server.py            # FastAPI app, localhost:7373 only
│   │   ├── routes/
│   │   │   ├── environments.py  # CRUD for named environments
│   │   │   ├── discoveries.py   # Discovery results per environment
│   │   │   ├── configs.py       # Generated configs + history
│   │   │   ├── dashboards.py    # Stock + generated dashboards
│   │   │   └── auth.py          # Login, session management
│   │   └── models.py            # Pydantic request/response models
│   ├── rag/
│   │   ├── store.py             # ChromaDB wrapper, collection management
│   │   ├── embed.py             # Embedding via Ollama nomic-embed-text
│   │   ├── query.py             # Retrieval, context assembly for prompts
│   │   └── ingest.py            # Knowledge package loader
│   ├── auth/
│   │   ├── base.py              # AuthProvider interface
│   │   ├── simple.py            # bcrypt implementation (build now)
│   │   ├── ldap.py              # LDAP/AD (stub, build later)
│   │   ├── duo.py               # Duo MFA (stub, build later)
│   │   └── iam.py               # AWS IAM (stub, build later)
│   ├── db/
│   │   ├── schema.py            # SQLite schema, migrations
│   │   └── queries.py           # Typed query functions
│   ├── web/
│   │   ├── templates/
│   │   │   ├── base.html        # Base layout
│   │   │   ├── login.html       # Simple auth page
│   │   │   ├── report.html      # Discovery report + Yes/No review (free)
│   │   │   ├── environment.html # Environment overview
│   │   │   └── configs.html     # Generated config viewer/history
│   │   └── static/
│   │       ├── style.css        # Minimal, clean styling
│   │       └── app.js           # Minimal JS for toggle/submit
│   └── config.py                # Settings, paths, defaults
├── knowledge/
│   └── v1.0/
│       ├── corpus.jsonl         # 174 training pairs (repurposed as RAG docs)
│       ├── exemplars/           # Annotated reference configs
│       ├── stock_dashboards/    # Pre-built Grafana dashboard JSON
│       │   ├── mysql.json
│       │   ├── postgresql.json
│       │   ├── redis.json
│       │   ├── nginx.json
│       │   ├── node_exporter.json
│       │   ├── kubernetes.json
│       │   ├── elasticsearch.json
│       │   └── blackbox.json
│       └── manifest.json        # Version, changelog, compatibility
├── tests/
│   ├── test_scan.py
│   ├── test_rag.py
│   ├── test_generate.py
│   └── test_api.py
├── scripts/
│   ├── build_appimage.sh        # AppImage packaging
│   └── build_binary.sh          # PyInstaller packaging
├── PLAN.md                      # Build plan (this project)
├── ELEVATOR_PITCH.md
├── PRODUCT_OVERVIEW.md
├── ENGINEERING_MAP.md           # This document
└── pyproject.toml               # Package definition, dependencies

---

## Data Directory (client machine)

~/.monvisor/
├── config.yml          # Grafana URL, Ollama URL, auth config, tier
├── state.db            # SQLite database
├── chroma/             # ChromaDB vector store
├── reports/            # Generated HTML reports (named by env + timestamp)
├── configs/            # Generated YAML files (named by env + type + timestamp)
└── knowledge/          # Installed knowledge packages
    └── v1.0/
```

---

## SQLite Schema

```sql
-- Named environments (CIDR groups)
CREATE TABLE environments (
    id          INTEGER PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,       -- 'prod', 'staging', 'dev'
    prometheus_url TEXT,                    -- configurable per environment
    grafana_url TEXT,                       -- configurable per environment
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- CIDRs belonging to an environment (many per environment)
CREATE TABLE cidrs (
    id          INTEGER PRIMARY KEY,
    env_id      INTEGER REFERENCES environments(id),
    cidr        TEXT NOT NULL,              -- '192.168.1.0/24'
    label       TEXT,                       -- optional human label
    added_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Individual scan runs
CREATE TABLE discoveries (
    id          INTEGER PRIMARY KEY,
    env_id      INTEGER REFERENCES environments(id),
    scan_time   DATETIME DEFAULT CURRENT_TIMESTAMP,
    cidr        TEXT,
    host_count  INTEGER,
    raw_findings TEXT                       -- JSON blob
);

-- Individual services found during scan
CREATE TABLE services (
    id              INTEGER PRIMARY KEY,
    discovery_id    INTEGER REFERENCES discoveries(id),
    env_id          INTEGER REFERENCES environments(id),
    host            TEXT NOT NULL,
    port            INTEGER NOT NULL,
    service_type    TEXT,                   -- 'node_exporter', 'mysql', 'nginx', etc.
    version         TEXT,
    monitor         BOOLEAN DEFAULT NULL,  -- NULL=undecided, TRUE=yes, FALSE=no
    notes           TEXT,
    decided_at      DATETIME
);

-- Generated configuration files
CREATE TABLE configs (
    id              INTEGER PRIMARY KEY,
    env_id          INTEGER REFERENCES environments(id),
    config_type     TEXT,                   -- 'prometheus', 'alertmanager', 'rules'
    content         TEXT,                   -- YAML content
    generated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    deployed_at     DATETIME,               -- NULL if not yet deployed
    deployed_by     TEXT
);

-- Grafana dashboards (stock and generated)
CREATE TABLE dashboards (
    id              INTEGER PRIMARY KEY,
    env_id          INTEGER REFERENCES environments(id),
    name            TEXT,
    source          TEXT,                   -- 'stock' or 'generated'
    service_type    TEXT,                   -- what service it covers
    content         TEXT,                   -- Grafana dashboard JSON
    provisioned_at  DATETIME
);

-- Auth sessions
CREATE TABLE sessions (
    id          TEXT PRIMARY KEY,           -- UUID token
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at  DATETIME,
    user        TEXT DEFAULT 'admin'
);
```

---

## Core Workflows

### 1. Init
```
monvisor init
  → Check Ollama running, Gemma4 available
  → Check nomic-embed-text available
  → Create ~/.monvisor/ directory structure
  → Initialize SQLite schema
  → Ingest knowledge/v1.0/ into ChromaDB
  → Set bcrypt password
  → Generate nginx config snippet
  → Print next steps
```

### 2. Scan
```
monvisor scan prod
  → Load all CIDRs for environment 'prod'
  → For each CIDR:
      nmap -sV -p 1-1024,1883,2379,2380,3000,3306,5432,5672,
               6379,6443,7473,8080,8443,8500,9090,9093,9100-9200,
               15672,27017 <cidr>
  → Fingerprint each open port against known service signatures
  → Store raw findings in discoveries table
  → Store individual services in services table
  → Generate terminal report (rich)
  → Generate HTML report → ~/.monvisor/reports/prod-<timestamp>.html
  → Print: "Run 'monvisor review prod' to approve services for monitoring"
```

### 3. Review (Free — terminal)
```
monvisor review prod
  → Load undecided services for environment
  → For each service, rich terminal prompt:
      web01:9100  node_exporter v1.8.2  [Y/n/skip/?]
  → Store decisions in services.monitor
```

### 4. Review (Web UI)
```
monvisor ui prod
  → Start FastAPI on localhost:7373
  → Detect if running on remote server → print SSH tunnel instruction
  → Open browser (if local) or print URL
  → User reviews services in browser, toggles Yes/No
  → Selections POST to /api/discoveries/{id}/decisions
  → Browser confirms saved, user clicks "Generate Configs"
```

### 5. Generate
```
monvisor generate prod
  → Load all services where monitor=TRUE for environment
  → For each service type, query RAG store:
      "scrape config for node_exporter"
      "alerting rules for mysql"
      etc.
  → Assemble context from RAG results + discovered service details
  → Send to Ollama (Gemma4) with structured prompt
  → Parse YAML response, validate syntax
  → Write to ~/.monvisor/configs/prod-prometheus-<timestamp>.yml
  → Write to ~/.monvisor/configs/prod-rules-<timestamp>.yml
  → Write to ~/.monvisor/configs/prod-alertmanager-<timestamp>.yml
  → Print summary + file paths
```

### 6. Deploy (Paid)
```
monvisor deploy prod
  → Load latest generated configs for environment
  → SSH to Prometheus server
  → Backup existing configs
  → Write new configs
  → Run promtool check config (validate before applying)
  → Reload Prometheus (POST /-/reload)
  → Verify targets are UP
  → Report results
```

---

## Service Fingerprinting

Port → service type mapping (partial list):

```python
FINGERPRINTS = {
    9090:  'prometheus',
    9093:  'alertmanager',
    9100:  'node_exporter',
    9104:  'mysqld_exporter',
    9113:  'nginx_exporter',
    9115:  'blackbox_exporter',
    9116:  'snmp_exporter',
    9121:  'redis_exporter',
    9187:  'postgres_exporter',
    9091:  'pushgateway',
    3000:  'grafana',
    3306:  'mysql',
    5432:  'postgresql',
    6379:  'redis',
    6443:  'kubernetes_api',
    8080:  'http_generic',
    8500:  'consul',
    9200:  'elasticsearch',
    27017: 'mongodb',
    5672:  'rabbitmq',
    15672: 'rabbitmq_management',
}
```

Secondary fingerprinting via HTTP response headers and path probing
(e.g. GET /metrics → confirm Prometheus exporter, GET /api/health → Grafana).

---

## RAG Architecture

```
Knowledge Package (corpus.jsonl + exemplars/)
        ↓ ingest.py
ChromaDB collections:
  'pairs'      ← 174 instruction/output pairs
  'exemplars'  ← annotated reference configs
  'dashboards' ← stock dashboard JSON with metadata
        ↓ query.py
Retrieval:
  1. Embed user query via nomic-embed-text
  2. Similarity search → top 5 relevant chunks
  3. Assemble context block
  4. Inject into Ollama prompt with service details
        ↓
Ollama (Gemma4)
        ↓
YAML output → validate → write to disk
```

---

## Auth Architecture

```python
# auth/base.py
class AuthProvider(ABC):
    @abstractmethod
    def authenticate(self, username: str, password: str) -> Optional[str]:
        """Returns session token or None"""

    @abstractmethod
    def validate_token(self, token: str) -> bool:
        """Returns True if token is valid"""

    @abstractmethod
    def logout(self, token: str) -> None:
        pass

# Implementations:
# auth/simple.py   → bcrypt (build now)
# auth/ldap.py     → python-ldap (build later)
# auth/duo.py      → duo_client (build later)
# auth/iam.py      → boto3 (build later)
# auth/saml.py     → pysaml2 (build later, covers Okta/Azure AD)
```

---

## Nginx Auto-Configuration

`monvisor init` generates and prints (does not auto-write without confirmation):

```nginx
# MonVisor nginx configuration
# Generated by monvisor init
# Place in /etc/nginx/conf.d/monvisor.conf

server {
    listen 443 ssl;
    server_name _;

    ssl_certificate     /etc/ssl/certs/monvisor.crt;
    ssl_certificate_key /etc/ssl/private/monvisor.key;

    # Grafana (URL configurable)
    location / {
        proxy_pass http://localhost:3000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # MonVisor web UI
    location /monvisor/ {
        proxy_pass http://localhost:7373/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 80;
    return 301 https://$host$request_uri;
}
```

---

## Build Phases

### Phase 1 — Foundation [COMPLETE]
- ✓ Project scaffold, pyproject.toml, Click CLI entry point
- ✓ SQLite schema + all tables + query functions
- ✓ monvisor init command working
- ✓ ChromaDB loaded: 275 corpus pairs + 51 exemplar chunks
- ✓ bcrypt auth (SimpleAuthProvider)
- ✓ RAG query verification passing
- ✓ nomic-embed-text pulled and working
- ✓ Package installed system-wide (pip install -e .)
- Fixes: Ollama API version-safe detection, exemplar chunking (1400 char max)

### Phase 2 — Discovery [NEXT]
- CIDR scan with python-nmap
- Service fingerprinting (port → service type, HTTP probing)
- Rich terminal report
- HTML report generation → ~/.monvisor/reports/
- monvisor scan command (currently stub)

### Phase 3 — Review + Generate
- Terminal review workflow (CLI yes/no per service)
- Web UI (FastAPI + Jinja2 templates)
- Simple bcrypt auth on web UI
- RAG-backed config generation via Ollama
- YAML validation (promtool)
- monvisor review and monvisor generate commands
- monvisor ui command

### Phase 4 — Polish + Package
- Nginx config auto-generation
- SSH tunnel detection + auto-print instructions
- AppImage packaging
- Knowledge update installer
- monvisor knowledge update command

### Phase 5 — Paid Features
- SSH deploy
- Grafana dashboard provisioning
- Custom dashboard generation
- Grafana review UI
- Enterprise auth stubs

---

## Knowledge Package Format

```
monvisor-knowledge-v1.1.pkg  (tar.gz)
├── manifest.json
│   {
│     "version": "1.1",
│     "min_monvisor": "1.0",
│     "changelog": "Added postgres_exporter v0.15 support",
│     "prometheus_version": "3.12.0",
│     "grafana_version": "13.0.1"
│   }
├── corpus.jsonl             # New/updated pairs
├── exemplars/               # New/updated reference configs
└── stock_dashboards/        # New/updated dashboard JSON
```

Install:
```bash
monvisor knowledge update ./monvisor-knowledge-v1.1.pkg
  → Validate manifest
  → Backup current ChromaDB collection
  → Ingest new documents
  → Update state.db knowledge_version
  → Print changelog
```

---

## Environment Variables

```bash
MONVISOR_HOME        # Override default ~/.monvisor/
MONVISOR_OLLAMA_URL  # Override default http://localhost:11434
MONVISOR_PORT        # Override default web UI port 7373
MONVISOR_TIER        # 'free' or 'paid' (license check in paid)
```

---

## Dependencies (pyproject.toml)

```toml
[project]
name = "monvisor"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "click>=8.1",           # CLI framework
    "rich>=13.0",           # Terminal formatting
    "fastapi>=0.110",       # Web API
    "uvicorn>=0.27",        # ASGI server
    "jinja2>=3.1",          # HTML templates
    "python-nmap>=0.7",     # Port scanning
    "chromadb>=0.5",        # Vector store
    "ollama>=0.2",          # Ollama client
    "pydantic>=2.0",        # Data validation
    "pyyaml>=6.0",          # YAML parsing/generation
    "bcrypt>=4.1",          # Password hashing
    "itsdangerous>=2.1",    # Session tokens
    "httpx>=0.27",          # HTTP client (Grafana API, Prometheus API)
    "paramiko>=3.4",        # SSH (deploy feature)
]
```
