"""
monvisor/rag/query.py
Retrieval logic — query ChromaDB and assemble context for Ollama prompts.
"""

from typing import List, Optional
from monvisor.rag.store import get_or_create_collection
from monvisor.rag.embed import embed_one


def retrieve(query: str, collection_name: str = "pairs", n_results: int = 5) -> List[dict]:
    """
    Embed the query and retrieve the top n_results similar documents.
    Returns list of dicts with 'document' and 'metadata'.
    """
    collection = get_or_create_collection(collection_name)
    if collection.count() == 0:
        return []

    vector = embed_one(query)
    results = collection.query(
        query_embeddings=[vector],
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    out = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        out.append({
            "document": doc,
            "metadata": meta,
            "distance": dist,
        })
    return out


def build_context(query: str, n_pairs: int = 4, n_exemplars: int = 2) -> str:
    """
    Build a context block by retrieving relevant pairs and exemplars.
    Returns a formatted string ready to inject into a prompt.
    """
    pair_results     = retrieve(query, "pairs",     n_results=n_pairs)
    exemplar_results = retrieve(query, "exemplars", n_results=n_exemplars)

    sections = []

    if pair_results:
        sections.append("## Relevant knowledge")
        for r in pair_results:
            sections.append(r["document"])
            sections.append("")

    if exemplar_results:
        sections.append("## Reference configurations")
        for r in exemplar_results:
            fname = r["metadata"].get("filename", "config")
            sections.append(f"### {fname}")
            # Trim exemplar to first 800 chars to keep context window manageable
            sections.append(r["document"][:800])
            sections.append("")

    return "\n".join(sections)


def verify_rag() -> dict:
    """
    Quick health check — confirm both collections exist and have documents.
    Returns dict with counts.
    """
    pairs_col     = get_or_create_collection("pairs")
    exemplars_col = get_or_create_collection("exemplars")
    return {
        "pairs":     pairs_col.count(),
        "exemplars": exemplars_col.count(),
    }
