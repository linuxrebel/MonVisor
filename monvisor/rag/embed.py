"""
monvisor/rag/embed.py
Embedding via Ollama nomic-embed-text.
"""

from typing import List
import ollama
from monvisor.config import OLLAMA_URL, OLLAMA_EMBED_MODEL


def embed(texts: List[str]) -> List[List[float]]:
    """Embed a list of texts, return list of float vectors."""
    client = ollama.Client(host=OLLAMA_URL)
    vectors = []
    for text in texts:
        response = client.embeddings(model=OLLAMA_EMBED_MODEL, prompt=text)
        vectors.append(response["embedding"])
    return vectors


def embed_one(text: str) -> List[float]:
    """Embed a single text, return float vector."""
    return embed([text])[0]
