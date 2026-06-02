# MonVisor — AI-assisted monitoring configuration for Prometheus/Grafana.
# Copyright (C) 2026 James Sparenberg
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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


def reset_collection(name: str) -> chromadb.Collection:
    """Drop a collection and recreate it empty.

    Ingest uses content-hash IDs with upsert, so re-ingesting a *different*
    corpus would otherwise leave the previous documents orphaned in the store
    (new content -> new IDs -> old IDs never removed). Resetting before a fresh
    ingest guarantees the store reflects exactly the corpus being loaded.
    """
    client = get_client()
    try:
        client.delete_collection(name)
    except Exception:
        # Collection may not exist yet — that's fine, we just recreate it.
        pass
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
