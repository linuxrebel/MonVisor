#!/usr/bin/env bash
# Build the self-contained MonVisor install tarball:
#   dist/monvisor-<version>-install.tar.gz
# Contents (extracts into monvisor-<version>-install/):
#   install.py, the wheel, INSTALL.md, LICENSE
# The user extracts it and runs `python3 install.py` — no GitHub needed; the
# installer finds the wheel sitting next to it.
set -euo pipefail

cd "$(dirname "$0")/.."          # repo root

VERSION="$(grep -E '^version' pyproject.toml | head -1 | sed -E 's/.*"([^"]+)".*/\1/')"
WHEEL="monvisor-${VERSION}-py3-none-any.whl"
STAGE_NAME="monvisor-${VERSION}-install"
STAGE="$(mktemp -d)/${STAGE_NAME}"
TARBALL="dist/${STAGE_NAME}.tar.gz"

echo ":: Building wheel for ${VERSION}..."
rm -rf dist build
python -m build --wheel >/dev/null

test -f "dist/${WHEEL}" || { echo "xx wheel not found: dist/${WHEEL}"; exit 1; }

# Sanity: wheel must carry the bundled corpus
PAIRS="$(unzip -p "dist/${WHEEL}" monvisor/knowledge/v1.0/corpus.jsonl | grep -c . || true)"
echo ":: Wheel corpus pairs: ${PAIRS}"
[ "${PAIRS}" -gt 0 ] || { echo "xx wheel has no corpus!"; exit 1; }

echo ":: Assembling ${TARBALL}..."
mkdir -p "${STAGE}"
cp scripts/install.py "${STAGE}/"
cp "dist/${WHEEL}" "${STAGE}/"
cp INSTALL.md LICENSE "${STAGE}/"
tar -czf "${TARBALL}" -C "$(dirname "${STAGE}")" "${STAGE_NAME}"
rm -rf "$(dirname "${STAGE}")"

echo ":: Done: ${TARBALL}"
tar tzf "${TARBALL}"
echo
echo "End user:  tar xzf ${STAGE_NAME}.tar.gz && cd ${STAGE_NAME} && python3 install.py"
