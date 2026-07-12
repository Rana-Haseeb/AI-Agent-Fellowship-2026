"""
Document processing for the Document Intelligence RAG pipeline.

Responsibilities:
    1. extract_text_and_metadata(uploaded_file)
       Safely read PDF / TXT / MD files into a normalized list of
       {"text": str, "metadata": {"source": ..., "page": ...}} records.
    2. chunk_documents(extracted_docs, chunk_size, chunk_overlap)
       Split those records into LangChain `Document` chunks (with metadata
       preserved) using a RecursiveCharacterTextSplitter.

PDFs are parsed with `pypdf`; plain-text formats use native decoding with
graceful fallback. All failures are logged and degrade gracefully (a bad page
or file never crashes the pipeline — it is skipped with a warning).
"""

from __future__ import annotations

import io
import logging
import os
from typing import Any, Dict, List

from pypdf import PdfReader

# LangChain has moved these classes between packages across versions.
# Import defensively so the module works on both new and old installs.
try:  # LangChain >= 0.2 split packages
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:  # pragma: no cover - older monolithic langchain
    from langchain.text_splitter import RecursiveCharacterTextSplitter

try:
    from langchain_core.documents import Document
except ImportError:  # pragma: no cover
    from langchain.schema import Document


# --------------------------------------------------------------------------- #
#  Logging
# --------------------------------------------------------------------------- #
logger = logging.getLogger(__name__)
if not logging.getLogger().handlers and not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


# --------------------------------------------------------------------------- #
#  Internal helpers
# --------------------------------------------------------------------------- #
def _get_filename(uploaded_file: Any) -> str:
    """Best-effort filename from a Streamlit UploadedFile or file-like object."""
    return getattr(uploaded_file, "name", None) or "uploaded_file"


def _read_bytes(uploaded_file: Any) -> bytes:
    """Read raw bytes from a Streamlit UploadedFile or any file-like object,
    without permanently consuming the stream position."""
    if hasattr(uploaded_file, "getvalue"):
        data = uploaded_file.getvalue()
    elif hasattr(uploaded_file, "read"):
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        data = uploaded_file.read()
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
    else:
        raise TypeError("uploaded_file must be a file-like object exposing read()/getvalue().")

    return data.encode("utf-8", errors="replace") if isinstance(data, str) else data


def _decode_text(raw: bytes) -> str:
    """Decode raw bytes to text, trying common encodings before falling back
    to a lossy UTF-8 decode so decoding never raises."""
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    logger.warning("Falling back to lossy UTF-8 decode; some characters may be replaced.")
    return raw.decode("utf-8", errors="replace")


def _extract_pdf(raw: bytes, filename: str) -> List[Dict[str, Any]]:
    """Extract text page-by-page from a PDF. Returns one record per non-empty page."""
    records: List[Dict[str, Any]] = []
    try:
        reader = PdfReader(io.BytesIO(raw))
    except Exception as exc:
        logger.error("Failed to open PDF '%s': %s", filename, exc)
        return records

    num_pages = len(reader.pages)
    logger.info("Parsing PDF '%s' (%d page(s)).", filename, num_pages)

    for page_num, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            logger.warning("Could not extract page %d of '%s': %s", page_num, filename, exc)
            continue

        text = text.strip()
        if not text:
            logger.debug("Page %d of '%s' is empty; skipping.", page_num, filename)
            continue

        records.append({"text": text, "metadata": {"source": filename, "page": page_num}})

    if not records:
        logger.warning("No extractable text found in '%s' (scanned/image-only PDF?).", filename)
    return records


def _extract_plaintext(raw: bytes, filename: str) -> List[Dict[str, Any]]:
    """Extract text from a .txt or .md file as a single record."""
    text = _decode_text(raw).strip()
    if not text:
        logger.warning("File '%s' contains no readable text.", filename)
        return []
    return [{"text": text, "metadata": {"source": filename, "page": 1}}]


# --------------------------------------------------------------------------- #
#  Public interface
# --------------------------------------------------------------------------- #
def extract_text_and_metadata(uploaded_file: Any) -> List[Dict[str, Any]]:
    """
    Read a PDF / TXT / MD file into a normalized list of text+metadata records.

    Parameters
    ----------
    uploaded_file : Streamlit UploadedFile or any file-like object
        Must expose a ``name`` attribute and ``read()`` / ``getvalue()``.

    Returns
    -------
    list[dict]
        One record per page (PDF) or per file (TXT/MD), each shaped as::

            {"text": "<stripped text>",
             "metadata": {"source": "<filename>", "page": <int>}}

        Returns an empty list (never raises) if the file type is unsupported,
        unreadable, or contains no extractable text.
    """
    filename = _get_filename(uploaded_file)
    ext = os.path.splitext(filename)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        logger.error(
            "Unsupported file type '%s' for '%s'. Supported: %s",
            ext or "<none>", filename, ", ".join(sorted(SUPPORTED_EXTENSIONS)),
        )
        return []

    try:
        raw = _read_bytes(uploaded_file)
    except Exception as exc:
        logger.error("Could not read bytes from '%s': %s", filename, exc)
        return []

    if not raw:
        logger.warning("File '%s' is empty.", filename)
        return []

    if ext == ".pdf":
        return _extract_pdf(raw, filename)
    return _extract_plaintext(raw, filename)


def chunk_documents(
    extracted_docs: List[Dict[str, Any]],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> List[Document]:
    """
    Split extracted text records into overlapping LangChain ``Document`` chunks.

    Uses ``RecursiveCharacterTextSplitter`` (paragraph → line → sentence → word
    → character), preserving each source's structural metadata and adding a
    ``chunk`` index so retrieved passages can be traced back to their origin.

    Parameters
    ----------
    extracted_docs : list[dict]
        Output of :func:`extract_text_and_metadata`.
    chunk_size : int, default 500
        Target maximum characters per chunk.
    chunk_overlap : int, default 50
        Characters shared between consecutive chunks (preserves context).

    Returns
    -------
    list[langchain_core.documents.Document]
        Chunks with ``page_content`` and ``metadata`` = source metadata +
        ``{"chunk": <int>}``. Returns an empty list if there is nothing to split.
    """
    if not extracted_docs:
        logger.warning("chunk_documents received no documents to split.")
        return []

    if chunk_overlap >= chunk_size:
        logger.warning(
            "chunk_overlap (%d) >= chunk_size (%d); clamping overlap to %d.",
            chunk_overlap, chunk_size, chunk_size // 4,
        )
        chunk_overlap = chunk_size // 4

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: List[Document] = []
    for record in extracted_docs:
        text = (record.get("text") or "").strip()
        base_metadata = dict(record.get("metadata", {}))
        if not text:
            continue

        try:
            pieces = splitter.split_text(text)
        except Exception as exc:
            logger.error(
                "Failed to split text from '%s': %s",
                base_metadata.get("source", "<unknown>"), exc,
            )
            continue

        for chunk_index, piece in enumerate(pieces):
            piece = piece.strip()
            if not piece:
                continue
            metadata = {**base_metadata, "chunk": chunk_index}
            chunks.append(Document(page_content=piece, metadata=metadata))

    logger.info(
        "Chunked %d source record(s) into %d chunk(s) (size=%d, overlap=%d).",
        len(extracted_docs), len(chunks), chunk_size, chunk_overlap,
    )
    return chunks
