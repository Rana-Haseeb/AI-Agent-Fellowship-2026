# 📄 Designing Enterprise Retrieval-Augmented Generation Systems

### Assignment 2 · Week 2 — Visibility Bots Innovation Lab

**Author:** Rana Muhammad Haseeb Khan · **Track 2: NLP & AI Agents** · **Date:** July 2026

> Findings marked **📊 measured** come from experiments I ran against a real document through the
> system I built. Full data: [EXPERIMENTS.md](EXPERIMENTS.md).

---

## 1. Why RAG Exists

A Large Language Model is a **frozen, closed book**. Its weights encode a snapshot of public text
taken at training time, which creates four hard limits for enterprise use:

| Limitation | Consequence |
| :--- | :--- |
| **Training cut-off** | Cannot know anything published after training |
| **No private knowledge** | Has never seen your contracts, policies, or tickets |
| **Hallucination** | Fluently invents plausible-sounding facts when uncertain |
| **No provenance** | Cannot show *where* an answer came from — fatal for audit and compliance |

### Why not fine-tuning?

Fine-tuning adjusts weights to change *behaviour and style*; it is a poor mechanism for injecting
*facts*.

| Dimension | Fine-tuning | RAG |
| :--- | :--- | :--- |
| Update a fact | Retrain the model | Re-index one document (seconds) |
| Cost | GPU hours per update | Embedding cost only |
| Provenance | None — facts dissolve into weights | Exact document + page cited |
| Access control | Baked in for everyone | Enforced per-query via metadata filters |
| Forgetting a fact | Very hard | Delete the vectors |

**RAG separates knowledge from reasoning.** The model supplies language competence; the vector store
supplies current, private, permissioned facts. This is why nearly every enterprise AI product is a
retrieval system with an LLM attached, not a fine-tuned model.

---

## 2. Enterprise Architecture

A production RAG system is **two pipelines**, not one. They run on different schedules and have
different cost profiles — conflating them is a common design error.

```text
INGESTION PATH   (offline - once per document)

+--------------+    +--------------+    +--------------+    +--------------+    +--------------+
|  Documents   |    |   Parse &    |    |    Chunk     |    |    Embed     |    |  Vector DB   |
|   PDF DOCX   | -> |   Extract    | -> |  900 chars   | -> |    MiniLM    | -> |   ChromaDB   |
|   TXT  MD    |    |  clean text  |    | 120 overlap  |    |   384-dim    |    | cosine HNSW  |
+--------------+    +--------------+    +--------------+    +--------------+    +--------------+


QUERY PATH   (online - per question)

+------------+    +------------+    +------------+    +------------+    +------------+    +------------+
|    User    |    |   Embed    |    |  Retrieve  |    |   Prompt   |    |    LLM     |    |   Answer   |
|  Question  | -> |   query    | -> | top-k = 6  | -> | + context  | -> |  generate  | -> |+ citations |
|            |    |  384-dim   |    | + metadata |    |+ grounding |    |            |    |            |
+------------+    +------------+    +------------+    +------------+    +------------+    +------------+
```

**Critical property: both paths must use the *same* embedding model.** Vectors from different models
occupy different semantic spaces; mixing them silently destroys retrieval quality without raising an
error. Changing models therefore requires a full re-index — which is why a *"refresh embeddings"*
operation belongs in the product, not just the codebase.

---

## 3. Document Processing & Chunking

Chunking is **the single highest-leverage decision** in a RAG system, and the most commonly
underestimated.

Documents are split because embeddings compress an entire passage into one fixed-length vector.
Embed a whole 50-page report and you get one blurry "average" of everything — useless for precise
retrieval. Chunks must be small enough to be topically coherent, yet large enough to contain a
complete thought.

### 📊 Measured: chunk size determines whether the answer is complete

Same document, same question ("list the 5 key elements"), only chunk size varied:

| Chunk size | Chunks | Retrieval recall | **Elements in the final answer** |
| ---: | ---: | ---: | :--- |
| 300 | 27 | 0.867 | **1 of 5** ❌ |
| 500 | 14 | 0.933 | **3 of 5** ⚠️ |
| 1000 | 7 | **1.000** | **5 of 5** ✅ |

A five-item list spanning ~900 characters was **split across chunks** at small sizes. With `k=5`,
only some fragments were retrieved — so the model answered confidently and fluently with **one of
five** elements. It did not hallucinate; it simply never received the rest.

**This is the defining risk of RAG: silent incompleteness.** A wrong answer is obvious; a
*partial* answer looks perfect.

**Overlap** exists to repair a different problem — a sentence cut in half at a chunk boundary. 📊
Measured: raising overlap 0 → 200 improved top-1 similarity **+8.3%** but left recall unchanged and
grew the index **+43%**. Overlap fixes *boundaries*, not fragmentation. A 10–20% overlap is a sound
default.

**Metadata** attached at chunk time (`source`, `page`, `chunk`) is what later makes citations,
per-document filtering, and per-document deletion possible. Metadata that isn't captured during
ingestion cannot be recovered at query time.

---

## 4. Embeddings

An embedding maps text to a vector such that **semantic similarity becomes geometric proximity**.
"Interest-free loans" and "microcredit without interest" land near each other despite sharing no
keywords — this is what makes RAG better than keyword search.

Similarity is measured with **cosine similarity** — the angle between vectors, ignoring magnitude:

```
cos(A,B) = (A · B) / (||A|| × ||B||)      range: -1 … 1, where 1 = identical direction
```

Magnitude reflects text length, which is irrelevant to meaning — so angle, not distance, is the right
measure. When vectors are **normalized** to unit length (as in this system), cosine similarity
reduces to a plain dot product, which is why normalization is both a quality and a speed decision.

### 📊 Measured: better ranking beats better recall

| Model | Dim | Disk | Retrieval recall | Top-1 similarity | **Answer coverage** | Index time |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `all-MiniLM-L6-v2` | 384 | 88 MB | **0.933** | 0.602 | 0.80 | **0.41 s** |
| `bge-small-en-v1.5` | 384 | 129 MB | 0.911 | **0.763** | **0.90** ✅ | 0.70 s |

BGE scored *lower* keyword recall yet produced *better answers*. Recall only asks "was the fact
somewhere in the top-5?"; **ranking** determines whether the right passage sits first, where the
model weights it most. **A retrieval proxy metric can point the opposite way from real user
outcomes** — an argument for always evaluating end-to-end.

---

## 5. Vector Databases

A vector database stores embeddings with their metadata and answers nearest-neighbour queries fast.
Exhaustive comparison against millions of vectors is too slow, so these systems use **Approximate
Nearest Neighbour (ANN)** indexes — most commonly **HNSW** (Hierarchical Navigable Small World), a
layered proximity graph that reaches the right neighbourhood in roughly logarithmic hops, trading a
little exactness for orders-of-magnitude speed.

| | **ChromaDB** | **FAISS** |
| :--- | :--- | :--- |
| Type | Full database | Similarity-search library |
| Metadata + filtering | ✅ Built in | ❌ Manual side-store |
| Persistence | ✅ Automatic | Manual save/load |
| CRUD / delete by filter | ✅ | Rebuild index |
| Raw speed at scale | Good | Excellent (GPU-capable) |

**I chose ChromaDB.** The workload is document management, not billion-scale search: users upload,
query, filter by document, and delete. Those are *database* operations. FAISS would have meant
hand-building a metadata store, a persistence layer, and deletion semantics around it — reimplementing
a database to gain speed the corpus size doesn't need. At 10M+ vectors, FAISS or a distributed store
(Qdrant, Milvus) becomes the right call.

Core concepts: a **collection** groups vectors under one embedding space; **indexing** builds the ANN
graph; **search** returns the top-k with distances; **retrieval** returns the original text plus
metadata — the vector is only the address, never the payload.

---

## 6. Retrieval

Retrieval is a **funnel**, and `k` sets its width. Too small and multi-part answers arrive truncated
(§3). Too large and the prompt fills with noise, raising cost and diluting attention.

Three strategies, all implemented in this system:

- **Semantic search** — meaning-based; handles paraphrase, fails on rare exact tokens (an invoice
  number embeds meaninglessly).
- **Hybrid search** — fuses semantic ranking with keyword matching via **Reciprocal Rank Fusion**,
  `score = Σ 1/(60 + rank_i)`. RRF combines rankings without needing to normalize incompatible score
  scales, and recovers exact identifiers that pure embeddings miss.
- **Metadata filtering** — restricts search to a document, department, or date. In enterprise settings
  this is also the **access-control layer**: a filter on `user_permissions` is what stops retrieval
  leaking documents across tenants.

### 📊 Measured: query formulation changes what is retrieved

Wrapping the user's question in an instructional template ("List every key fact about…") **lowered
top-1 similarity by up to 13%** — the boilerplate dominates the embedding and pulls it off-topic.
Yet the same templates **improved the generated answer** (coverage 0.40 → 0.60) by instructing the
model to be exhaustive.

**The two effects oppose each other**, which yields a concrete architectural rule:

> **Embed the raw question for retrieval; apply templates only when constructing the LLM prompt.**

This system implements exactly that split.

---

## 7. Prompt Construction

The prompt is where retrieved evidence becomes an answer, and where grounding is enforced. The
structure used here:

```text
SYSTEM   persona (optional)  +  strict grounding rules
         "Answer ONLY from the context. If absent, reply exactly:
          'I cannot find the answer in the provided documents.'
          Cite sources inline as [Source N]. Never invent facts."

USER     CONTEXT:
           [Source 1] (document: policy.pdf, page: 3, chunk: 2)
           <retrieved text>
           [Source 2] (document: policy.pdf, page: 5, chunk: 0)
           <retrieved text>
         QUESTION: <the user's raw question>
```

Four deliberate choices:

1. **Labelled context blocks.** Each chunk carries a `[Source N]` tag with document, page, and chunk.
   The model can only cite labels that exist, making fabricated citations structurally difficult.
2. **An exact fallback string.** A precise sentence — not "say you don't know" — is machine-checkable,
   so the application can detect refusal and suppress the citation panel.
3. **Persona kept subordinate.** A user-supplied persona sets tone, but the grounding rules are
   re-asserted after it so persona instructions cannot override factual constraints.
4. **Low temperature (0.0–0.2).** Grounded extraction is not a creative task.

---

## 8. Hallucination Reduction

Hallucination is not a bug to patch but a **property to constrain**. Defence in depth:

| Layer | Mechanism | Effect |
| :--- | :--- | :--- |
| **1. Restrict** | "Answer ONLY from context" | Removes reliance on parametric memory |
| **2. Escape hatch** | Exact fallback sentence | Gives the model a correct way to say *no* |
| **3. Attribute** | `[Source N]` inline citations | Makes each claim traceable |
| **4. Short-circuit** | Zero retrieved chunks → fallback, no LLM call | Cannot hallucinate without being asked |
| **5. Reveal** | Retrieved chunks shown in the UI | User can verify the evidence directly |
| **6. Constrain** | `temperature = 0` | Removes sampling randomness |

Providing an explicit, *acceptable* way to fail is the highest-value item. A model with no
sanctioned refusal will fabricate, because producing text is its only available action.

**📊 Measured:** an out-of-document control question ("What is the capital of France?") was correctly
refused with the exact fallback string in **3 of 3** configurations — grounding held regardless of
chunk size.

But note §3: **grounding prevents fabrication, not incompleteness.** The model that returned 1 of 5
elements was perfectly grounded and perfectly cited — and still unhelpful. Retrieval quality is not
optional insurance; it is the ceiling on answer quality.

**Evaluation** must therefore measure both: *retrieval recall* (did we find it?) and *answer
coverage* (did the user receive it?). The gap between them is where these systems fail silently.

---

## 9. Future Improvements

1. **Re-ranking.** Retrieve k=20 with the fast bi-encoder, then re-score with a cross-encoder that
   reads query and passage *together*. Directly targets the ranking weakness §4 exposed.
2. **Query transformation.** Rewrite conversational follow-ups ("what about the second one?") into
   standalone queries, and use HyDE — embed a *hypothetical answer* rather than the question, since
   answers sit closer to answer-shaped passages.
3. **Semantic / hierarchical chunking.** Split on document structure (headings, list boundaries)
   rather than character counts. §3's failure was a five-item list severed mid-list — a
   structure-aware splitter would have kept it intact.
4. **Scaling to millions of documents.** Move to a distributed store (Qdrant/Milvus), shard by
   tenant, quantize vectors (PQ/int8) to cut memory ~4×, cache frequent queries, and run ingestion
   as an async worker queue rather than inline with the upload.
5. **Continuous evaluation.** A regression suite of question/ground-truth pairs run on every config
   change — turning the ad-hoc harness in [EXPERIMENTS.md](EXPERIMENTS.md) into CI.
6. **Agentic RAG.** Let the model decide *whether* and *how many times* to retrieve, decomposing
   multi-hop questions into sub-queries — the natural bridge from Week 2 into agent architectures.

---

## 10. References

1. Lewis, P., et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* arXiv:2005.11401.
2. Karpukhin, V., et al. (2020). *Dense Passage Retrieval for Open-Domain Question Answering.* arXiv:2004.04906.
3. Malkov, Y. & Yashunin, D. (2018). *Efficient and Robust Approximate Nearest Neighbor Search using HNSW Graphs.* arXiv:1603.09320.
4. Reimers, N. & Gurevych, I. (2019). *Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks.* arXiv:1908.10084.
5. Cormack, G., et al. (2009). *Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods.* SIGIR.
6. Gao, L., et al. (2022). *Precise Zero-Shot Dense Retrieval without Relevance Labels (HyDE).* arXiv:2212.10496.
7. Es, S., et al. (2023). *RAGAS: Automated Evaluation of Retrieval Augmented Generation.* arXiv:2309.15217.
8. Khan, R. M. H. (2026). *RAG Experiments — Measured Findings.* [EXPERIMENTS.md](EXPERIMENTS.md).

---

*Researched and measured by Rana Muhammad Haseeb Khan · Visibility Bots Fellowship — 2026.*
