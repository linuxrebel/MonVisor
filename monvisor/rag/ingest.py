"""
monvisor/rag/ingest.py
Knowledge package loader — ingests corpus JSONL and exemplar configs into ChromaDB.
Fixed: exemplar chunking to stay within nomic-embed-text 2048 token limit.
"""

import json
import hashlib
from pathlib import Path
from typing import List
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from monvisor.rag.store import get_or_create_collection
from monvisor.rag.embed import embed
from monvisor.config import CORPUS_SOURCE, EXEMPLARS_SOURCE

# nomic-embed-text context limit — stay well under 2048 tokens (~1500 chars safe)
MAX_CHUNK_CHARS = 1400


def _doc_id(text: str) -> str:
    """Stable document ID from content hash."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> List[str]:
    """Split text into chunks that fit within the embedding model context."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    while text:
        chunk = text[:max_chars]
        # Try to split on newline boundary
        last_nl = chunk.rfind("\n")
        if last_nl > max_chars // 2:
            chunk = text[:last_nl]
        chunks.append(chunk.strip())
        text = text[len(chunk):].strip()
    return [c for c in chunks if c]


def ingest_corpus(corpus_path: Path = None) -> int:
    """
    Ingest the JSONL corpus pairs into ChromaDB 'pairs' collection.
    Returns number of documents ingested.
    """
    corpus_path = corpus_path or CORPUS_SOURCE
    if not corpus_path.exists():
        raise FileNotFoundError(f"Corpus not found: {corpus_path}")

    pairs = []
    with open(corpus_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    pairs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not pairs:
        return 0

    collection = get_or_create_collection("pairs")

    docs, ids, metas = [], [], []
    for pair in pairs:
        input_part = f"\n\nInput: {pair['input']}" if pair.get("input") else ""
        # Keep instruction + output but trim output if needed
        instruction = pair["instruction"]
        output = pair["output"][:800]  # trim long outputs for embedding
        text = f"Instruction: {instruction}{input_part}\n\nOutput: {output}"
        # Ensure within context limit
        text = text[:MAX_CHUNK_CHARS]
        doc_id = _doc_id(text)
        docs.append(text)
        ids.append(doc_id)
        metas.append({
            "type":        pair["meta"].get("type", ""),
            "topic":       pair["meta"].get("topic", ""),
            "source":      pair["meta"].get("source_url", ""),
            "instruction": pair["instruction"][:200],
        })

    batch_size = 16
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), transient=True) as progress:
        task = progress.add_task("Embedding corpus pairs...", total=len(docs))
        for i in range(0, len(docs), batch_size):
            batch_docs  = docs[i:i+batch_size]
            batch_ids   = ids[i:i+batch_size]
            batch_metas = metas[i:i+batch_size]
            batch_vecs  = embed(batch_docs)
            collection.upsert(
                documents=batch_docs,
                embeddings=batch_vecs,
                ids=batch_ids,
                metadatas=batch_metas,
            )
            progress.advance(task, len(batch_docs))

    return len(docs)


def ingest_exemplars(exemplars_path: Path = None) -> int:
    """
    Ingest annotated reference config files into ChromaDB 'exemplars' collection.
    Long files are chunked to stay within nomic-embed-text context limit.
    Returns number of chunks ingested.
    """
    exemplars_path = exemplars_path or EXEMPLARS_SOURCE
    if not exemplars_path.exists():
        raise FileNotFoundError(f"Exemplars path not found: {exemplars_path}")

    collection = get_or_create_collection("exemplars")

    docs, ids, metas = [], [], []

    for fpath in sorted(exemplars_path.rglob("*")):
        if not fpath.is_file():
            continue
        suffix = fpath.suffix.lower()
        if suffix not in {".yml", ".yaml", ".json", ".prom", ".md"}:
            continue
        try:
            content = fpath.read_text(encoding="utf-8")
        except Exception:
            continue

        # Chunk the file content
        chunks = _chunk_text(f"File: {fpath.name}\n\n{content}")
        for chunk_idx, chunk in enumerate(chunks):
            doc_id = _doc_id(chunk)
            docs.append(chunk)
            ids.append(doc_id)
            metas.append({
                "filename": fpath.name,
                "filetype": suffix.lstrip("."),
                "path":     str(fpath),
                "chunk":    chunk_idx,
            })

    if not docs:
        return 0

    batch_size = 16
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), transient=True) as progress:
        task = progress.add_task("Embedding exemplar configs...", total=len(docs))
        for i in range(0, len(docs), batch_size):
            batch_docs  = docs[i:i+batch_size]
            batch_ids   = ids[i:i+batch_size]
            batch_metas = metas[i:i+batch_size]
            batch_vecs  = embed(batch_docs)
            collection.upsert(
                documents=batch_docs,
                embeddings=batch_vecs,
                ids=batch_ids,
                metadatas=batch_metas,
            )
            progress.advance(task, len(batch_docs))

    return len(docs)
