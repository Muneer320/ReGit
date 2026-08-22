"""Vector leg — Chroma PersistentClient (data/<store>/vectordb) + MiniLM-L6-v2.

ADR-11: 384-dim, cosine, local + offline (model cached under data/models via
HF_HOME). All heavy imports (chromadb, sentence-transformers, torch) are LAZY
— importing this module must stay cheap so the API and unit tests never pay
for the vector stack unless search/indexing actually uses it.

Failure contract: any problem (missing dep, model download failure, broken
chroma dir) raises :class:`VectorUnavailable`; callers (indexer/service) catch
it and run the deterministic FTS5+provenance pipeline in degraded mode —
never a crash, never a fake result (retrieval-spec.md fallbacks).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class VectorUnavailable(Exception):
    """Vector stack cannot be used (missing dep / model / corrupt chroma)."""


DEFAULT_MODEL = "all-MiniLM-L6-v2"


class VectorStore:
    """Disk-backed embedding index for chunks. Lazy on every heavy resource."""

    def __init__(self, data_dir: str, collection: str = "chunks", model: str = DEFAULT_MODEL) -> None:
        self.root = Path(data_dir)
        self.collection_name = collection
        self.model_name = model
        self._client = None
        self._collection = None
        self._model = None
        # Model cache location (ADR-11: pre-downloaded to data/models at H0).
        os.environ.setdefault("HF_HOME", str(self.root / "models"))

    # -- lazy infra ---------------------------------------------------------

    def _ensure_client(self):
        if self._collection is not None:
            return self._collection
        try:
            import chromadb
        except Exception as exc:  # ImportError / broken install
            raise VectorUnavailable(f"chromadb unavailable: {exc}") from exc
        try:
            client = chromadb.PersistentClient(path=str(self.root / "vectordb"))
            collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            raise VectorUnavailable(f"chroma PersistentClient failed: {exc}") from exc
        self._client = client
        self._collection = collection
        return collection

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:
            raise VectorUnavailable(f"sentence-transformers unavailable: {exc}") from exc
        try:
            model = SentenceTransformer(self.model_name, cache_folder=str(self.root / "models"))
        except Exception as exc:
            raise VectorUnavailable(f"MiniLM model load failed: {exc}") from exc
        self._model = model
        return model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Normalized MiniLM embeddings (cosine-ready)."""
        if not texts:
            return []
        model = self._ensure_model()
        try:
            vecs = model.encode(texts, normalize_embeddings=True)
            return [v.tolist() for v in vecs]
        except Exception as exc:
            raise VectorUnavailable(f"embedding failed: {exc}") from exc

    # -- ops ----------------------------------------------------------------

    def upsert(self, ids: list[str], texts: list[str], metadatas: list[dict] | None = None) -> None:
        """Embed + upsert chunk vectors. Atomicity is NOT guaranteed by chroma;
        failures raise VectorUnavailable and the caller re-runs the keyword
        pipeline (degraded) — the sqlite index is always the source of truth."""
        if not ids:
            return
        collection = self._ensure_client()
        embeddings = self.embed(texts)
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas or [{} for _ in ids],
        )

    def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        collection = self._ensure_client()
        try:
            collection.delete(ids=ids)
        except Exception as exc:
            raise VectorUnavailable(f"chroma delete failed: {exc}") from exc

    def query(self, text: str, n_results: int = 20, where: dict | None = None):
        """kNN over the query embedding -> (ids, cosine_sims) lists.

        Chroma returns cosine DISTANCE for hnsw:space=cosine; we convert to
        similarity (1 - distance). Returns (ids, sims) with 0 results when the
        collection is empty. Any failure -> VectorUnavailable.
        """
        collection = self._ensure_client()
        embeddings = self.embed([text])
        try:
            res = collection.query(
                query_embeddings=embeddings,
                n_results=n_results,
                where=where,
                include=["distances"],
            )
        except Exception as exc:
            raise VectorUnavailable(f"chroma query failed: {exc}") from exc
        ids: list[str] = []
        sims: list[float] = []
        for cid, dist in zip((res.get("ids") or [[]])[0], (res.get("distances") or [[]])[0]):
            ids.append(cid)
            sims.append(1.0 - float(dist))
        return ids, sims