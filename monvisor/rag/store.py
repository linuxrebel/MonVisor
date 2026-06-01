"""
monvisor/rag/store.py
ChromaDB wrapper — collection management and document storage.
"""

import json
from pathlib import Path
from typing import Optional
import chromadb
from chromadb.config import Settings
from monvisor.config import CHROMA_PATH


def get_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(
        path=str(CHROMA_PATH),
        settings=Settings(anonymized_telemetry=False)
    )


def get_or_create_collection(name: str) -> chromadb.Collection:
    client = get_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"}
    )


def collection_count(name: str) -> int:
    try:
        col = get_or_create_collection(name)
        return col.count()
    except Exception:
        return 0
