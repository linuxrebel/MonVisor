# MonVisor — Project State
# Location: /mnt/data/git/AI/MonVisor/MD-Files/PROJECT_STATE.md
# Last updated: 2026-06-01 (Phase 4 complete; blackbox fallback + recommendations added)
# Purpose: Full context for resuming work after context window reset

---

## DESIGN NOTES / BACKLOG

### Agentless monitoring via blackbox_exporter
For hosts where we cannot install an exporter (appliances, locked-down
devices, third-party boxes), fall back to remote/agentless probing with
blackbox_exporter (HTTP/HTTPS/TCP/ICMP modules).

Heuristic for "can't put an agent here":
  - No openssh detected on any port for that host
    → assume no install path → flag host as blackbox-only.
  - generate should then emit a blackbox scrape job (module per probe type:
    http_2xx for web ports, tcp_connect for open TCP, icmp for liveness)
    targeting that host instead of expecting a /metrics endpoint.

Implementation sketch (future, likely Phase 3.5 / generate enhancement):
  - In scan: record per-host whether openssh (or other admin path) was seen.
  - In generate: for monitored hosts with no scrapeable exporter AND no ssh,
    build a blackbox job using the blackbox_exporter target found on the
    network (or note that one must be deployed).
  - Surface in review UI: tag such services "remote-probe only".
  - RAG already has blackbox exemplars — use them for the probe config.

Status: IMPLEMENTED (manual path, 2026-06-01). Review offers 'b' = blackbox/
not installable; generate emits blackbox_<module> jobs (http_2xx/https_2xx/
tcp_connect chosen by port) relabelled through a blackbox_exporter (discovered
instance, else 'blackbox-url' setting, else 127.0.0.1:9115). Exporter
recommendations show in terminal + HTML report (monvisor/recommend.py).
DB: services.monitor_mode column added via additive migration in schema.py.
STILL PENDING: automatic "no openssh on host -> auto-flag blackbox" heuristic
(currently user-driven via the review 'b' choice).

### Report suspected OS of discovered devices
The scan report should announce the suspected OS per host.

Notes:
  - nmap OS fingerprinting (-O) is most accurate but requires root; our scan
    runs unprivileged (-sT), so -O is not available by default.
  - Cheap signal already on hand: service banners from -sV often leak the OS
    (e.g. openssh "9.2p1 Debian 2+deb12u9" → Debian 12; lighttpd/dnsmasq
    versions hint at appliance/embedded). Derive a best-guess from banners.
  - Optionally offer an opt-in privileged scan (sudo) that adds -O for a
    real OS match when the user can run it.
  - Store suspected_os per host (new column on a hosts table, or aggregate
    onto the discovery) and show it in both terminal and HTML reports.
  - Tie-in: a confident "Debian/Linux" guess also informs the blackbox vs.
    agent decision above (Linux + ssh → installable; embedded/no ssh → blackbox).

Status: NOT YET IMPLEMENTED — design note only.

---

## WHAT WAS BUILT (COMPLETED)

### Monitoring Corpus — /mnt/data/git/mon-proj/
A 174-pair instruction-tuning corpus for Prometheus/Alertmanager/Grafana.
REPURPOSED as the RAG knowledge base for MonVisor.

Corpus files:
  train/train.jsonl          — 156 pairs (primary RAG source)
  train/eval.jsonl           — 18 pairs
  corpus/combined.jsonl      — all 174 pairs merged
  exemplars/                 — annotated reference configs (8 files + grafana_provisioning/)
  README.md                  — corpus documentation

Versions pinned: Prometheus 3.12.0, Alertmanager 0.32.1, Grafana 13.0.1

---

## THE PRODUCT — MonVisor

### Product documents — /mnt/data/git/AI/MonVisor/
  MD-Files/PROJECT_STATE.md    ← this file
  MD-Files/ENGINEERING_MAP.md  ← full technical architecture (KEY REFERENCE)
  MD-Files/ELEVATOR_PITCH.md   ← business pitch (md)
  MD-Files/PRODUCT_OVERVIEW.md ← executive overview (md)
  docs/Elevator-Pitch.docx
  docs/Product-Overview.docx
  docs/Engineering-Map.docx

---

## LOCKED ARCHITECTURE DECISIONS

Language:        Python 3.11+
LLM:             Ollama + Gemma4 (model-agnostic later)
Embedding:       nomic-embed-text via Ollama
RAG store:       ChromaDB (LlamaIndex-ready for later upgrade)
API:             FastAPI, on-demand, localhost:7373 only
Web:             Jinja2 + vanilla CSS/JS (no framework)
State:           SQLite (~/.monvisor/state.db)
Auth now:        bcrypt + session tokens
Auth later:      Pluggable interface — LDAP, Duo, AWS IAM, SAML
Reverse proxy:   Nginx (auto-configured by monvisor init)
Packaging:       AppImage (Linux primary), PyInstaller (Mac/Windows)
Port scanning:   python-nmap

---

## TIER STRUCTURE

Free tier (CLI):
  - CIDR scan + service discovery
  - Terminal report (rich) + HTML report
  - Simple web review UI (Yes/No per service)
  - Prometheus, Alertmanager, rules YAML generation
  - Stock Grafana dashboards (view/import manually)
  - RAG knowledge base updates via packages

Paid tier (Professional):
  - Grafana-native review UI
  - Automated config deploy via SSH
  - Custom AI-generated Grafana dashboards
  - Stock dashboard auto-provisioning via Grafana API
  - Enterprise auth (LDAP, Duo, AWS IAM, SAML)
  - Web UI branding

---

## DATA MODEL

Data directory: ~/.monvisor/
  config.yml     — Grafana URL, Ollama URL, auth config, tier
  state.db       — SQLite
  chroma/        — ChromaDB vector store
  reports/       — Generated HTML reports
  configs/       — Generated YAML files
  knowledge/     — Installed RAG knowledge packages
    v1.0/
      corpus.jsonl
      exemplars/
      stock_dashboards/
      manifest.json

Key SQLite tables:
  environments  (id, name, prometheus_url, grafana_url)
  cidrs         (id, env_id, cidr, label)
  discoveries   (id, env_id, scan_time, cidr, raw_findings JSON)
  services      (id, discovery_id, env_id, host, port, service_type, version, monitor BOOL)
  configs       (id, env_id, config_type, content, generated_at, deployed_at)
  dashboards    (id, env_id, name, source, service_type, content JSON)
  sessions      (id, created_at, expires_at)
  settings      (key, value)

---

## CLI COMMANDS

monvisor init                              # setup, load knowledge, set password
monvisor env add prod 192.168.1.0/24       # create named environment with CIDR
monvisor env add-cidr prod 192.168.2.0/24  # add CIDR to existing environment
monvisor env list                          # list all environments
monvisor scan prod                         # scan all CIDRs in environment
monvisor scan prod --new-only              # only scan new hosts
monvisor review prod                       # interactive CLI yes/no review
monvisor generate prod                     # generate YAML configs via RAG+Ollama
monvisor deploy prod                       # SSH push configs (paid)
monvisor ui prod                           # launch web UI (FastAPI)
monvisor knowledge status                  # show RAG store counts
monvisor knowledge update v1.1.pkg        # install knowledge package update
monvisor config set grafana-url https://grafana.company.com

---

## ACCESS MODEL

Engineer:         SSH → server → CLI commands
Dashboard users:  Browser → Nginx :443 → Grafana (URL configurable)
Review/approval:  Browser → Nginx :443 → /monvisor/ → MonVisor web UI
Remote detection: SSH tunnel instructions auto-printed when no display detected

---

## BUILD PHASES

### PHASE 1 — Foundation [COMPLETE]
  ✓ Project scaffold, pyproject.toml, Click CLI entry point
  ✓ SQLite schema + all tables + query functions
  ✓ monvisor init command (working)
  ✓ Knowledge corpus ingested into ChromaDB (275 pairs + 51 exemplars)
  ✓ bcrypt auth (SimpleAuthProvider)
  ✓ RAG query verification passing
  ✓ All CLI command stubs registered
  ✓ nomic-embed-text pulled and working
  ✓ Package installed system-wide (pip install -e .)

  Known fixes applied during Phase 1:
  - Ollama client API version-safe model list detection
  - nomic-embed-text 2048 token limit — exemplars chunked to 1400 chars max

### PHASE 2 — Discovery [COMPLETE]
  ✓ CIDR scan with python-nmap (cli/scan.py) — -sT -sV --open, no root needed
  ✓ Service fingerprinting (FINGERPRINTS port map + nmap product fallback)
  ✓ HTTP probing for secondary fingerprinting (/metrics, /-/healthy, /api/health)
  ✓ Version extraction from *_build_info metrics
  ✓ Rich terminal report grouped by host (cli/report.py)
  ✓ HTML report generation → ~/.monvisor/reports/<env>-<ts>.html
  ✓ monvisor scan command wired (--new-only, --no-html flags)

  New files: monvisor/cli/scan.py, monvisor/cli/report.py
  All three (scan/report/main) py_compile clean.
  Note: requires nmap binary on PATH (sudo dnf install nmap).

### PHASE 3 — Review + Generate [COMPLETE]
  ✓ Terminal review workflow (cli/review.py) — y/n/s/a/q per service
  ✓ FastAPI web UI (api/server.py) + Jinja2 templates + static css/js
  ✓ bcrypt session-cookie auth on web UI (SimpleAuthProvider, httponly cookie)
  ✓ Web review: env list, per-env Yes/No toggles, generate trigger
  ✓ Config generation (cli/generate.py): deterministic prometheus.yml +
    RAG+Ollama rules.yml, YAML validation, best-effort promtool check
  ✓ monvisor review / generate / ui commands wired
  ✓ ui detects headless session → prints SSH tunnel instructions

  New files:
    monvisor/cli/review.py, monvisor/cli/generate.py
    monvisor/api/server.py
    monvisor/web/templates/{base,login,index,report}.html
    monvisor/web/static/{style.css,app.js}
  All py_compile clean. Web deps (fastapi/uvicorn/jinja2) already installed.
  Note: generate's rules.yml needs Ollama running; prometheus.yml is
  deterministic and always produced. promtool check skipped if not on PATH.

### PHASE 4 — Polish + Package [COMPLETE]
  ✓ Nginx config generation (cli/nginx.py) — prints + offers to write with
    confirm; falls back to ~/.monvisor/monvisor.conf if /etc/nginx not writable
  ✓ monvisor nginx [env] command (--print-only); grafana_url resolved from
    env → setting → default; init prints a pointer to it
  ✓ SSH tunnel detection (already in cli ui from Phase 3)
  ✓ Knowledge update installer (cli/update.py): manifest validation,
    path-traversal guard, chroma backup → chroma.bak, reuses ingest_corpus/
    ingest_exemplars, copies payload to ~/.monvisor/knowledge/v<ver>/,
    records knowledge_version, prints changelog
  ✓ monvisor knowledge update <pkg> wired
  ✓ AppImage build scaffold (scripts/build_appimage.sh) — SCAFFOLD ONLY,
    bash -n clean; documents nmap/Ollama as external (unbundled) deps

  New files:
    monvisor/cli/nginx.py, monvisor/cli/update.py
    scripts/build_appimage.sh
  All py_compile clean; build script passes bash -n.
  Note: AppImage not yet built/verified end-to-end (scaffold). PyInstaller
  path (scripts/build_binary.sh) for Mac/Win still pending.

### PHASE 5 — Paid Features [NEXT]
  - SSH config deploy
  - Grafana dashboard provisioning API
  - Custom dashboard generation
  - Grafana review UI
  - Enterprise auth stubs (LDAP, Duo, IAM, SAML)

---

## PROJECT FILE STRUCTURE (current)

/mnt/data/git/AI/MonVisor/
├── monvisor/
│   ├── __init__.py
│   ├── config.py              ← paths, defaults, FINGERPRINTS dict, ensure_dirs()
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py            ← Click CLI, all commands (scan/review/generate are stubs)
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       └── __init__.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── store.py           ← ChromaDB client + collection management
│   │   ├── embed.py           ← nomic-embed-text via Ollama
│   │   ├── ingest.py          ← corpus + exemplar ingestion with chunking
│   │   └── query.py           ← retrieve() + build_context() + verify_rag()
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── base.py            ← AuthProvider abstract class
│   │   └── simple.py          ← bcrypt implementation
│   ├── db/
│   │   ├── __init__.py
│   │   ├── schema.py          ← SQLite schema + init_db() + get_conn()
│   │   └── queries.py         ← all typed query functions
│   └── web/
│       ├── __init__.py
│       ├── templates/         ← empty (Phase 3)
│       └── static/            ← empty (Phase 3)
├── knowledge/
│   └── v1.0/
│       └── stock_dashboards/  ← empty (Phase 5)
├── tests/                     ← empty (to be populated)
├── scripts/                   ← empty (Phase 4 packaging)
├── MD-Files/
│   ├── PROJECT_STATE.md       ← this file
│   ├── ENGINEERING_MAP.md
│   ├── ELEVATOR_PITCH.md
│   └── PRODUCT_OVERVIEW.md
├── docs/
│   ├── Elevator-Pitch.docx
│   ├── Product-Overview.docx
│   └── Engineering-Map.docx
└── pyproject.toml

---

## ENVIRONMENT

OS:       Fedora Linux 44
Machine:  Bairn (james)
GPU:      NVIDIA GeForce RTX 3050 4GB Laptop
RAM:      31GB
Python:   3.14.5 (system-wide)
Ollama models available:
  gemma4:latest              (8B E4B, Q4_K_M, 9.6GB) ← primary LLM
  nomic-embed-text:latest    (274MB) ← embedding model
  starcoder:15b
  dolphincoder:7b
  openclaw:latest
  uandinotai/dolphin-uncensored:latest

Key paths:
  /mnt/data/git/AI/MonVisor/    ← MonVisor project root
  /mnt/data/git/mon-proj/       ← Corpus (RAG knowledge source)
  ~/.monvisor/                  ← Runtime data (state.db, chroma/, reports/, configs/)

Installed packages (system-wide, relevant):
  monvisor 0.1.0 (editable install)
  chromadb, ollama, click, rich, fastapi, uvicorn, jinja2
  python-nmap, bcrypt, itsdangerous, httpx, paramiko, pyyaml

---

## RESUME INSTRUCTIONS

1. Read this file for current status
2. Read ENGINEERING_MAP.md for full technical detail
3. Check current phase above — start from first PENDING phase
4. The monvisor command is available system-wide
5. RAG store is populated — no need to re-run init unless state.db is lost

To verify everything is still working:
  monvisor --help
  monvisor knowledge status
