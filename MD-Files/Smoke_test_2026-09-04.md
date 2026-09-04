# MonVisor — Smoke Test Report

- Date: 2026-09-04
- Branch: `development`
- Tester: James + Claude
- Purpose: re-establish the real state of the free-tier base after a long gap,
  before doing fix work. Point-in-time record; bugs are tracked in
  `KNOWN_ISSUES.md` (referenced by ID below).

## Environment

- Host: bairn, Fedora 44, Python 3.14.7, RTX 3050 4GB (+ Intel Iris Xe), 31 GB RAM.
- Install: editable (`pip install -e .`) in system Python; CLI at `~/.local/bin/monvisor`.
- Data dir: `~/.monvisor/` (state.db, chroma/, reports/, configs/).
- Ollama: `ollama serve` running. Models present: nomic-embed-text (embed),
  qwen3.5, ornith, dolphin3, qwen2.5, granite4.1.
  **`gemma4:latest` (the shipped default LLM) is NOT installed** — env drift (I2).
- User config: `~/.config/MonVisor/mv.config` → `ollama-model: ornith:latest` (I1 fix).

## Automated tests

`python3 -m pytest -v` → **16 passed, 1 warning** (harmless chromadb
DeprecationWarning). Suite is `tests/test_smoke.py`: bundled-knowledge validity,
CLI wiring/registration, ingest replace contract, config sanity, schema, and
exporter-recommendation logic (`TestRecommend`).

Note: `TestRecommend` proves exporter-recommendation logic EXISTS and passes, yet
it never surfaces in real `generate` output (see R2b) — logic present, not wired
into the generate path.

## Command-by-command results

| Command | Result | Notes |
|---|---|---|
| `init` | ✓ works | DB + dirs + knowledge load; Ollama check now via `ollama_status()`. |
| `knowledge status` | ✓ works | 231 pairs / 51 exemplars. |
| `knowledge update` | not exercised | installs a tar.gz knowledge package. |
| `ask` | ✓ works | Routed to ornith (I1 fix). Clean grounded YAML, no reasoning-block leak. Slow: 9B on CPU (multi-minute). |
| `config get/set` | ✓ works | Now backed by `mv.config` (YAML). Verified set→get→used by ask. |
| `env list` | ✓ works | One env: `prod` = 192.168.87.0/24. |
| `scan` | NOT run | Network noise; needs consent + target. R1 repro pending. |
| `review` | help only | Interactive (needs TTY). Root of R2b: sets `monitor=1` but never `monitor_mode`. |
| `generate` | ⚠ partial | prometheus.yml OK + persisted; rules.yml HANGS (R2a); drops 7/8 services (R2b). |
| `nginx` | ✓ works | Emits valid nginx conf (Grafana `/`, UI `/monvisor/`, 80→443). Write-prompt honored. |
| `ui` | help only | Launches a bound web server on :7373 — not exercised here. |
| `deploy` | stub | Phase 5 (paid), intentionally not implemented. |

## Data state (state.db, from June 2026 scans)

- Environments: 1 (`prod`). CIDRs: 1 (192.168.87.0/24).
- Discoveries: 3 runs, each host_count=3.
  **Ground truth: 13 devices live on the /24 → scan found 3 (R1, ~77% miss).**
- Services: 8, all `monitor=1`, all `monitor_mode=NULL`:
  - 192.168.87.27: dnsmasq/53, lighttpd/80, lighttpd/443
  - 192.168.87.33: nginx/80, nginx/443, http_generic/8080
  - 192.168.87.36: openssh/22, node_exporter/9100
- Configs: 1 (prometheus.yml written this session). Dashboards: 0.
- Settings table: `auth_password_hash` (kept), plus a now-dead `ollama-model` row
  left over from a pre-fix `config set` (harmless; mv.config is authoritative).

## Fixed this session

- **I1** — LLM model/URL now user-configurable via `mv.config`; `ask`/`generate`
  resolve through `config.ollama_model()`/`ollama_url()`.
- **I3** — model-missing error distinguishes "Ollama up but model missing" vs down.
- **I5** — `ollama_status()` (API primary, `ps ax`→`ollama serve` fallback).

## Open, prioritized (see KNOWN_ISSUES.md)

1. **R2a 🔴** — `generate` rules.yml hangs (unbounded thinking-model LLM call, no
   timeout). Blocks the command from completing. Smallest fix: timeout + generation
   cap on the ollama calls.
2. **R2b 🟠** — `generate` silently drops services lacking a native exporter
   because `review` never sets `monitor_mode`. No blackbox fallback, no exporter
   recs surface. Fix: assign monitor mode in review (or default+recommend in generate).
3. **R1 🟠** — scan finds 3/13. Needs a fresh scan to reproduce/diagnose.
4. **R3/R4, T1** — Grafana integration, exporter add/remove, RAG corpus refresh.

## Explicitly NOT done (no missteps)

- No network scan run (awaiting consent + target).
- No fixes applied — this was discovery only.
- `ui` server not launched; `review` not driven (interactive).
