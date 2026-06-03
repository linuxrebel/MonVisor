# MonVisor — Project State
# Location: /mnt/data/git/AI/MonVisor/MD-Files/PROJECT_STATE.md
# Last updated: 2026-06-02 (v0.1.1 released)
# Purpose: Full context for resuming work after a context-window reset.
#          Read this top to bottom; it is the single source of resume truth.

---

## NEXT MOVE (READ FIRST)

**v0.1.1 is shipped. The next session is a PLANNING session, not a coding one.**

Goal: plan the path forward — primarily Phase 5 (paid features), but also decide
sequencing, scope, and the code-isolation strategy before writing any Phase 5 code.
Do NOT start building Phase 5 in this (GPL) repo without first settling the
"paid tier / code isolation" decision below (see DESIGN NOTES).

Open planning questions to resolve next session:
  1. Where does paid-tier code live? (separate private non-GPL repo that wraps
     MonVisor as a dependency — see isolation warning. Needs a concrete repo plan.)
  2. Phase 5 ordering: which paid feature first? (SSH deploy is the natural MVP —
     it completes the scan→review→generate→DEPLOY loop. Grafana provisioning and
     AI dashboards are larger. Enterprise auth is stubs-first.)
  3. Licensing/commercial model for the paid tier — how the free/paid boundary is
     enforced technically (MONVISOR_TIER exists today as a flag only).
  4. Anything from real-world 0.1.x use that should jump the queue (bugs/UX) before
     paid work starts.

---

## CURRENT STATUS (v0.1.1)

### Release
- v0.1.1 is LIVE on GitHub (published this session): installer-fix patch release.
  - Assets: monvisor-0.1.1-install.tar.gz + monvisor-0.1.1-py3-none-any.whl
  - Patch over 0.1.0: no feature/behavior change to MonVisor itself; installer
    reliability + corrected docs only.
- Version is bumped to 0.1.1 in BOTH load-bearing places: pyproject.toml and
  scripts/install.py (these two + the git tag must always match — see RELEASE.md).
- HEAD = 2716968 (at last update; doc-commit for this state file lands after).
  CONFIRM ON RESUME: `git log --oneline -1`, that the v0.1.1 tag points at the
  release commit, and that origin/main is fully pushed.

### Licenses
- MonVisor (code): GPL-3.0-or-later. LICENSE = full GPL text. GPL header on all
  source files + scripts; pyproject classifier set.
- MonVisor-Corpus (data): CC BY-SA 4.0, separate repo, has a GitHub remote.
  Attribution: "MonVisor-Corpus" by James Sparenberg, CC BY-SA 4.0,
  https://github.com/linuxrebel/MonVisor-Corpus

### Knowledge / RAG
- Pairs: 231 (174 domain + 57 MonVisor self-knowledge). Exemplars: 51 chunks (14 files).
- Bundled in monvisor/knowledge/v1.0/ (corpus.jsonl + exemplars/ + manifest.json).

### Tests
- 16/16 passing (smoke: packaging, CLI, config, schema, recommend, ask
  fallback/registration, ingest replace contract).

### Build phases
- Phases 1–4 COMPLETE (foundation, discovery, review+generate, polish+package).
- Phase 4.6 COMPLETE (self-knowledge corpus, `ask` command, store-orphaning &
  init-false-success fixes — see changelog).
- Phase 5 (paid features) = NEXT MAJOR WORK, not started. Plan first.

---

## CHANGELOG (most recent first)

### 2026-06-02 — v0.1.1 released (installer hardening + docs)
Patch release. Three real installer failure modes found on Ubuntu minimal, fixed,
then verified clean-box end-to-end on CentOS 10 AND Ubuntu 26.04 minimal (both
exercised the full path: Ollama install via official script, zstd extraction,
gemma4 + nomic pulls, venv creation, init verifying 231 pairs).

scripts/install.py fixes:
  1. venv detection false-positive. Was probing `import venv` (pure stdlib, always
     succeeds on Debian/Ubuntu) instead of `ensurepip` (ships separately in the
     pythonX.Y-venv package). EnvBuilder(with_pip=True) needs ensurepip, so the
     check passed and the install died later with "ensurepip is not available."
     Now probes ensurepip; installs the version-specific apt package
     (pythonX.Y-venv, derived from the running interpreter) with an apt-cache
     existence check + generic python3-venv fallback; re-verifies ensurepip in a
     FRESH subprocess (the parent process caches the failed import).
  2. Disk-full handling. A failed gemma4 pull (no space) used to continue and then
     crash with a raw OSError traceback at venv mkdir. Added a pre-flight
     free-space warning (MIN_FREE_GB=20, FREE space not disk size) before the long
     pull, and an ENOSPC guard around venv creation that prints a clean message and
     exits non-zero.
  3. Future-proofing note inline: the pythonX.Y-venv / python3-venv naming is a
     documented known fragility (a future Ubuntu LTS could rename it). On a miss it
     degrades to an actionable manual-install hint, not a crash. Fix-forward is
     adding the new name to apt_venv_pkgs. Deliberately no dynamic resolution.

Docs corrected with REAL disk numbers (from actual installs):
  - Full install consumes ~16–17 GB. 25 GB total disk is the practical minimum
    (lands ~80% full). 35–40 GB total recommended. ~20 GB FREE needed to install.
  - README, INSTALL.md, RELEASE.md, install.py (MIN_FREE_GB) all aligned to these.
  - README + INSTALL.md note multi-distro support (Fedora/RHEL/CentOS/Rocky + apt)
    and the Debian/Ubuntu venv gotcha.
  - RELEASE.md example version strings bumped to 0.1.1.

scripts/bundle_corpus.sh ADDED: automates re-bundle steps 4-6 (corpus + exemplars
copy + manifest pairs/build_date). Steps 2-3 (shard regen) and 7-8 (store reload,
artifact rebuild) stay manual by design.

### 2026-06-02 (earlier) — post-0.1.0 cleanup
- Relicensed MIT → GPL-3.0-or-later (headers, classifier, LICENSE).
- MonVisor-Corpus set to CC BY-SA 4.0, committed, pushed to GitHub.
- Removed stale ~/git/mon-proj copy.

### Phase 4.6 — self-knowledge + ask + RAG fixes
- 57-pair MonVisor self-knowledge corpus shard (build_monvisor_shard.py),
  folded into combined.jsonl (174 → 231 pairs).
- `monvisor ask "<q>"` command: RAG Q&A over local KB, two-layer relevance gate
  (distance pre-filter 0.40 + LLM INSUFFICIENT_CONTEXT sentinel), fallback message
  + issues URL, --show-sources flag.
- Knowledge-store orphaning bug fixed (reset_collection + replace= param; init and
  knowledge-update replace correctly).
- init false-success fixed (empty store → "Incomplete" panel + sys.exit(1);
  --reset-knowledge flag added).

---

## DESIGN NOTES / DECISIONS

### Paid tier / code isolation warning (CRITICAL — affects Phase 5 planning)
GPL-3.0 covers THIS repo. Do NOT build paid/closed features in this codebase and
expect to keep them closed. Paid features must live in a SEPARATE private repo that
is NOT GPL'd and calls/wraps MonVisor as a dependency. This is the first thing to
nail down in Phase 5 planning — the architecture has to support it cleanly
(MonVisor needs to expose the right extension points / stable interfaces).

### Free vs paid boundary today
MONVISOR_TIER env var ('free'/'paid') exists as a flag only; no real enforcement.
deploy.py is a stub. Phase 5 must decide how the boundary is actually enforced.

### Agentless monitoring via blackbox_exporter — IMPLEMENTED
Review offers 'b' = blackbox. Generate produces blackbox scrape jobs for hosts with
no SSH/exporter path detected.

### Knowledge re-bundle procedure (when the corpus changes)
  1. Edit MonVisor-Corpus/corpus/ shards
  2. python3 MonVisor-Corpus/scripts/build_monvisor_shard.py (if MonVisor shard changed)
  3. Regenerate combined.jsonl
  4-6. bash scripts/bundle_corpus.sh   (copies corpus+exemplars, updates manifest)
  7. monvisor init --reset-knowledge   (reload the store)
  8. bash scripts/build_release_tarball.sh  (rebuild artifacts)

### Release procedure
See RELEASE.md. Key invariant: version in pyproject.toml + install.py + git tag must
match, and origin/main must be pushed BEFORE anyone runs the installer (it's fetched
from main via raw.githubusercontent.com).

---

## PROJECT FILE STRUCTURE

/mnt/data/git/AI/MonVisor/   (== /home/james/git/AI/MonVisor/, same mount)
├── monvisor/
│   ├── config.py              ← paths, defaults, FINGERPRINTS, OLLAMA_*, ensure_dirs()
│   ├── cli/
│   │   ├── main.py            ← all commands: init/scan/review/generate/ask/ui/
│   │   │                        deploy/nginx/env/config/knowledge
│   │   ├── scan.py            ← nmap + fingerprinting
│   │   ├── report.py          ← terminal + HTML reports
│   │   ├── review.py          ← terminal review (y/n/b/s/a/q)
│   │   ├── generate.py        ← RAG + Ollama → YAML
│   │   ├── nginx.py           ← nginx config generator
│   │   └── update.py          ← knowledge update (always replace=True)
│   ├── rag/
│   │   ├── store.py           ← ChromaDB client; get_or_create + reset_collection()
│   │   ├── embed.py           ← nomic-embed-text via Ollama
│   │   ├── ingest.py          ← ingest_corpus/exemplars(replace=False)
│   │   └── query.py           ← retrieve() + build_context() + verify_rag()
│   ├── auth/
│   │   ├── base.py            ← AuthProvider abstract
│   │   └── simple.py          ← bcrypt + session tokens
│   ├── db/
│   │   ├── schema.py          ← SQLite schema + init_db() + get_conn()
│   │   └── queries.py         ← typed query functions
│   ├── web/
│   │   ├── templates/         ← FastAPI/Jinja2 templates
│   │   └── static/            ← CSS/JS assets
│   └── knowledge/v1.0/
│       ├── corpus.jsonl       ← 231 pairs (bundled RAG knowledge)
│       ├── exemplars/         ← 14 annotated reference configs
│       └── manifest.json      ← version, pairs:231, license:CC-BY-SA-4.0
├── tests/test_smoke.py        ← 16 tests
├── scripts/
│   ├── install.py             ← one-shot installer (stdlib only); VERSION="0.1.1"
│   ├── bundle_corpus.sh       ← re-bundle corpus into knowledge/ (steps 4-6)
│   └── build_release_tarball.sh ← builds dist/monvisor-{ver}-install.tar.gz
├── MD-Files/{PROJECT_STATE.md, ENGINEERING_MAP.md, ...}
├── INSTALL.md  RELEASE.md  README.md  LICENSE
└── pyproject.toml             ← version=0.1.1, GPL-3.0-or-later

Corpus repo (separate, CC BY-SA 4.0, has GitHub remote):
/home/james/git/AI/MonVisor-Corpus/
├── corpus/{combined.jsonl (231), monvisor.jsonl (57), *.jsonl (28 domain shards)}
├── exemplars/ (14)
├── scripts/build_monvisor_shard.py
├── manifest.json  README.md  LICENSE

---

## ENVIRONMENT

OS:       Fedora Linux 44 (KDE Plasma)
Machine:  Bairn (james), hostname bairn
GPU:      NVIDIA RTX 3050 4GB + Intel Iris Xe
RAM:      31GB
Python:   3.14.5 (system-wide)
Ollama:   gemma4:latest (9.6GB, primary LLM), nomic-embed-text:latest (274MB, embed),
          plus starcoder:15b, dolphincoder:7b, openclaw:latest, uandinotai/dolphin-uncensored

Key paths:
  ~/git/AI/MonVisor/          (== /mnt/data/git/AI/MonVisor/)
  ~/git/AI/MonVisor-Corpus/
  ~/.monvisor/                ← runtime (state.db, chroma/, reports/, configs/)
  ~/.venvs/monvisor/          ← installed venv (from installer)

Dev install: editable (pip install -e .) in system Python.

---

## RESUME INSTRUCTIONS

1. Read this file top to bottom, then ENGINEERING_MAP.md for architecture detail.
2. Verify the dev environment:
     cd ~/git/AI/MonVisor
     git log --oneline -1             # expect 2716968 (or later doc commits)
     git status -s                    # expect clean
     monvisor knowledge status        # expect 231 / 51
     python3 -m pytest -q             # expect 16 passed
3. NEXT MOVE = PLANNING (see "NEXT MOVE" at the top). Resolve the four open
   planning questions before any Phase 5 coding. The code-isolation decision
   (separate non-GPL repo for paid features) gates everything else.
4. When planning is done and Phase 5 coding starts: read the Phase 5 section of
   ENGINEERING_MAP.md, and keep paid code OUT of this GPL repo.
