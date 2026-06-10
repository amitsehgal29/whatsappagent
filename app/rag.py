"""
Retrieval-Augmented Generation (RAG) pipeline.

Chunks a curated gym knowledge corpus at paragraph boundaries, encodes each
chunk into a 384-dimensional embedding vector using the all-MiniLM-L6-v2
sentence transformer, and exposes a ``search()`` function that retrieves the
top-k most semantically similar chunks for a given natural-language query.

Vector similarity is computed via dot product on L2-normalised vectors, which
is mathematically equivalent to cosine similarity for unit vectors.  All
encoding happens once at module-import time to keep per-query latency in the
single-digit millisecond range.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import TOP_K

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
KNOWLEDGE_PATH: Path = Path(__file__).resolve().parent.parent / "data" / "knowledge.txt"

# ---------------------------------------------------------------------------
# Embedding model — loaded once, shared across all queries
# ---------------------------------------------------------------------------
_embedder = SentenceTransformer("all-MiniLM-L6-v2")

# ---------------------------------------------------------------------------
# Corpus ingestion
# ---------------------------------------------------------------------------
try:
    _raw = KNOWLEDGE_PATH.read_text(encoding="utf-8")
except FileNotFoundError:
    raise FileNotFoundError(
        f"Knowledge corpus not found at {KNOWLEDGE_PATH}. "
        "Create a data/knowledge.txt file with your gym information "
        "(one paragraph per chunk, separated by blank lines)."
    ) from None

# Paragraphs separated by blank lines become individual searchable chunks.
_chunks: list[str] = [c.strip() for c in _raw.split("\n\n") if c.strip()]

if not _chunks:
    raise ValueError(
        f"No content found in {KNOWLEDGE_PATH}. "
        "Add gym information as paragraphs separated by blank lines."
    )

# Encode every chunk to a unit vector.  L2-normalisation makes the inner
# product (dot product) identical to cosine similarity.
_chunk_vectors: np.ndarray = _embedder.encode(  # shape (N, 384)
    _chunks,
    normalize_embeddings=True,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search(query: str) -> str:
    """Return the top-K knowledge chunks most relevant to *query*.

    The chunks are concatenated with double-newline separators so the agent
    can inject them directly into the system prompt.
    """
    query_vector: np.ndarray = _embedder.encode(  # shape (384,)
        query,
        normalize_embeddings=True,
    )

    # Cosine-similarity scores for all chunks in a single vectorised operation.
    scores: np.ndarray = _chunk_vectors @ query_vector  # shape (N,)

    # Indices of the top-K chunks, descending by score.
    top_indices: np.ndarray = np.argsort(-scores)[:TOP_K]

    return "\n\n".join(_chunks[i] for i in top_indices)
