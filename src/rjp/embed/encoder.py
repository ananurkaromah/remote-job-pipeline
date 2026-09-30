"""Embedding via SentenceTransformers bge-small-en-v1.5 (384 dims, ADR-013).

The model is expected to be baked into the Docker image at build time
(HF_HOME pinned, HF_HUB_OFFLINE=1 at runtime -- see Dockerfile and
docs/deployment.md). Import is lazy so that modules which don't need
embedding (most tests) don't require the sentence-transformers package.
"""
from __future__ import annotations

from functools import lru_cache

from rjp import config


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(config.EMBEDDING_MODEL_NAME)


def encode_documents(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    embeddings = _model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def encode_query(text: str) -> list[float]:
    from rjp.embed.templates import build_query_text
    embedding = _model().encode([build_query_text(text)], normalize_embeddings=True, show_progress_bar=False)
    return embedding[0].tolist()
