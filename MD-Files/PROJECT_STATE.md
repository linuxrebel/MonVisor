# MonVisor — Project State
# Location: /mnt/data/git/AI/MonVisor/MD-Files/PROJECT_STATE.md
# Last updated: 2026-06-02 (end of session — v0.1.0 released, all pushed)
# Purpose: Full context for resuming work after context window reset

---

## CURRENT STATUS AT END OF 2026-06-02 SESSION

### Git / Release
- HEAD = origin/main = 7d2cf6c ("README: link to v0.1.0 release")
- FULLY PUSHED — local and remote are in sync, zero unpushed commits
- Tag v0.1.0 is on commit 4533813 (slightly behind HEAD — doc-only delta, harmless)
- v0.1.0 GitHub Release is LIVE: https://github.com/linuxrebel/MonVisor/releases/tag/v0.1.0
  - Assets: monvisor-0.1.0-install.tar.gz + monvisor-0.1.0-py3-none-any.whl
  - Release notes published (Hacker News tone, features listed, GPL-3.0/CC-BY-SA noted)
- dist/ contains: monvisor-0.1.0-install.tar.gz + monvisor-0.1.0-py3-none-any.whl

### Licenses
- MonVisor (code): GPL-3.0-or-later (changed from MIT this session)
- MonVisor-Corpus (data): CC BY-SA 4.0 (set this session)
- Attribution string: "MonVisor-Corpus" by James Sparenberg, licensed CC BY-SA 4.0
  https://github.com/linuxrebel/MonVisor-Corpus

### Knowledge / RAG (on Bairn dev box)
- Pairs: 231 (174 domain + 57 MonVisor self-knowledge)
- Exemplars: 51 chunks (14 files)
- Bundled in: monvisor/knowledge/v1.0/corpus.jsonl + exemplars/ + manifest.json

### Tests
- 16/16 passing

---

## WHAT WAS BUILT THIS SESSION (Phase 4.6)

1. MonVisor self-knowledge corpus shard (57 pairs / 19 topics):
   - MonVisor-Corpus/scripts/build_monvisor_shard.py generates corpus/monvisor.jsonl
   - Covers: all commands, workflow, free/paid boundary, troubleshooting,
     privacy, feedback URL, examples-vs-generate teaching distinction
   - Folded into combined.jsonl (174→231), re-bundled into the package

2. `monvisor ask "<question>"` command:
   - RAG Q&A over local knowledge base (same build_context + Ollama path as generate)
   - Two-layer relevance gate: distance pre-filter (0.40) + LLM INSUFFICIENT_CONTEXT sentinel
   - Fallback: "I've not yet learned how to do that" + GitHub issues URL
   - --show-sources flag; tested live (in-domain / out-of-domain / teaching boundary)

3. Knowledge-store orphaning bug FIXED:
   - store.reset_collection(); ingest_corpus/exemplars take replace= param
   - init replaces when store exists or --reset-knowledge passed
   - knowledge update always replaces (backup still provides rollback)
   - Verified: A+B bug reproduced then fixed

4. init false-success FIXED:
   - Tracks knowledge_ok; empty store → "Incomplete" panel + sys.exit(1)
   - Actionable error message names Ollama/embed-model as cause
   - --reset-knowledge flag added

5. scripts/install.py — one-shot installer (stdlib only):
   - Ensures nmap + curl + zstd + python venv (re-verifies after install)
   - Installs Ollama via consent prompt (--install-ollama / --no-install-ollama)
   - Starts Ollama (systemctl or background), waits for :11434
   - Pulls nomic-embed-text first, then gemma4
   - Finds wheel: local (script dir / CWD / dist/) FIRST, GitHub release fallback
   - Creates venv at ~/.venvs/monvisor, installs, runs init
   - Post-init: verifies knowledge pairs > 0; reports "Done" or "Incomplete"

6. scripts/build_release_tarball.sh:
   - Builds wheel + assembles install.tar.gz (install.py + wheel + INSTALL.md + LICENSE)
   - Extracts into monvisor-{version}-install/; run with: bash scripts/build_release_tarball.sh

7. Docs written/updated:
   - README.md: full install rewrite (curl/zstd prereqs, release tarball path, alias/deactivate)
   - INSTALL.md: complete clone-to-running guide + troubleshooting (all real failure modes)
   - RELEASE.md: repeatable release checklist + realign-stale-tag procedure
   - GPL/CC-BY-SA licensing in README, pyproject, source headers, manifests

8. Relicensed GPL-3.0-or-later:
   - GPL notice header on all 18 source files + 2 scripts
   - pyproject classifier updated
   - MonVisor-Corpus: CC BY-SA 4.0 + attribution string in README

9. Press release / HN announcement post drafted (in chat; not committed to repo)

---

## PENDING (NEXT SESSION — pick up from here)

### High priority
- REBUILD tarball with current code before any distribution:
    bash scripts/build_release_tarball.sh
  (The v0.1.0 release asset was built pre-relicense — the attached tarball's
  LICENSE may say MIT. Options: re-cut v0.1.0 or roll to v0.1.1.)

- VM end-to-end test (clone-free, real download path):
    # Need VM with 12-15 GB free disk (prior VM failed on disk size)
    tar xzf monvisor-0.1.0-install.tar.gz
    cd monvisor-0.1.0-install && python3 install.py
    # Should say "Downloading ... from GitHub release" (not 404 fallback)
    # Ollama-install + zstd branch NOT yet exercised on a real clean box

### Non-blocking / housekeeping
- rm -rf ~/git/mon-proj (stale copy; superseded by MonVisor-Corpus)
- Push MonVisor-Corpus to GitHub (no remote yet)
- scripts/bundle_corpus.sh — corpus→package copy still manual
- pyproject.toml: license table format deprecation warning (harmless until 2027)

### Phase 5 — Paid Features [NEXT MAJOR WORK]
- SSH config deploy
- Grafana dashboard provisioning API
- Custom AI-generated dashboards
- Grafana review UI
- Enterprise auth stubs (LDAP, Duo, IAM, SAML)

---

## DESIGN NOTES / BACKLOG

### Paid tier / code isolation warning
GPL-3.0 covers this repo. DO NOT build paid features in this codebase and
expect to keep them closed-source. Paid features should live in a separate
private repo that is NOT GPL'd, and call/wrap MonVisor as a dependency.

### Agentless monitoring via blackbox_exporter
IMPLEMENTED (2026-06-01). Review offers 'b' = blackbox. Generate produces
blackbox scrape jobs for hosts with no SSH/exporter path detected.

### Knowledge update / re-bundle procedure
When corpus changes:
  1. Edit MonVisor-Corpus/corpus/ shards
  2. Run: python3 MonVisor-Corpus/scripts/build_monvisor_shard.py  (if MonVisor shard changed)
  3. Regenerate combined.jsonl (append or rebuild)
  4. cp MonVisor-Corpus/corpus/combined.jsonl monvisor/knowledge/v1.0/corpus.jsonl
  5. cp -r MonVisor-Corpus/exemplars monvisor/knowledge/v1.0/exemplars
  6. Update monvisor/knowledge/v1.0/manifest.json (pairs count, build_date)
  7. monvisor init --reset-knowledge  (reload the store)
  8. bash scripts/build_release_tarball.sh  (rebuild artifacts)
  (scripts/bundle_corpus.sh would automate steps 4-6 — not yet written)

---

## PROJECT FILE STRUCTURE (current)

/mnt/data/git/AI/MonVisor/
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
│   └── knowledge/
│       └── v1.0/
│           ├── corpus.jsonl   ← 231 pairs (bundled RAG knowledge)
│           ├── exemplars/     ← 14 annotated reference configs
│           └── manifest.json  ← version, pairs:231, license:CC-BY-SA-4.0
├── tests/
│   └── test_smoke.py          ← 16 tests: packaging, CLI, config, schema, recommend,
│                                  ask fallback/registration, ingest replace contract
├── scripts/
│   ├── install.py             ← one-shot installer (stdlib only)
│   └── build_release_tarball.sh ← builds dist/monvisor-{ver}-install.tar.gz
├── MD-Files/
│   ├── PROJECT_STATE.md       ← this file
│   ├── ENGINEERING_MAP.md
│   └── (other docs)
├── INSTALL.md                 ← full install guide + troubleshooting
├── RELEASE.md                 ← release checklist + stale-tag procedure
├── README.md                  ← project overview, links to v0.1.0 release
├── LICENSE                    ← GPL-3.0-or-later (full text)
└── pyproject.toml             ← version=0.1.0, GPL-3.0-or-later classifier

Corpus repo (separate):
/home/james/git/AI/MonVisor-Corpus/
├── corpus/
│   ├── combined.jsonl         ← 231 pairs (all shards + monvisor shard)
│   ├── monvisor.jsonl         ← 57 MonVisor self-knowledge pairs
│   └── *.jsonl                ← 28 domain shards (prometheus, alertmanager, etc.)
├── exemplars/                 ← 14 annotated reference configs
├── scripts/
│   └── build_monvisor_shard.py ← generates corpus/monvisor.jsonl from CLI --help
├── manifest.json              ← corpus build metadata (pinned versions)
├── README.md                  ← CC BY-SA 4.0 license + attribution string
└── LICENSE                    ← CC BY-SA 4.0 (full text)
NOTE: MonVisor-Corpus has NO GitHub remote yet.
Stale copy at ~/git/mon-proj — safe to rm -rf.

---

## ENVIRONMENT

OS:       Fedora Linux 44 (KDE Plasma)
Machine:  Bairn (james), hostname bairn
GPU:      NVIDIA RTX 3050 4GB + Intel Iris Xe
RAM:      31GB
Python:   3.14.5 (system-wide)
Ollama models:
  gemma4:latest              (9.6GB) ← primary LLM — VERIFIED REAL MODEL
  nomic-embed-text:latest    (274MB) ← embedding
  starcoder:15b, dolphincoder:7b, openclaw:latest, uandinotai/dolphin-uncensored:latest

Key paths:
  /mnt/data/git/AI/MonVisor/          = /home/james/git/AI/MonVisor/ (same mount)
  /mnt/data/git/AI/MonVisor-Corpus/   = /home/james/git/AI/MonVisor-Corpus/
  ~/.monvisor/                         ← runtime (state.db, chroma/, reports/, configs/)
  ~/.venvs/monvisor/                   ← installed venv (from installer)

Dev install: editable (pip install -e .) in system Python

---

## RESUME INSTRUCTIONS

1. Read this file top to bottom — all state is here.
2. Read ENGINEERING_MAP.md for technical architecture detail.
3. Verify dev environment still working:
     cd ~/git/AI/MonVisor
     git log --oneline -1             # expect 7d2cf6c
     monvisor knowledge status        # expect 231 / 51
     python3 -m pytest -q             # expect 16 passed
4. START HERE for next work: "PENDING" section above.
   - If doing VM test: rebuild tarball first with build_release_tarball.sh
   - If doing Phase 5: read ENGINEERING_MAP.md Phase 5 section
   - If doing corpus update: follow "Knowledge update / re-bundle procedure" above
