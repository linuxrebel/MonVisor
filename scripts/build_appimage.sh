#!/usr/bin/env bash
# scripts/build_appimage.sh
# Phase 4 — AppImage packaging scaffold for MonVisor (Linux).
#
# STATUS: SCAFFOLD. The steps below outline the intended build. Sections marked
# TODO are not yet verified end-to-end. Run from the repo root.
#
# Prerequisites (install manually for now):
#   - python3.11+ with the project installed in a clean venv
#   - appimagetool      https://github.com/AppImage/AppImageKit/releases
#   - (optional) python-appimage  for a Python-bundling base
#
set -euo pipefail

APP=MonVisor
VERSION="${1:-0.1.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${ROOT}/build/appimage"
APPDIR="${BUILD}/${APP}.AppDir"

echo "==> Cleaning ${BUILD}"
rm -rf "${BUILD}"
mkdir -p "${APPDIR}/usr/bin"

echo "==> Creating isolated venv and installing monvisor"
python3 -m venv "${APPDIR}/usr/python"
# shellcheck disable=SC1091
source "${APPDIR}/usr/python/bin/activate"
pip install --upgrade pip wheel
pip install "${ROOT}"          # installs monvisor + deps from pyproject
deactivate

# TODO: prune the venv (strip tests, __pycache__, *.dist-info) to shrink the image.

echo "==> Writing AppRun launcher"
cat > "${APPDIR}/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/python/bin:${PATH}"
exec "${HERE}/usr/python/bin/monvisor" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

echo "==> Writing .desktop entry"
cat > "${APPDIR}/${APP}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=${APP}
Exec=monvisor
Icon=monvisor
Categories=Utility;Network;
Terminal=true
EOF

# TODO: provide a real icon. Placeholder keeps appimagetool happy.
touch "${APPDIR}/monvisor.png"

echo "==> Building AppImage"
# Requires appimagetool on PATH. NOTE: bundled CPython is glibc-dependent;
# build on the OLDEST glibc you intend to support for best portability.
if ! command -v appimagetool >/dev/null 2>&1; then
  echo "ERROR: appimagetool not found on PATH. Download it from:"
  echo "  https://github.com/AppImage/AppImageKit/releases"
  exit 1
fi

OUT="${ROOT}/dist/${APP}-${VERSION}-x86_64.AppImage"
mkdir -p "${ROOT}/dist"
ARCH=x86_64 appimagetool "${APPDIR}" "${OUT}"

echo "==> Done: ${OUT}"
echo "    Smoke test:  ${OUT} --help"

# ── Known gaps (TODO before this is production-ready) ────────────────────────
#  - nmap is an external binary dependency; AppImage does NOT bundle it.
#    Document that nmap must be installed on the host (sudo dnf install nmap).
#  - Ollama is a separate service; not bundled by design (model-agnostic).
#  - Verify chromadb's native deps load inside the bundled venv.
#  - Consider PyInstaller path instead (scripts/build_binary.sh) for Mac/Win.
