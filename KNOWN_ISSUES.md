# MonVisor — Known Issues

Working list of open problems blocking a solid free-tier base. Paid-tier (Phase 5)
work is on hold until these are resolved. Newest findings at the bottom of each
section.

Legend: 🔴 blocker · 🟠 broken feature · 🟡 gap/UX · 🔵 needs investigation · 📋 backlog task

---

## Backlog / tasks

### T1 📋 Refresh RAG corpus with current Prometheus + Grafana docs
The bundled knowledge (`pairs`/`exemplars`) needs updating against current
Prometheus and Grafana documentation — config syntax, exporters, PromQL,
alerting/rules, and Grafana provisioning drift over releases and the corpus is
from the initial build. Stale knowledge → stale generated configs and answers.
- Corpus source lives in the separate `MonVisor-Corpus` repo (CC BY-SA 4.0), not
  this repo. Update the shards there, rebuild `combined.jsonl`, re-bundle into
  `monvisor/knowledge/`, then `monvisor init --reset-knowledge`.
- Re-bundle procedure: see `MD-Files/Project_state.md` "Knowledge re-bundle
  procedure" (steps 1–8) and `scripts/bundle_corpus.sh`.
- Scope TBD: which doc sources, how much, versions to target.

---

## Reported from real-world 0.1.x use (James)

### R1 🟠 Scan misses hosts and services on a real home network
`monvisor scan` did not detect all live IPs and running services on James's home
LAN. Coverage is incomplete vs. what is actually on the network.
- **Ground truth: 13 devices live on 192.168.87.0/24.** The June scans
  (`discoveries` in state.db) found only **3 hosts** (host_count=3) — a 3/13 miss,
  ~77% of devices undetected.
- Services found were only on those 3 hosts (.27 dnsmasq/lighttpd, .33 nginx,
  .36 openssh/node_exporter).
- Suspected area: `monvisor/cli/scan.py` (single-pass nmap today), host-discovery
  method (many devices — IoT/printers/phones — won't answer the probes used), port
  list in `config.py` (`ALL_PORTS`), fingerprinting.
- The Architectural_roadmap Phase 4.9 "two-pass scan + hosts table" is the planned
  overhaul, but this is first a correctness bug to reproduce on the current code.
- Status: NOT yet reproduced this session (needs a fresh scan — network noise +
  consent). Repro target: `monvisor scan prod` should find ~13, not 3.

### R2 🟠 `monvisor generate` — partially works, two real bugs (exercised 2026-09-04)
Ran `generate prod` against the 8 existing monitored services (no rescan). The
deterministic `prometheus.yml` was produced, promtool-checked, and persisted to the
`configs` table — but two bugs surfaced. Split into R2a / R2b.

#### R2a ✅ FIXED — rules.yml generation hung; now a hard wall-clock deadline
Was: `_generate_rules()` made an unbounded ollama `client.chat` call. On CPU it
ran for many minutes and `generate` never completed; the whole command hung on the
rules step after prometheus.yml.
- Measured root cause (not prefill — prefill is only ~7.5s for the 5.4 KB rules
  prompt): generation on this 4 GB box runs at ~3 tok/s at that context size, so
  the `num_predict=2048` rules request needs ~11 min of generation. Also httpx's
  own `timeout` is only per-read (does not cap a response that keeps streaming), so
  it was an unreliable bound (observed 187s one run, 656s another).
- Fix: `config.ollama_chat()` now streams and enforces a **hard total wall-clock
  deadline itself** (checks the clock on every chunk, raises `TimeoutError` past
  `OLLAMA_TIMEOUT_S`=180), plus an httpx read timeout (`OLLAMA_IDLE_TIMEOUT_S`=120)
  to catch a stalled server, `think=False`, and the `num_predict` cap. `ask` and
  the rules step both route through it. On timeout the rules step prints a clear
  message and returns None — prometheus.yml is untouched and `generate` exits 0.
- Verified: `generate prod` completes deterministically in ~184s (180s deadline +
  overhead), exit 0, "✓ Done", prometheus.yml written, rules skipped cleanly.
- Expected behaviour by hardware: on this CPU-only box rules.yml is skipped by
  design (2048 tokens can't finish in 180s at ~3 tok/s). On a GPU box (tens of
  tok/s) the same call finishes well under the deadline and rules.yml generates.
  Tunable via `OLLAMA_TIMEOUT_S` / `num_predict` if a slow box must produce rules.
- Tests: `TestOllamaChat` covers the bounds, the `think` fallback, and the hard
  deadline. Suite 19/19.

#### R2b 🟠 generate silently drops services with no native exporter (7 of 8)
Only `node_exporter` (192.168.87.36:9100) reached `prometheus.yml`. The other 7
monitored services (dnsmasq, lighttpd×2, nginx×2, http_generic, openssh) were
dropped with no warning.
- Root cause: routing at `generate.py:239-241`. `scrapeable` = type in `_SCRAPEABLE`
  and `monitor_mode != 'blackbox'`; `blackbox` = `monitor_mode == 'blackbox'`. All 8
  services have `monitor_mode = NULL` because **`review` sets `monitor=1` but never
  assigns `monitor_mode`**. Non-exporter services are therefore neither scrapeable
  nor blackbox → silently excluded.
- Effect: the README's "blackbox fallback for un-instrumentable hosts" and "exporter
  recommendations" never trigger. A service the user approved just disappears.
- Fix scope: `review` must let the user choose a monitor mode (exporter / blackbox /
  skip) per service, or generate must default un-instrumentable approved services to
  blackbox and/or surface exporter recommendations instead of dropping them.
- Related: R4 (add/remove exporters), roadmap Phase 4.8a `configure`.

### R3 🟡 No Grafana integration
No working hook into Grafana (datasource/dashboard provisioning). Listed as
free-tier in Product_overview but not implemented; deeper Grafana automation is
Phase 5.
- Status: scope/decision needed — what belongs in free tier vs paid.

### R4 🟡 No add/remove of exporters and their data
No workflow to add or remove exporters (and the associated inventory/config/data)
after initial generation.
- Related roadmap items: Phase 4.8a `configure`, 4.9 host lifecycle
  (pending/configured/missing/forgotten).
- Status: not implemented.

---

## Found this session (2026-09-04)

### I1 ✅ FIXED — `config set ollama-model` was a dead setting
Was: `config set ollama-model <name>` wrote to the SQLite `settings` table, but
`ask`/`generate` read the hardcoded constant `config.OLLAMA_MODEL = "gemma4:latest"`,
so the model could not be changed without editing source.
- Fix: user settings now live in a YAML file `$HOME/.config/MonVisor/mv.config`
  (source of truth). `config set/get` read/write it (`monvisor/config.py`
  `set_user_setting`/`get_user_setting`); `ask`/`generate` resolve the model via
  `config.ollama_model()` (file → `OLLAMA_MODEL` default) and the URL via
  `config.ollama_url()` (env → file → default). `grafana-url` and `blackbox-url`
  readers moved to the file too. The SQLite `settings` table is retained for
  internal/secret state only (`auth_password_hash`, `knowledge_version`).
- Verified: `config set ollama-model ornith:latest` → `ask` loads ornith (not
  gemma4), returns a clean grounded answer.
- Note: any old `grafana-url`/`blackbox-url` values in the SQLite settings table
  are NOT migrated — re-set them with `config set` if they were configured.

### I2 🟡 Shipping default model — deferred (not a blocker)
Shipped default `gemma4:latest` is gone from the local Ollama. Resolved for now by
pointing `ollama-model` at `ornith:latest` via mv.config — this works and is the
accepted state. Decision (2026-09-04): do NOT swap the LLM now.
- ornith is 9B; on this box it runs ~69% CPU / 31% GPU (RTX 3050 4GB, spills to
  CPU → multi-minute `ask`). Acceptable — a commercial deployment will have more
  VRAM headroom, and even if it does not, it works, which is what matters.
- Left OPEN only as low-priority housekeeping: at some point align the documented
  shipping default (README/INSTALL/config.py `OLLAMA_MODEL`) with a maintained,
  pullable model. No urgency.

### I3 ✅ FIXED — misleading model-error message
Was: on a missing model the error said "Check that Ollama is running…" even though
Ollama was up. Now `ask` calls `config.ollama_status()` and prints either
"Ollama is up, but model '<m>' is unavailable — ollama pull <m> / config set
ollama-model" or the daemon-down detail. (The parallel path in `generate` still
uses a generic message — minor, left for later.)

### I4 🔵 Thinking-model output — validated for `ask`, not yet for `generate`
ornith/qwen3.5 are *thinking* models; concern was leaked reasoning blocks or blank
output on truncation. `ask` with ornith returned clean YAML, no reasoning leak
(ollama chatml template returns final content only). NOT yet validated for
`generate` (the YAML-emit + promtool path). Revisit when R2 is exercised.

### I5 🟡 Ollama up-check now uses ps fallback correctly
Added `config.ollama_status()`: HTTP `/api/tags` primary, `ps ax` → `ollama serve`
fallback (NOT `llama-server`, which only runs while a model is loaded and would
false-negative an idle daemon). Wired into `monvisor init`. Not yet surfaced in a
dedicated `monvisor doctor`/status command — candidate follow-up.
