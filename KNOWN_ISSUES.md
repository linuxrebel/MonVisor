# MonVisor — Known Issues

Working list of open problems blocking a solid free-tier base. Paid-tier (Phase 5)
work is on hold until these are resolved. Newest findings at the bottom of each
section.

Legend: 🔴 blocker · 🟠 broken feature · 🟡 gap/UX · 🔵 needs investigation

---

## Reported from real-world 0.1.x use (James)

### R1 🟠 Scan misses hosts and services on a real home network
`monvisor scan` did not detect all live IPs and running services on James's home
LAN. Coverage is incomplete vs. what is actually on the network.
- Suspected area: `monvisor/cli/scan.py` (single-pass nmap today), port list in
  `config.py` (`ALL_PORTS`), fingerprinting.
- The Architectural_roadmap Phase 4.9 "two-pass scan + hosts table" is the planned
  overhaul, but this is first a correctness bug to reproduce on the current code.
- Status: NOT yet reproduced/diagnosed this session.

### R2 🟠 Prometheus config generation not proven end-to-end
`monvisor generate` has not been confirmed to produce a viable, promtool-valid
Prometheus config against real discovered services.
- Blocked behind I1/I2 below (LLM model wiring) — generate calls the model.
- Status: NOT yet exercised this session (blocked).

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
