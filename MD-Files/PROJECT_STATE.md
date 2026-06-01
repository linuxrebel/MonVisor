# MonVisor — Project State
# Location: /mnt/data/git/AI/MonVisor/PROJECT_STATE.md
# Last updated: 2026-05-31
# Purpose: Full context for resuming work after context window reset

---

## WHAT WAS BUILT (COMPLETED)

### Monitoring Corpus — /mnt/data/git/mon-proj/
A 174-pair instruction-tuning corpus for Prometheus/Alertmanager/Grafana.
Originally built for fine-tuning but REPURPOSED as the RAG knowledge base for MonVisor.

Corpus files:
  train/train.jsonl          — 156 pairs (primary RAG source)
  train/eval.jsonl           — 18 pairs
  corpus/combined.jsonl      — all 174 pairs merged
  corpus/corpus_stats.json   — statistics
  exemplars/                 — annotated reference configs (8 files)
    prometheus_full.yml, alertmanager_full.yml, blackbox_full.yml,
    snmp_full.yml, rules_full.yml, node_exporter_textfile.prom,
    docker-compose-full.yml, grafana_provisioning/ (4 files)
  README.md                  — full corpus documentation

Corpus coverage:
  Prometheus: 81 pairs (config, PromQL, rules, relabeling, SD, TLS, auth, Agent mode, promtool)
  Exporters:  27 pairs (node, blackbox, snmp, mysql, postgres, redis, elasticsearch, windows, k8s)
  Alertmanager: 27 pairs (routing, receivers, templates, HA, time_intervals, API)
  Grafana:    25 pairs (datasource, variables, panels, provisioning, Loki, Tempo, API)
  Integration: 14 pairs (architecture, docker-compose, federation, Kubernetes, remote_write)

Versions pinned: Prometheus 3.12.0, Alertmanager 0.32.1, Grafana 13.0.1

---

## THE PRODUCT — MonVisor

### What it is
An AI-powered, locally-deployed monitoring advisor for Prometheus/Grafana environments.
Scans a network (CIDR input), discovers services, generates production-ready
monitoring configs, and provisions Grafana dashboards. Runs entirely on-premises.
No cloud, no data leaving the environment.

### Product documents (all at /mnt/data/git/AI/MonVisor/)
  ELEVATOR_PITCH.md      — 2 paragraph business pitch
  PRODUCT_OVERVIEW.md    — Executive overview
  ENGINEERING_MAP.md     — Full technical architecture (THE KEY REFERENCE)

### Core workflow
1. User provides CIDR range + environment name (prod/staging/dev)
2. MonVisor scans ports 1-1024 + common high ports
3. Fingerprints services (Prometheus, Grafana, exporters, databases, etc.)
4. Generates human-readable report (terminal rich + HTML)
5. User reviews findings — approves what to monitor (CLI or web UI)
6. MonVisor generates YAML configs via RAG + Ollama
7. Optionally deploys configs via SSH (paid tier)

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
  - Grafana-native review UI (review inside Grafana itself)
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
  cidrs         (id, env_id, cidr, label)          ← multiple CIDRs per environment
  discoveries   (id, env_id, scan_time, cidr, raw_findings JSON)
  services      (id, discovery_id, env_id, host, port, service_type, version, monitor BOOL)
  configs       (id, env_id, config_type, content, generated_at, deployed_at)
  dashboards    (id, env_id, name, source, service_type, content JSON)
  sessions      (id, created_at, expires_at)

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
monvisor knowledge update v1.1.pkg        # install knowledge package update
monvisor config set grafana-url https://grafana.company.com

---

## ACCESS MODEL

Engineer:         SSH → server → CLI commands
Dashboard users:  Browser → Nginx :443 → Grafana (URL configurable)
Review/approval:  Browser → Nginx :443 → /monvisor/ → MonVisor web UI

Nginx sits in front of both Grafana and MonVisor.
Grafana URL is configurable (not hardcoded).
MonVisor web UI is admin/manipulation via CLI only — web is view/review only.
SSH tunnel instruction auto-printed when running on remote server without display.

---

## BUILD PHASES

Phase 1 — Foundation (NEXT TO BUILD)
  - Project scaffold, pyproject.toml, Click CLI entry point
  - SQLite schema + query functions
  - monvisor init command
  - Knowledge package ingest into ChromaDB
  - Basic RAG query verification

Phase 2 — Discovery
  - CIDR scan with python-nmap
  - Service fingerprinting (port → service type mapping)
  - Rich terminal report
  - HTML report generation
  - monvisor scan command

Phase 3 — Review + Generate
  - Terminal review workflow
  - FastAPI web UI + Jinja2 templates
  - Simple bcrypt auth
  - RAG-backed config generation
  - YAML validation (promtool)
  - monvisor review and monvisor generate commands

Phase 4 — Polish + Package
  - Nginx config auto-generation
  - SSH tunnel detection + instruction printing
  - AppImage packaging
  - Knowledge update installer

Phase 5 — Paid Features
  - SSH config deploy
  - Grafana dashboard provisioning API
  - Custom dashboard generation
  - Grafana review UI
  - Enterprise auth stubs (LDAP, Duo, IAM, SAML)

---

## KEY FILES TO KNOW

/mnt/data/git/AI/MonVisor/ENGINEERING_MAP.md   ← Full architecture reference
/mnt/data/git/mon-proj/train/train.jsonl        ← RAG corpus (156 pairs)
/mnt/data/git/mon-proj/exemplars/               ← RAG exemplar configs
/mnt/data/git/mon-proj/README.md                ← Corpus documentation

---

## ENVIRONMENT

OS:       Fedora Linux 44
Machine:  Bairn (james)
GPU:      NVIDIA RTX 3050 4GB Laptop
RAM:      31GB
Python:   3.14.5 (system-wide)
Ollama:   gemma4:latest (8B E4B, Q4_K_M, 9.6GB)
          starcoder:15b, dolphincoder:7b also available
Unsloth:  2026.5.9 (system-wide, not needed for MonVisor)
Torch:    2.10.0+cu128 (system-wide, not needed for MonVisor)

Key paths:
  /mnt/data/git/AI/MonVisor/    ← MonVisor project
  /mnt/data/git/mon-proj/       ← Corpus (RAG knowledge source)
  /mnt/data/git/gemma4-finetune/ ← Abandoned fine-tune attempt (ignore)

---

## RESUME INSTRUCTIONS

Read this file first.
Read ENGINEERING_MAP.md for full technical detail.
Current status: All planning complete, Phase 1 not yet started.
Next action: Scaffold the project structure and begin Phase 1.
