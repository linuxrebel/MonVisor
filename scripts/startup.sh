#!/bin/bash
# MonVisor startup check script
# Run this at the start of each session to verify everything is healthy
# Usage: bash /mnt/data/git/AI/MonVisor/scripts/startup.sh

set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║       MonVisor — Startup Check       ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. monvisor command available ────────────────────────────────────────────
echo -n "  monvisor command ... "
if command -v monvisor &>/dev/null; then
    VERSION=$(monvisor --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+')
    echo "✓ (v${VERSION})"
else
    echo "✗  Not found. Run: pip3 install -e /mnt/data/git/AI/MonVisor --break-system-packages"
    exit 1
fi

# ── 2. Ollama running ─────────────────────────────────────────────────────────
echo -n "  Ollama service ....... "
if curl -sf http://localhost:11434/api/tags &>/dev/null; then
    echo "✓ Running"
else
    echo "✗  Not running. Start with: ollama serve &"
    echo ""
    echo "  Starting Ollama in background..."
    ollama serve &>/tmp/ollama.log &
    sleep 3
    if curl -sf http://localhost:11434/api/tags &>/dev/null; then
        echo "  ✓ Ollama started"
    else
        echo "  ✗  Failed to start Ollama. Check: tail /tmp/ollama.log"
        exit 1
    fi
fi

# ── 3. Gemma4 available ───────────────────────────────────────────────────────
echo -n "  gemma4:latest ........ "
if ollama list 2>/dev/null | grep -q "gemma4"; then
    echo "✓ Available"
else
    echo "✗  Not found. Run: ollama pull gemma4:latest"
fi

# ── 4. nomic-embed-text available ────────────────────────────────────────────
echo -n "  nomic-embed-text ..... "
if ollama list 2>/dev/null | grep -q "nomic-embed-text"; then
    echo "✓ Available"
else
    echo "✗  Not found. Run: ollama pull nomic-embed-text"
fi

# ── 5. RAG store populated ────────────────────────────────────────────────────
echo -n "  RAG store ............ "
RAG_OUT=$(monvisor knowledge status 2>&1)
PAIRS=$(echo "$RAG_OUT" | grep -o 'Pairs:.*[0-9]\+' | grep -o '[0-9]\+$')
EXEMPLARS=$(echo "$RAG_OUT" | grep -o 'Exemplars:.*[0-9]\+' | grep -o '[0-9]\+$')
if [ -n "$PAIRS" ] && [ "$PAIRS" -gt 0 ]; then
    echo "✓ ${PAIRS} pairs, ${EXEMPLARS} exemplars"
else
    echo "✗  Empty. Run: monvisor init"
fi

# ── 6. State database ─────────────────────────────────────────────────────────
echo -n "  State database ....... "
DB="$HOME/.monvisor/state.db"
if [ -f "$DB" ]; then
    SIZE=$(du -sh "$DB" | cut -f1)
    echo "✓ ${DB} (${SIZE})"
else
    echo "✗  Not found. Run: monvisor init"
fi

# ── 7. Corpus source ──────────────────────────────────────────────────────────
echo -n "  Corpus source ........ "
CORPUS="/mnt/data/git/mon-proj/train/train.jsonl"
if [ -f "$CORPUS" ]; then
    LINES=$(wc -l < "$CORPUS")
    echo "✓ ${CORPUS} (${LINES} pairs)"
else
    echo "✗  Not found at ${CORPUS}"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "  Project root: /mnt/data/git/AI/MonVisor"
echo "  Data dir:     ~/.monvisor/"
echo "  Current phase: Phase 2 — Discovery (NEXT TO BUILD)"
echo ""
echo "  To resume:"
echo "    Read MD-Files/PROJECT_STATE.md and MD-Files/ENGINEERING_MAP.md"
echo "    then say: go"
echo ""
