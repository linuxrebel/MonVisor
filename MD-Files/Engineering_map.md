# MonVisor — Engineering Product Map
# Last updated: 2026-06-03 (Phases 4.7–4.12 planned)

## Overview

MonVisor is a locally-deployed, AI-augmented monitoring lifecycle management
assistant built on Prometheus, Grafana, and Alertmanager. It runs on its own
dedicated box or VM, separate from the existing monitoring stack. It combines
network discovery, RAG-based AI advisory, interactive configuration, synthetic
monitoring, brownfield import, and config generation into a single installable tool.

The guiding principle: meet the user where they are, then help them get where
they need to go. MonVisor never modifies existing infrastructure without consent.

---

## Deployment Architecture

MonVisor runs on its own host. The existing monitoring stack is untouched.

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│   EXISTING MONITORING BOX   │     │      MONVISOR BOX / VM      │
│  Prometheus (existing)      │     │  MonVisor CLI + Web UI      │
│  Alertmanager (existing)    │     │  Prometheus (managed)       │
│  Grafana (existing)         │     │  Alertmanager (suppressed)  │
│  Alerts: going to oncall    │     │  Grafana (managed)          │
└─────────────────────────────┘     │  Ollama + Gemma4 (9.6GB)   │
                                    │  ChromaDB (3 collections)   │
         User decides cutover  ←────│  SQLite inventory           │
         on their own timeline      │  Synthetic test runner      │
                                    │  nginx (TLS termination)    │
                                    └─────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Language | Python 3.11+ | Ecosystem fit, RAG/ML libraries, packaging |
| LLM runtime | Ollama (Gemma4 default) | Local, model-agnostic, no API cost |
| RAG vector store | ChromaDB | Local-first, no server, 3 collections |
| Embedding model | nomic-embed-text (via Ollama) | No extra download, good quality |
| Web content fetch | httpx + trafilatura | Lightweight HTML extraction, no browser |
| API layer | FastAPI | Async, Pydantic, on-demand only |
| Web templates | Jinja2 + vanilla CSS/JS | No framework dependency, lightweight |
| State persistence | SQLite | Single file, portable, no server |
| Auth (now) | bcrypt + session tokens | Simple, secure, no dependencies |
| Auth (later) | Pluggable interface | LDAP, Duo, AWS IAM, SAML |
| Reverse proxy | Nginx (auto-configured) | TLS termination, path routing |
| Packaging | AppImage (Linux), PyInstaller (Mac/Win) | Single binary |
| Port scanning | python-nmap | Reliable, well-maintained |
| ARP sweep | scapy (optional) | Same-subnet host discovery |
| IaC generation | Ansible + Terraform | DR artifacts (free tier) |

---

## Repository Structure

```
/mnt/data/git/AI/MonVisor/
├── monvisor/
│   ├── cli/
│   │   ├── main.py              # Entry point; all commands
│   │   ├── scan.py              # Two-pass scan, capability detection (4.9)
│   │   ├── hosts.py             # monvisor hosts command (4.9)
│   │   ├── configure.py         # Interactive agent loop (4.8a)
│   │   ├── synthetic.py         # Synthetic test management (4.8b)
│   │   ├── import_config.py     # Brownfield import (4.10)
│   │   ├── cutover.py           # Phase tracking (4.11)
│   │   ├── alerting.py          # Enable/disable/test notification channels (4.11)
│   │   ├── iac.py               # IaC export commands (4.12)
│   │   ├── report.py            # Terminal + HTML report generation
│   │   ├── review.py            # Terminal review workflow
│   │   ├── generate.py          # RAG + Ollama → YAML config generation
│   │   ├── deploy.py            # SSH push (Phase 5 stub)
│   │   ├── nginx.py             # nginx config generator
│   │   └── update.py            # Knowledge package installer
│   ├── api/
│   │   ├── server.py            # FastAPI app, localhost:7373 only
│   │   └── routes/
│   │       ├── environments.py
│   │       ├── discoveries.py
│   │       ├── configs.py
│   │       ├── dashboards.py
│   │       └── auth.py
│   ├── rag/
│   │   ├── store.py             # ChromaDB wrapper, 3-collection management
│   │   ├── embed.py             # Embedding via Ollama nomic-embed-text
│   │   ├── query.py             # Retrieval, 3-tier answer routing (4.7)
│   │   ├── fetch.py             # httpx + trafilatura web fetch (4.7)
│   │   ├── learn.py             # Ingest into 'learned'; TTL management (4.7)
│   │   ├── ingest.py            # Knowledge package loader
│   │   └── prompts.py           # ALL prompt strings, centralised (4.7)
│   ├── net/
│   │   ├── discover.py          # Pass 1: ICMP/ARP/mDNS host discovery (4.9)
│   │   ├── fingerprint.py       # Pass 2: service fingerprinting (4.9)
│   │   └── oui.py               # MAC → vendor lookup (4.9)
│   ├── synthetic/
│   │   ├── runner.py            # Test execution engine, step types (4.8b)
│   │   ├── exporter.py          # Prometheus metrics endpoint :9399 (4.8b)
│   │   └── schema.py            # Test definition YAML validation (4.8b)
│   ├── parsers/
│   │   ├── prometheus.py        # prometheus.yml scrape_config extraction (4.10)
│   │   └── alertmanager.py      # alertmanager.yml parsing (4.10)
│   ├── iac/
│   │   ├── base.py              # Shared rendering logic (4.12)
│   │   ├── ansible.py           # Ansible playbook generator (4.12)
│   │   └── terraform.py         # Terraform module generator (4.12)
│   ├── auth/
│   │   ├── base.py              # AuthProvider abstract interface
│   │   ├── simple.py            # bcrypt + session tokens (current)
│   │   ├── ldap.py              # LDAP/AD (stub)
│   │   ├── duo.py               # Duo MFA (stub)
│   │   └── iam.py               # AWS IAM (stub)
│   ├── db/
│   │   ├── schema.py            # SQLite schema + migrations
│   │   └── queries.py           # Typed query functions
│   ├── web/
│   │   ├── templates/           # FastAPI/Jinja2 templates
│   │   └── static/              # CSS/JS assets
│   ├── data/
│   │   └── oui_mini.json        # Trimmed OUI table ~40KB (4.9)
│   ├── config.py                # Settings, paths, defaults, FINGERPRINTS
│   └── knowledge/v1.0/
│       ├── corpus.jsonl         # 231 pairs (bundled)
│       ├── exemplars/           # 14 annotated reference configs (bundled)
│       └── manifest.json
├── tests/test_smoke.py          # 16 tests (to grow with each phase)
├── scripts/
│   ├── install.py               # One-shot installer (stdlib only)
│   ├── bundle_corpus.sh         # Re-bundle corpus into knowledge/
│   └── build_release_tarball.sh
├── MD-Files/                    # Architecture and planning docs
└── pyproject.toml               # version=0.1.1, GPL-3.0-or-later
```

---

## SQLite Schema

### Existing Tables (unchanged)

```sql
CREATE TABLE environments (
    id          INTEGER PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    prometheus_url TEXT,
    grafana_url TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cidrs (
    id      INTEGER PRIMARY KEY,
    env_id  INTEGER REFERENCES environments(id),
    cidr    TEXT NOT NULL,
    label   TEXT,
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE discoveries (
    id          INTEGER PRIMARY KEY,
    env_id      INTEGER REFERENCES environments(id),
    scan_time   DATETIME DEFAULT CURRENT_TIMESTAMP,
    cidr        TEXT,
    host_count  INTEGER,
    raw_findings TEXT
);

CREATE TABLE services (
    id              INTEGER PRIMARY KEY,
    discovery_id    INTEGER REFERENCES discoveries(id),
    host_id         INTEGER REFERENCES hosts(id),   -- added migration 0002
    env_id          INTEGER REFERENCES environments(id),
    host            TEXT NOT NULL,
    port            INTEGER NOT NULL,
    service_type    TEXT,
    version         TEXT,
    monitor         BOOLEAN DEFAULT NULL,
    notes           TEXT,
    decided_at      DATETIME
);

CREATE TABLE configs (
    id              INTEGER PRIMARY KEY,
    env_id          INTEGER REFERENCES environments(id),
    config_type     TEXT,   -- 'prometheus','alertmanager','rules','custom_scrape'
    content         TEXT,
    generated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    deployed_at     DATETIME,
    deployed_by     TEXT
);

CREATE TABLE dashboards (
    id              INTEGER PRIMARY KEY,
    env_id          INTEGER REFERENCES environments(id),
    name            TEXT,
    source          TEXT,   -- 'stock','generated'
    service_type    TEXT,
    content         TEXT,
    provisioned_at  DATETIME
);

CREATE TABLE sessions (
    id          TEXT PRIMARY KEY,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at  DATETIME,
    user        TEXT DEFAULT 'admin'
);
```

### New Tables (migration 0002 — Phase 4.9)

```sql
CREATE TABLE hosts (
    id              INTEGER PRIMARY KEY,
    env_id          INTEGER REFERENCES environments(id),
    ip              TEXT NOT NULL,
    mac             TEXT,
    vendor          TEXT,
    hostname        TEXT,
    device_type     TEXT,       -- 'printer','camera','router','server',
                                --  'workstation','iot','unknown'
    scan_status     TEXT DEFAULT 'pending',
                                -- 'pending','configured','missing','forgotten'
    -- Probe response profile
    responds_icmp   BOOLEAN DEFAULT NULL,
    responds_arp    BOOLEAN DEFAULT NULL,
    responds_tcp80  BOOLEAN DEFAULT NULL,
    responds_tcp443 BOOLEAN DEFAULT NULL,
    responds_snmp   BOOLEAN DEFAULT NULL,
    responds_mdns   BOOLEAN DEFAULT NULL,
    -- History
    first_seen      DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen       DATETIME,
    scan_count      INTEGER DEFAULT 0,
    notes           TEXT,
    UNIQUE(env_id, ip)
);

CREATE INDEX idx_hosts_env ON hosts(env_id);
CREATE INDEX idx_hosts_ip  ON hosts(ip);

-- Latest services per host without joining through discovery history
CREATE VIEW host_current_services AS
    SELECT s.*
    FROM services s
    INNER JOIN (
        SELECT host_id, MAX(id) AS max_id
        FROM services
        GROUP BY host_id
    ) latest ON s.id = latest.max_id;
```

**History note:** Schema allows adding `host_history` table later (append on
each scan_count increment) without breaking current design. Deferred pending
community input on desired retention behaviour.

---

## ChromaDB Collections

| Collection | Content | Source | Persistence |
|---|---|---|---|
| `pairs` | 231 instruction/output pairs | Bundled with MonVisor | Permanent |
| `exemplars` | 51 chunks / 14 annotated configs | Bundled with MonVisor | Permanent |
| `learned` | Web-fetched + user-pasted content | Runtime, TTL-managed | Prunable |

`learned` metadata per document:
```python
{
  "source_url":   "https://...",
  "fetched_at":   "2026-06-03T14:22:00Z",
  "content_hash": "sha256:...",    # dedup key
  "ttl_days":     7,
  "origin":       "web_fetch" | "user_paste" | "knowledge_add",
  "stale":        False,
}
```

`learned` is never included in the shipped knowledge package. It is runtime
state on the MonVisor host only.

---

## Core Workflows

### 1. Init
```
monvisor init
  → Check Ollama running, Gemma4 + nomic-embed-text available
  → Create ~/.monvisor/ directory structure
  → Run SQLite migrations (all unapplied)
  → Ingest knowledge/v1.0/ into 'pairs' and 'exemplars' collections
  → Set bcrypt password
  → Ask: enable web fetch? (opt-in, stored in config.yml)
  → Generate nginx config snippet
  → Print next steps + current cutover phase (1)
```

### 2. Scan (Greenfield — one-time)
```
monvisor scan <env>
  → Warn if env already has a completed scan (require --refresh to proceed)
  → Detect root/cap_net_raw capabilities
  → Pass 1: host discovery (nmap -sn -T3 + ARP if same-subnet + mDNS passive)
  → Display live host count as discovered
  → Pass 2: service scan against confirmed-live hosts only (-T3)
  → Fingerprint open ports (FINGERPRINTS dict + HTTP probing)
  → Upsert hosts table (responds_* profile recorded)
  → Upsert services table (latest state)
  → Generate terminal report (rich)
  → Generate HTML report → ~/.monvisor/reports/<env>-<timestamp>.html
  → Print: "Run 'monvisor review <env>' to approve services"
```

### 3. Targeted Rescan (On-Demand — post-inventory)
```
monvisor scan <env> --host <ip|cidr>
  → Use known responds_* profile (try known-working probe first)
  → If host responds: update last_seen, upsert services
  → If host does not respond: surface missing-host prompt
      [1] Temporarily offline  [2] Decommissioned  [3] IP reassigned
```

### 4. Brownfield Import
```
monvisor import --prometheus-config /path/to/prometheus.yml
  → Parse scrape_configs, extract targets
  → Create/update environment in SQLite
  → Populate hosts (scan_status='configured') + services tables
  → Flag unresolvable targets for user review
  → Report: N imported, M flagged, K skipped
  → Original file untouched
```

### 5. Review (Terminal)
```
monvisor review <env>
  → Load pending services
  → Rich terminal prompt per service: host:port  type  version  [Y/n/skip/?]
  → Store decisions in services.monitor
```

### 6. Interactive Configure
```
monvisor configure <env> <host>
  → Load host + services from inventory
  → Gemma4 REPL loop: one question at a time (max 8 turns)
  → On [READY_TO_GENERATE]: emit YAML fragment
  → Validate, write to configs table (config_type='custom_scrape')
  → If synthetic branch triggered: route to synthetic test definition flow
  → Offer to save session as corpus pair
```

### 7. Generate
```
monvisor generate <env>
  → Load services where monitor=TRUE + custom_scrape configs
  → RAG query per service type (pairs + exemplars only)
  → Ollama (Gemma4) → YAML
  → Validate (promtool)
  → Write to ~/.monvisor/configs/
  → Regenerate IaC artifacts if 4.12 enabled
```

### 8. Ask (Three-Tier)
```
monvisor ask "<question>"
  → Tier 1: RAG (pairs + exemplars + learned) — grounded answer if hit
  → Tier 2: General domain Ollama — labelled [General knowledge]
  → Tier 3: Web fetch (if enabled) or guided search suggestion
  → --show-sources: distance scores of retrieved pairs
```

### 9. Synthetic Tests
```
monvisor synthetic create <name>     # launches configure agent in synthetic mode
monvisor synthetic start             # starts runner + exporter as systemd unit
monvisor synthetic stop
monvisor synthetic list              # show all tests + last pass/fail
monvisor synthetic status <name>     # step-level detail for one test
```

### 10. Cutover + Alerting
```
monvisor cutover status              # current phase + what it means
monvisor cutover advance             # confirm readiness, move to next phase
monvisor alerting enable pagerduty --integration-key <key>
monvisor alerting enable email --smtp-host <host>
monvisor alerting enable slack --webhook <url>
monvisor alerting test <type>        # send test notification
monvisor alerting disable <type>
```

### 11. IaC Export
```
monvisor iac generate --format ansible
monvisor iac generate --format terraform
monvisor iac status
monvisor iac diff
```

---

## Service Fingerprinting

```python
FINGERPRINTS = {
    # Prometheus ecosystem
    9090:  'prometheus',        9093:  'alertmanager',
    9100:  'node_exporter',     9104:  'mysqld_exporter',
    9113:  'nginx_exporter',    9115:  'blackbox_exporter',
    9116:  'snmp_exporter',     9121:  'redis_exporter',
    9187:  'postgres_exporter', 9091:  'pushgateway',
    # Applications
    3000:  'grafana',           3306:  'mysql',
    5432:  'postgresql',        6379:  'redis',
    6443:  'kubernetes_api',    8080:  'http_generic',
    8500:  'consul',            9200:  'elasticsearch',
    27017: 'mongodb',           5672:  'rabbitmq',
    15672: 'rabbitmq_management',
    # Device/IoT (added 4.9)
    80:    'http_device',       443:   'https_device',
    161:   'snmp',              554:   'rtsp_camera',
    5353:  'mdns_device',
}
```

Secondary fingerprinting: HTTP `Server:` header + path probing
(`/metrics`, `/api/health`, `/cgi-bin/`, `/api/system`).

---

## RAG Architecture

```
Knowledge Package (corpus.jsonl + exemplars/) — bundled, shipped
        ↓ ingest.py
ChromaDB:
  'pairs'     ← 231 pairs  (permanent)
  'exemplars' ← 51 chunks  (permanent)
  'learned'   ← dynamic    (TTL-managed, NOT shipped)
        ↓ query.py (three-tier routing for ask)
Tier 1 → RAG hit from any collection → grounded answer
Tier 2 → General domain Ollama prompt → [General knowledge] label
Tier 3 → httpx+trafilatura web fetch → store in 'learned' → re-query
          OR offline: guided search string + paste-in prompt
        ↓
generate path: 'pairs' + 'exemplars' ONLY (deterministic YAML output)
```

---

## Synthetic Test Architecture

```
Test definition YAML (generated by monvisor configure)
        ↓
monvisor/synthetic/runner.py
  → Step execution engine (HTTP GET/POST, TCP, ICMP, custom)
  → Secret injection from ~/.monvisor/synthetic_secrets/ (0600)
  → Per-step timing, success/fail, value extraction
        ↓
monvisor/synthetic/exporter.py
  → Prometheus metrics endpoint :9399
  → monvisor_synthetic_step_duration_seconds{test,step}
  → monvisor_synthetic_step_success{test,step}
  → monvisor_synthetic_test_success{test}
  → monvisor_synthetic_test_last_run_timestamp{test}
        ↓
Prometheus scrapes :9399 like any other target
Alert rules auto-generated per test (step failure for 2m → alert)
```

---

## Alert Suppression Architecture

MonVisor Alertmanager default config (never auto-modified):
```yaml
route:
  receiver: 'null'
receivers:
  - name: 'null'
```

External receivers added only by `monvisor alerting enable`.
Cutover phase stored in config.yml. Never auto-advanced.

---

## Auth Architecture

```python
class AuthProvider(ABC):
    def authenticate(self, username, password) -> Optional[str]: ...  # token or None
    def validate_token(self, token) -> bool: ...
    def logout(self, token) -> None: ...

# Implementations:
# simple.py  → bcrypt (current)
# ldap.py    → python-ldap (stub)
# duo.py     → duo_client (stub)
# iam.py     → boto3 (stub)
# saml.py    → pysaml2 (stub — Okta/Azure AD)
```

---

## Build Phases

### Phases 1–4 [COMPLETE]
Foundation, discovery, review+generate, polish+package. See PROJECT_STATE.md.

### Phase 4.7 — AI Intelligence [PLANNED]
- 3-tier ask strategy (RAG → domain LLM → web fetch)
- httpx + trafilatura web fetch pipeline
- `learned` ChromaDB collection with TTL
- Offline guided search fallback
- Centralised prompts.py

### Phase 4.8a — Interactive Configure [PLANNED]
- `monvisor configure` agent REPL loop
- Gemma4 drives clarifying questions (max 8 turns)
- [READY_TO_GENERATE] emit signal
- Session-to-corpus-pair saving

### Phase 4.8b — Synthetic Monitoring [PLANNED]
- In-house Python test runner (no external framework)
- Multi-step test definition YAML
- Custom Prometheus exporter :9399
- systemd unit management
- Auto-generated alert rules per test

### Phase 4.9 — Discovery Overhaul [PLANNED]
- Two-pass scan (host discovery → service scan)
- Conservative timing (-T3 default, never T4/T5)
- `hosts` table with probe response profile
- Scan_status lifecycle (pending/configured/missing/forgotten)
- Missing-host prompt on targeted rescan
- `monvisor hosts` command
- OUI vendor lookup (bundled oui_mini.json)

### Phase 4.10 — Brownfield Import [PLANNED]
- `monvisor import --prometheus-config`
- Non-destructive: original file never modified
- Partial import handling with flagging
- Grafana datasource/dashboard import (optional)

### Phase 4.11 — Phased Cutover [PLANNED]
- Alert suppression by default (null receiver)
- Phase 1–4 tracking in config.yml
- `monvisor cutover` and `monvisor alerting` commands
- Test notification support

### Phase 4.12 — IaC Export [PLANNED, free tier]
- Ansible playbook generation
- Terraform module generation
- Auto-regeneration on accepted changes
- Puppet/Salt stubs

### Phase 5 — Paid Features [DEFERRED]
- SSH deploy
- Grafana dashboard provisioning
- Custom dashboard generation
- Enterprise auth (LDAP, Duo, SAML)

---

## Dependencies

```toml
[project]
dependencies = [
    "click>=8.1",
    "rich>=13.0",
    "fastapi>=0.110",
    "uvicorn>=0.27",
    "jinja2>=3.1",
    "python-nmap>=0.7",
    "chromadb>=0.5",
    "ollama>=0.2",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "bcrypt>=4.1",
    "itsdangerous>=2.1",
    "httpx>=0.27",
    "paramiko>=3.4",
    "trafilatura>=1.8",      # added 4.7: HTML content extraction
]

[project.optional-dependencies]
browser = ["playwright>=1.40"]   # 4.7: JS-rendered page fetch
scan    = ["scapy>=2.5"]         # 4.9: ARP sweep (root required)
```

---

## Environment Variables

```bash
MONVISOR_HOME              # override ~/.monvisor/
MONVISOR_OLLAMA_URL        # override http://localhost:11434
MONVISOR_PORT              # override web UI port 7373
MONVISOR_TIER              # 'free' or 'paid'
MONVISOR_WEB_FETCH         # 'true'/'false' override for web fetch
MONVISOR_CONFIGURE_MAX_TURNS   # override 8-turn limit for configure loop
```
