"""Retrieval subsystem (retrieval-spec.md / ADR-11): chunkers + delta indexer
+ hybrid search service. NOT a RAG chatbot — cited evidence only."""
from __future__ import annotations

from .chunkers import Chunk, chunk_chat, chunk_code, chunk_document, chunk_markdown, chunk_pdf
from .indexer import Indexer, ReindexOutcome, rebuild, reindex_commit
from .service import SearchService, search
from .vectors import VectorStore, VectorUnavailable

__all__ = [
    "Chunk",
    "Indexer",
    "ReindexOutcome",
    "SearchService",
    "VectorStore",
    "VectorUnavailable",
    "chunk_chat",
    "chunk_code",
    "chunk_document",
    "chunk_markdown",
    "chunk_pdf",
    "rebuild",
    "reindex_commit",
    "search",
]