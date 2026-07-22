# 🏗️ RAG Architecture — Document Intelligence Platform

### Assignment 3 · Week 2 — Visibility Bots Innovation Lab

**Author:** Rana Muhammad Haseeb Khan · **Track 2: NLP & AI Agents**

This document specifies the complete 10-stage retrieval-augmented generation pipeline as
**actually implemented** in this repository — every stage maps to real code.

---

## 1. The 10-Stage Pipeline

```text
+----------------------------------------------------------+
|                         1. USER                          |
|             asks a natural-language question             |
+-----------------------------+----------------------------+
                              |   question (text)
                              v
+----------------------------------------------------------+
|                       2. FRONTEND                        |
|     Streamlit UI - pages/2_Document_Intelligence.py      |
+-----------------------------+----------------------------+
                              |   upload / query event
                              v
+----------------------------------------------------------+
|                        3. BACKEND                        |
|            Python orchestration layer - src/             |
+-----------------------------+----------------------------+
                              |   raw file bytes
                              v
+----------------------------------------------------------+
|                  4. DOCUMENT PROCESSING                  |
|      document_processor.extract_text_and_metadata()      |
+-----------------------------+----------------------------+
                              |   [{text, source, page}]
                              v
+----------------------------------------------------------+
|                       5. CHUNKING                        |
|     document_processor.chunk_documents()   900 / 120     |
+-----------------------------+----------------------------+
                              |   LangChain Document[]
                              v
+----------------------------------------------------------+
|                 6. EMBEDDING GENERATION                  |
|         HuggingFaceEmbeddings - all-MiniLM-L6-v2         |
+-----------------------------+----------------------------+
                              |   float[384] per chunk
                              v
+----------------------------------------------------------+
|                    7. VECTOR DATABASE                    |
|        ChromaDB PersistentClient - cosine / HNSW         |
+-----------------------------+----------------------------+
                              |   id + vector + metadata
                              v
+----------------------------------------------------------+
|                       8. RETRIEVER                       |
|     vector_store.search_similar_chunks()   top-k = 6     |
+-----------------------------+----------------------------+
                              |   top-k chunks + scores
                              v
+----------------------------------------------------------+
|                          9. LLM                          |
|           rag_pipeline.generate_rag_response()           |
+-----------------------------+----------------------------+
                              |   grounded answer text
                              v
+----------------------------------------------------------+
|                       10. RESPONSE                       |
|       answer + [Source N] citations rendered in UI       |
+----------------------------------------------------------+
```

### Execution reality: one pipeline, two timelines

The ten stages form a single logical flow, but they **do not all run on every request**.
Stages 4–7 run **once per document** (ingestion); stages 8–10 run **once per question** (query).
Stage 7 is the boundary where the two meet.

```text
   INGESTION (offline)                        QUERY (online)
   1 -> 2 -> 3 -> 4 -> 5 -> 6 -> [ 7 ] <- 8 <- 3 <- 2 <- 1
        upload path                 |         question path
                                    +---> 8 -> 9 -> 10
```

Separating them is what makes the system fast: embedding is expensive and happens once; querying
touches only an index lookup and one LLM call.

---

## 2. Data Transformation

The clearest way to understand the pipeline is to follow the **shape of the data**:

| Stage | Input | Output |
| :--- | :--- | :--- |
| 1 User | intent | question string |
| 2 Frontend | file / question | `UploadedFile`, session event |
| 3 Backend | UI event | orchestrated function call |
| 4 Doc Processing | raw bytes | `[{"text", "metadata":{source,page}}]` |
| 5 Chunking | page records | `Document[]` (~900 chars, +`chunk` index) |
| 6 Embedding | chunk text | `float[384]` unit vector |
| 7 Vector DB | id + vector + text + metadata | persisted, indexed |
| 8 Retriever | query vector | top-k `{text, metadata, score}` |
| 9 LLM | system + context + question | grounded answer with `[Source N]` |
| 10 Response | answer + citations | rendered markdown + source cards |

---

## 3. Component Specifications

### 1 · User
The human with an information need. Two interaction modes: **contributing** knowledge (uploading
documents) and **consuming** it (asking questions). The system never assumes the user knows which
document holds the answer — that is the retriever's job.

### 2 · Frontend — `pages/2_📄_Document_Intelligence.py`
Streamlit UI. Handles authentication (simulated sessions), multi-format upload, the document
library, retrieval controls (`k`, scope, hybrid toggle), the chat interface, and rendering.

Two design commitments make the system trustworthy rather than a black box:
- **Transparent execution** — an expander shows the *exact* retrieved chunks with source, page,
  chunk index, and similarity score **before** the answer.
- **Page-isolated state** — `st.session_state.rag_*` keeps this page's chat and sessions separate
  from the Week 1 workspace.

### 3 · Backend — `src/`
The orchestration layer, deliberately **decoupled from Streamlit**. No module in `src/` imports
`streamlit`, so the same pipeline could be driven by a FastAPI service, a CLI, or the experiment
harness — which is precisely how [EXPERIMENTS.md](EXPERIMENTS.md) tested it. Its job is sequencing:
parse → chunk → embed → store, and retrieve → construct → generate.

### 4 · Document Processing — `document_processor.extract_text_and_metadata()`
Converts bytes into normalized text records.

| Format | Parser | Page semantics |
| :--- | :--- | :--- |
| PDF | `pypdf` | one record per real page |
| DOCX | `python-docx` (incl. tables) | synthetic pages, 40 paragraphs each |
| TXT / MD | native decode | single record |

Encoding is attempted `utf-8-sig → utf-8 → utf-16 → latin-1`, then a lossy fallback, so decoding
**never raises**. Whitespace is stripped and empty pages dropped. A corrupt or image-only PDF
returns `[]` with a logged reason rather than crashing the upload.

**Why metadata is captured here:** `source` and `page` are attached at extraction. Provenance not
recorded at this stage is unrecoverable later — citations, per-document filtering, and per-document
deletion all depend on it.

### 5 · Chunking — `document_processor.chunk_documents()`
`RecursiveCharacterTextSplitter` splits on a descending separator hierarchy
(`paragraph → line → sentence → word → character`), so it breaks at the most natural boundary
available. Defaults: **900 chars / 120 overlap**, with a `chunk` index added to metadata.

**These values are measured, not guessed.** At 300 chars a five-item list fragmented so badly the
final answer contained **1 of 5** items; at 1000 it contained **5 of 5**
([EXPERIMENTS.md §2](EXPERIMENTS.md)). Chunk size is the highest-leverage parameter in the system.

### 6 · Embedding Generation — `vector_store.py`
`all-MiniLM-L6-v2` via `HuggingFaceEmbeddings` maps each chunk to a **384-dimensional unit vector**.
Runs **locally** — no API cost, no data leaving the machine.

Two deliberate choices:
- **Normalized vectors** — with unit length, cosine similarity reduces to a dot product: faster and
  numerically stable.
- **Lazy loading** — the model (~88 MB) is downloaded and loaded on *first embed*, not at import,
  so app startup stays fast.

⚠️ **Invariant:** ingestion and query **must** use the same model. Vectors from different models are
geometrically incompatible and degrade retrieval *silently, without error*. Changing models requires
a full re-index — which is why **"♻️ Refresh embeddings"** is a first-class product feature.

### 7 · Vector Database — ChromaDB
`PersistentClient` writing to `.chroma_db/`, one collection with **cosine** space and an **HNSW**
index (logarithmic-time approximate nearest-neighbour search).

Each record stores `id + vector + document text + metadata`. IDs are deterministic —
`source::page::chunk::md5(text)[:8]` — so re-indexing the same file **upserts in place** instead of
creating duplicates. Metadata is sanitized to Chroma-safe primitives before write.

**Why Chroma over FAISS:** this workload is document *management* — filter by source, delete a
document, list the library. Those are database operations. FAISS is a search library and would have
required hand-building metadata storage, persistence, and deletion around it.

### 8 · Retriever — `vector_store.search_similar_chunks()` / `hybrid_search()`
Embeds the query with the *same* model, then returns the top-k most similar chunks with scores
converted to similarity (`1 − cosine_distance`).

Three capabilities:
- **Semantic search** — meaning-based matching (default, `k=6`).
- **Hybrid search** — fuses semantic and keyword rankings via **Reciprocal Rank Fusion**
  (`Σ 1/(60+rank)`), recovering exact identifiers that embeddings miss.
- **Metadata filtering** — restricts search to one document; in a multi-tenant deployment this same
  mechanism is the access-control boundary.

**Key design rule (measured):** retrieval embeds the **raw user question**. Prompt templates are
applied later, at stage 9 — templating the query diluted the embedding and cut top-1 similarity by
up to **13%** ([EXPERIMENTS.md §4](EXPERIMENTS.md)).

### 9 · LLM — `rag_pipeline.generate_rag_response()`
Assembles the prompt and calls the model. Providers (OpenRouter · OpenAI · Google Gemini) are all
reached through the OpenAI-compatible SDK, so one code path serves all three.

Prompt structure:
```text
SYSTEM  persona (optional) + strict grounding rules + exact fallback sentence
USER    CONTEXT: [Source 1] (document, page, chunk) <text> …
        QUESTION: <raw user question>
```

Grounding is enforced in layers: answer only from context; a precise refusal sentence; inline
`[Source N]` citations; and a **short-circuit** — if retrieval returns nothing, the fallback is
returned *without* an LLM call, making hallucination structurally impossible in that path.
Temperature defaults to **0.2**. Empty-response and 401/403/404/429/timeout errors are mapped to
actionable user messages.

### 10 · Response
The answer is parsed for `[Source N]` markers to flag which sources were actually cited, then
rendered with three artifacts: the **answer**, a **📎 Sources card** (document · page · chunk ·
snippet), and **telemetry** (latency, model, retrieval mode). Chunks retrieved *and* citations are
persisted on the message, so re-renders never recompute.

---

## 4. Cross-Cutting Concerns

| Concern | Implementation |
| :--- | :--- |
| **Failure isolation** | Every stage returns a safe empty value and logs; one bad page never fails a batch |
| **Idempotency** | Content-hashed IDs make re-indexing an upsert |
| **Observability** | Structured logging per module; retrieved context surfaced in the UI |
| **Secrets** | Keys from env/session only, never persisted; `.env` git-ignored |
| **Cost control** | Local embeddings (free); LLM called once per question; token/cost dashboard |
| **Testability** | `src/` is Streamlit-free; embeddings and LLM client are injectable |

## 5. Known Limits & Scaling Path

Single-node Chroma on local disk suits thousands of documents. Beyond that: move to a distributed
store (Qdrant/Milvus), shard by tenant, quantize vectors (~4× memory reduction), run ingestion as an
async worker queue rather than inline with upload, and add a **cross-encoder re-ranker** between
stages 8 and 9 — the highest-value next addition, since measurement showed *ranking* quality, not
recall, drove final answer quality.

---

*Architecture documented by Rana Muhammad Haseeb Khan · Visibility Bots Fellowship — 2026.*
