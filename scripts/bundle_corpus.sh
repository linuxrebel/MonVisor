#!/usr/bin/env bash
# MonVisor — AI-assisted monitoring configuration for Prometheus/Grafana.
# Copyright (C) 2026 James Sparenberg
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.

# Re-bundle the MonVisor-Corpus into the MonVisor package's knowledge dir.
# Automates steps 4-6 of the "Knowledge update / re-bundle procedure":
#   - copy combined.jsonl -> monvisor/knowledge/<ver>/corpus.jsonl
#   - copy exemplars/      -> monvisor/knowledge/<ver>/exemplars/
#   - update manifest.json (pairs count + build_date)
#
# Does NOT run build_monvisor_shard.py or regenerate combined.jsonl (steps 2-3)
# and does NOT reload the store or rebuild artifacts (steps 7-8) — those stay
# manual/deliberate. Run those yourself after reviewing this script's diff.
#
# Usage:
#   bash scripts/bundle_corpus.sh                 # auto-detect paths + version
#   CORPUS_REPO=/path bash scripts/bundle_corpus.sh
#   KNOWLEDGE_VER=v1.1 bash scripts/bundle_corpus.sh
set -euo pipefail

cd "$(dirname "$0")/.."                                  # MonVisor repo root
MONVISOR_ROOT="$(pwd)"

# --- locate the corpus repo --------------------------------------------------
CORPUS_REPO="${CORPUS_REPO:-${MONVISOR_ROOT}/../MonVisor-Corpus}"
[ -d "${CORPUS_REPO}" ] || { echo "xx corpus repo not found: ${CORPUS_REPO}"; echo "   set CORPUS_REPO=/path/to/MonVisor-Corpus"; exit 1; }

COMBINED="${CORPUS_REPO}/corpus/combined.jsonl"
EXEMPLARS_SRC="${CORPUS_REPO}/exemplars"
test -f "${COMBINED}"     || { echo "xx not found: ${COMBINED}"; exit 1; }
test -d "${EXEMPLARS_SRC}" || { echo "xx not found: ${EXEMPLARS_SRC}"; exit 1; }

# --- locate the bundled knowledge dir ----------------------------------------
KNOWLEDGE_BASE="${MONVISOR_ROOT}/monvisor/knowledge"
if [ -n "${KNOWLEDGE_VER:-}" ]; then
    KDIR="${KNOWLEDGE_BASE}/${KNOWLEDGE_VER}"
else
    # newest v* dir
    KDIR="$(find "${KNOWLEDGE_BASE}" -maxdepth 1 -type d -name 'v*' | sort -V | tail -1)"
fi
[ -n "${KDIR}" ] && [ -d "${KDIR}" ] || { echo "xx no knowledge dir under ${KNOWLEDGE_BASE} (set KNOWLEDGE_VER=v1.0)"; exit 1; }
MANIFEST="${KDIR}/manifest.json"
test -f "${MANIFEST}" || { echo "xx manifest not found: ${MANIFEST}"; exit 1; }

echo ":: Corpus repo : ${CORPUS_REPO}"
echo ":: Bundle dir  : ${KDIR}"

# --- copy corpus -------------------------------------------------------------
PAIRS="$(grep -c . "${COMBINED}")"
[ "${PAIRS}" -gt 0 ] || { echo "xx combined.jsonl is empty"; exit 1; }
echo ":: Pairs       : ${PAIRS}"

cp "${COMBINED}" "${KDIR}/corpus.jsonl"

# --- copy exemplars (clean replace) ------------------------------------------
rm -rf "${KDIR}/exemplars"
cp -r "${EXEMPLARS_SRC}" "${KDIR}/exemplars"
EX_COUNT="$(find "${KDIR}/exemplars" -type f | wc -l | tr -d ' ')"
echo ":: Exemplars   : ${EX_COUNT} files"

# --- update manifest (pairs + build_date) ------------------------------------
TODAY="$(date +%F)"
python3 - "${MANIFEST}" "${PAIRS}" "${TODAY}" <<'PY'
import json, sys
path, pairs, today = sys.argv[1], int(sys.argv[2]), sys.argv[3]
with open(path) as f:
    m = json.load(f)
m["pairs"] = pairs
m["build_date"] = today
with open(path, "w") as f:
    json.dump(m, f, indent=2)
    f.write("\n")
print(f":: Manifest    : pairs={pairs} build_date={today}")
PY

echo
echo ":: Done. Next steps (manual):"
echo "   1. git diff ${KDIR#${MONVISOR_ROOT}/}        # review the change"
echo "   2. monvisor init --reset-knowledge           # reload the store"
echo "   3. monvisor knowledge status                 # expect ${PAIRS} / ${EX_COUNT}"
echo "   4. bash scripts/build_release_tarball.sh     # rebuild artifacts"
