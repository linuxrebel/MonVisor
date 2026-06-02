# Releasing MonVisor

A repeatable checklist for cutting a MonVisor release and publishing the wheel
so the installer's download path works.

## Version locations (keep in sync)

The version lives in two files and must match the git tag:

- `pyproject.toml`        → `version = "X.Y.Z"`
- `scripts/install.py`    → `VERSION = "X.Y.Z"`
- git tag                 → `vX.Y.Z`

If you bump the version, change both files first, in their own commit, before
tagging. A mismatch means the installer builds a URL for the wrong asset.

## Prerequisites

- `gh` (GitHub CLI) authenticated, or use the GitHub web UI for the release step.
- `python -m build` available (`pip install build`).
- All intended changes committed.

## Steps

### 1. Confirm a clean, pushed tree

```bash
cd ~/git/AI/MonVisor
git status -s                      # should be empty
git push origin main               # publish all commits FIRST
```

This matters: the installer is fetched from `main` (raw.githubusercontent.com),
so `main` must be current before anyone runs it. Verify the pushed copy:

```bash
git show origin/main:scripts/install.py | grep -c zstd   # expect a non-zero count
git show origin/main:INSTALL.md | head -1                # expect the title line
```

### 2. Verify version sync

```bash
grep '^version' pyproject.toml          # version = "0.1.0"
grep '^VERSION' scripts/install.py      # VERSION = "0.1.0"
```

Both must match the tag you're about to create.

### 3. Build clean artifacts

```bash
rm -rf dist build
python -m build                         # creates dist/monvisor-X.Y.Z-*.whl + .tar.gz
```

Sanity-check the wheel actually contains the bundled knowledge:

```bash
unzip -p dist/*.whl monvisor/knowledge/v1.0/corpus.jsonl | grep -c .   # expect 231
```

### 4. Tag and push the tag

```bash
git tag -a v0.1.0 -m "MonVisor 0.1.0"
git push origin v0.1.0
```

### 5. Create the GitHub release with both artifacts

```bash
gh release create v0.1.0 \
  dist/monvisor-0.1.0-py3-none-any.whl \
  dist/monvisor-0.1.0.tar.gz \
  --title "MonVisor 0.1.0" \
  --notes "Free-tier CLI: scan, review, generate, ask. Self-contained 231-pair
knowledge base bundled. Requires Ollama (gemma4 + nomic-embed-text) and nmap.
See INSTALL.md."
```

(Web UI alternative: Releases → Draft a new release → choose tag `v0.1.0` →
drag both files from `dist/` into the assets. The wheel filename must stay
exactly `monvisor-0.1.0-py3-none-any.whl` or the installer's download URL
won't match.)

### 6. Verify the published release

```bash
# the URL the installer will hit — should return HTTP 200
curl -fsSL -o /dev/null -w "%{http_code}\n" \
  https://github.com/linuxrebel/MonVisor/releases/download/v0.1.0/monvisor-0.1.0-py3-none-any.whl
```

### 7. End-to-end test (clean box, clone-free)

On a fresh VM or container with enough disk (12–15 GB for models):

```bash
curl -fsSLO https://raw.githubusercontent.com/linuxrebel/MonVisor/main/scripts/install.py
python3 install.py
# then:
source ~/.venvs/monvisor/bin/activate
monvisor knowledge status          # expect 231 / 14
monvisor ask "how do I run a scan"
```

This exercises the real download path (release wheel, not the local fallback).

## Bumping to the next version

1. Edit `version` in `pyproject.toml` and `VERSION` in `scripts/install.py`.
2. If the bundled knowledge changed, rebuild it into the package and update
   `monvisor/knowledge/v1.0/manifest.json`.
3. Commit, then follow steps 1–7 with the new `vX.Y.Z`.

## Notes

- `dist/` is gitignored — release artifacts are never committed, only attached
  to the GitHub release. Always rebuild in step 3 rather than reusing an old
  `dist/`.
- Corpus source lives in the separate `MonVisor-Corpus` repo and is re-bundled
  into `monvisor/knowledge/` before building. Keep that repo pushed too.


## Realigning a stale or mismatched tag

If `git tag` (or `gh release create`) reports the tag already exists, the tag is
probably pointing at an older commit than what you mean to ship. As long as **no
release has been published against it** (the asset URL still 404s) and nobody
has pulled it, you can safely move it:

```bash
git push origin main                    # push the real release commit first
git tag -d vX.Y.Z                        # delete stale local tag
git push origin :refs/tags/vX.Y.Z        # delete stale remote tag
git tag -a vX.Y.Z -m "MonVisor X.Y.Z"    # recreate on current HEAD
git push origin vX.Y.Z
git log --oneline -1 vX.Y.Z              # confirm it's the intended commit
```

Note: `git log <tag-object-sha>` shows the commit it wraps at the top, so an
annotated tag's SHA and its commit's SHA differ while still pointing at the same
commit — that is not a mismatch. A real mismatch is when the *commit* differs.

**Do NOT move a tag once a release is published against it or others may have
pulled it.** At that point, bump to the next patch version (e.g. X.Y.Z+1)
instead — a published tag is immutable in practice.
