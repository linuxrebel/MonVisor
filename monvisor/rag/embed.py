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
