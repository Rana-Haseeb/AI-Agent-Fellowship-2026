"""
Vector store for the Document Intelligence RAG pipeline.

Wraps a **persistent ChromaDB** collection with **sentence-transformers**
embeddings (via LangChain's ``HuggingFaceEmbeddings``). Exposes a clean,
production-ready interface for indexing, semantic search with optional
metadata filtering, per-document deletion, and a full reset.

Public helpers (module-level, backed by a shared singleton ``VectorStore``):
    - add_documents_to_store(documents)
    - search_similar_chunks(query, k=4, filter_dict=None)
    - delete_document_from_store(file_name)
    - clear_all_vectors()

The embedding model is loaded lazily (only on first embed call), so importing
this module is cheap and safe even before the model is downloaded.
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

# --------------------------------------------------------------------------- #
#  Config & logging
# --------------------------------------------------------------------------- #
logger = logging.getLogger(__name__)
if not logging.getLogger().handlers and not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

PERSIST_DIR = os.environ.get("CHROMA_DIR", ".chroma_db")
COLLECTION_NAME = "documents"
DEFAULT_MODEL = "all-MiniLM-L6-v2"


def _build_default_embeddings(model_name: str):
    """Construct a LangChain HuggingFaceEmbeddings instance (version-robust import).

    Normalized embeddings pair with Chroma's cosine space for stable similarity.
    """
    try:  # LangChain >= 0.2 dedicated package
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:  # pragma: no cover - older langchain
        from langchain_community.embeddings import HuggingFaceEmbeddings

    logger.info("Loading embedding model '%s' (first run downloads it)...", model_name)
    return HuggingFaceEmbeddings(
        model_name=model_name,
        encode_kwargs={"normalize_embeddings": True},
    )


def _sanitize_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Chroma only accepts str/int/float/bool metadata values. Coerce anything
    else (None, lists, dicts) into a safe primitive so ``add`` never fails."""
    clean: Dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        if value is None:
            clean[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            clean[key] = value
        else:
            clean[key] = str(value)
    return clean


def _make_id(text: str, metadata: Dict[str, Any]) -> str:
    """Stable, collision-resistant id from source position + a content hash.
    Re-adding the same chunk upserts in place instead of duplicating."""
    source = metadata.get("source", "doc")
    page = metadata.get("page", 0)
    chunk = metadata.get("chunk", 0)
    digest = hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()[:8]
    return f"{source}::p{page}::c{chunk}::{digest}"


# --------------------------------------------------------------------------- #
#  VectorStore
# --------------------------------------------------------------------------- #
class VectorStore:
    """Persistent ChromaDB collection with lazily-loaded HF embeddings.

    Parameters
    ----------
    persist_dir : str
        Directory for the on-disk Chroma database (default ``.chroma_db``).
    collection_name : str
        Name of the Chroma collection.
    model_name : str
        sentence-transformers model id for embeddings.
    embeddings : optional
        Inject a pre-built embeddings object (must expose ``embed_documents``
        and ``embed_query``). Mainly used for testing; if omitted, a
        HuggingFaceEmbeddings instance is built lazily on first use.
    """

    def __init__(
        self,
        persist_dir: str = PERSIST_DIR,
        collection_name: str = COLLECTION_NAME,
        model_name: str = DEFAULT_MODEL,
        embeddings: Any = None,
    ):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.model_name = model_name
        self._embeddings = embeddings
        self._client = None
        self._collection = None

    # ----- lazy resources ------------------------------------------------- #
    @property
    def embeddings(self):
        if self._embeddings is None:
            self._embeddings = _build_default_embeddings(self.model_name)
        return self._embeddings

    @property
    def client(self):
        if self._client is None:
            os.makedirs(self.persist_dir, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False, allow_reset=True),
            )
        return self._client

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    # ----- write ---------------------------------------------------------- #
    def add_documents_to_store(self, documents: List[Any]) -> int:
        """Embed and upsert a list of LangChain ``Document`` chunks.

        Returns the number of chunks stored (0 on empty input or failure).
        Metadata is preserved (and sanitized) so results remain traceable.
        """
        if not documents:
            logger.warning("add_documents_to_store called with no documents.")
            return 0

        texts, metadatas, ids = [], [], []
        for doc in documents:
            text = getattr(doc, "page_content", None)
            meta = getattr(doc, "metadata", {}) or {}
            if not text or not text.strip():
                continue
            meta = _sanitize_metadata(meta)
            texts.append(text)
            metadatas.append(meta)
            ids.append(_make_id(text, meta))

        if not texts:
            logger.warning("No non-empty chunks to add after filtering.")
            return 0

        try:
            embeddings = self.embeddings.embed_documents(texts)
        except Exception as exc:
            logger.error("Embedding generation failed: %s", exc)
            return 0

        try:
            # upsert avoids duplicate-id errors when re-indexing the same file
            self.collection.upsert(
                ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas
            )
        except Exception as exc:
            logger.error("Failed to write %d chunk(s) to Chroma: %s", len(texts), exc)
            return 0

        logger.info("Stored %d chunk(s) in collection '%s'.", len(texts), self.collection_name)
        return len(texts)

    # ----- read ----------------------------------------------------------- #
    def search_similar_chunks(
        self,
        query: str,
        k: int = 4,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic search over stored chunks.

        Parameters
        ----------
        query : str
            Natural-language question.
        k : int
            Number of chunks to return.
        filter_dict : dict, optional
            Chroma ``where`` filter, e.g. ``{"source": "report.pdf"}`` to
            restrict search to a single document.

        Returns
        -------
        list[dict]
            ``[{"text": str, "metadata": dict, "score": float}]`` ordered by
            descending similarity. Empty list if nothing matches or on error.
        """
        if not query or not query.strip():
            logger.warning("search_similar_chunks called with an empty query.")
            return []

        try:
            total = self.collection.count()
        except Exception as exc:
            logger.error("Could not read collection count: %s", exc)
            return []

        if total == 0:
            logger.info("Search skipped: the vector store is empty.")
            return []

        n_results = max(1, min(k, total))
        where = filter_dict or None

        try:
            query_embedding = self.embeddings.embed_query(query)
            result = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.error("Semantic search failed: %s", exc)
            return []

        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]

        hits: List[Dict[str, Any]] = []
        for text, meta, dist in zip(docs, metas, dists):
            # cosine distance -> similarity in [0, 1]
            score = round(1.0 - float(dist), 4) if dist is not None else None
            hits.append({"text": text, "metadata": meta or {}, "score": score})

        logger.info("Search returned %d hit(s) for query.", len(hits))
        return hits

    # ----- delete --------------------------------------------------------- #
    def delete_document_from_store(self, file_name: str) -> int:
        """Delete all chunks whose ``source`` metadata equals ``file_name``.

        Queries for the matching ids first, then deletes them, so the caller
        gets an accurate count and users can manage their library.
        Returns the number of chunks removed.
        """
        if not file_name:
            logger.warning("delete_document_from_store called with no file_name.")
            return 0

        try:
            matched = self.collection.get(where={"source": file_name}, include=[])
            ids = matched.get("ids", []) or []
        except Exception as exc:
            logger.error("Could not look up chunks for '%s': %s", file_name, exc)
            return 0

        if not ids:
            logger.info("No chunks found for source '%s'; nothing to delete.", file_name)
            return 0

        try:
            self.collection.delete(ids=ids)
        except Exception as exc:
            logger.error("Failed to delete chunks for '%s': %s", file_name, exc)
            return 0

        logger.info("Deleted %d chunk(s) for source '%s'.", len(ids), file_name)
        return len(ids)

    # ----- reset ---------------------------------------------------------- #
    def clear_all_vectors(self) -> bool:
        """Drop and recreate the collection, wiping all stored vectors.
        Returns True on success."""
        try:
            self.client.delete_collection(self.collection_name)
        except Exception as exc:
            # Not fatal — the collection may simply not exist yet.
            logger.warning("delete_collection('%s') skipped: %s", self.collection_name, exc)

        try:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            logger.error("Failed to recreate collection '%s': %s", self.collection_name, exc)
            return False

        logger.info("Cleared all vectors in collection '%s'.", self.collection_name)
        return True

    # ----- introspection (handy for the UI library view) ------------------ #
    def count(self) -> int:
        """Total number of stored chunks."""
        try:
            return self.collection.count()
        except Exception as exc:
            logger.error("count() failed: %s", exc)
            return 0

    def list_sources(self) -> List[str]:
        """Distinct source document names currently in the store."""
        try:
            data = self.collection.get(include=["metadatas"])
        except Exception as exc:
            logger.error("list_sources() failed: %s", exc)
            return []
        sources = {
            (m or {}).get("source")
            for m in (data.get("metadatas") or [])
            if (m or {}).get("source")
        }
        return sorted(sources)


# --------------------------------------------------------------------------- #
#  Module-level singleton + thin function wrappers (import-friendly)
# --------------------------------------------------------------------------- #
_default_store: Optional[VectorStore] = None


def get_store() -> VectorStore:
    """Return the shared VectorStore singleton (created on first call)."""
    global _default_store
    if _default_store is None:
        _default_store = VectorStore()
    return _default_store


def add_documents_to_store(documents: List[Any]) -> int:
    return get_store().add_documents_to_store(documents)


def search_similar_chunks(query: str, k: int = 4,
                          filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    return get_store().search_similar_chunks(query, k=k, filter_dict=filter_dict)


def delete_document_from_store(file_name: str) -> int:
    return get_store().delete_document_from_store(file_name)


def clear_all_vectors() -> bool:
    return get_store().clear_all_vectors()
