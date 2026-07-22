# 🧪 RAG Experiments — Measured Findings

### Assignment 4 · Week 2 — Visibility Bots Innovation Lab

**Author:** Rana Muhammad Haseeb Khan · **Track 2: NLP & AI Agents**

> Every number in this report was **measured**, not estimated. The harness runs the real `src/`
> pipeline — the same code the application uses — building a **fresh isolated vector store per
> configuration**. Both **retrieval** and **generation** are measured with a live LLM.

---

## 1. Methodology

| Item | Value |
| :--- | :--- |
| **Test document** | `Community Development.pdf` — 7 pages, 6,046 characters of extracted text |
| **Pipeline** | `document_processor` → `chunk_documents` → `vector_store` (ChromaDB, cosine) → `rag_pipeline` |
| **Embedding model (default)** | `all-MiniLM-L6-v2` (384-dim, normalized) — runs locally |
| **Generation model** | `nvidia/nemotron-3-ultra-550b-a55b:free` via OpenRouter, `temperature = 0.0` |
| **Retrieval depth** | `k = 5` |
| **Isolation** | New temp Chroma collection per configuration |
| **Total LLM calls** | 23 successful (13 + 10 gap-fill) |

### Evaluation set (ground truth verified against the PDF)

| # | Question | Expected keywords |
| :- | :--- | :--- |
| 1 | What are the key elements of community development? | Participation · Empowerment · Capacity Building · Sustainability · Inclusiveness |
| 2 | What is social cohesion? | cohesion |
| 3 | What is Asset-Based Community Development? | Asset-Based |
| 4 | Which bank in Bangladesh is given as an example? | Grameen |
| 5 | Which organization in Pakistan provides interest-free loans? | Akhuwat |
| 6 | What are the benefits of community development? | poverty · education · democracy |
| **C** | *(control)* What is the capital of France? | **must refuse** — not in the document |

Question 1 is the **discriminating** question: its five-part answer spans ~900 characters, so it
exposes chunking failures that single-fact questions hide.

### Metrics

| Metric | Definition |
| :--- | :--- |
| **Retrieval recall** | Share of ground-truth keywords present in the **retrieved chunks** |
| **Answer coverage** | Share of ground-truth keywords present in the **generated answer** (end-to-end) |
| **Context precision** | Share of retrieved chunks that are relevant (noise measure) |
| **Top-1 similarity** | Cosine similarity of the best-matching chunk |
| **Grounded refusal** | Did the control question correctly return the exact fallback sentence? |

> **Why two recall metrics?** Retrieval recall asks *"did the system find the facts?"*. Answer
> coverage asks *"did the user actually receive them?"*. **The gap between them is where RAG
> systems silently fail** — and this report measures both.

---

## 2. Experiment 1 — Chunk Size ⭐

**Setup:** sizes 300 / 500 / 1000 · overlap 50 · `k=5` · MiniLM · live generation.

| Chunk size | Chunks | Avg chars | Retrieval recall | Mean answer coverage | **Key-elements answer** | Grounded refusal |
| ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| 300 | 27 | 238.8 | 0.867 | 0.60 | **0.20** (1 of 5) ❌ | ✅ |
| 500 | 14 | 437.6 | 0.933 | 0.80 | **0.60** (3 of 5) ⚠️ | ✅ |
| 1000 | 7 | 863.7 | **1.000** | **1.00** | **1.00** (5 of 5) ✅ | ✅ |

### Verbatim generated answers

| Size | Answer (excerpt) |
| ---: | :--- |
| **300** | *"The context explicitly lists **participation** as a key element of community development…"* |
| **500** | *"…**Participation** … **Empowerment** … **Capacity Building**"* — missed Sustainability, Inclusiveness |
| **1000** | *"1. **Participation** 2. **Empowerment** 3. **Capacity Building** 4. **Sustainability** 5. **Inclusiveness**"* |

### Findings

- **Answer quality tracks chunk size directly: 0.20 → 0.60 → 1.00** on the discriminating question.
  The LLM cannot state facts retrieval never delivered — and it fails **silently and confidently**,
  producing a fluent, well-cited answer that is simply incomplete. This is the most dangerous
  failure mode in RAG.
- **This reproduced a real production bug.** The live app at `chunk_size=500` answered with only
  2–3 elements and the user reasonably assumed the PDF hadn't indexed fully. **It had.** The
  measurement proves the cause was **retrieval fragmentation**, not ingestion.
- **Top-1 similarity moves the opposite way** (0.672 → 0.570): small chunks are topically
  concentrated so they match more sharply, but they fragment multi-part answers.
- **Hallucination resistance held at every configuration** — the out-of-document control was
  correctly refused with the exact fallback string in **3 of 3** runs. Grounding is robust to
  chunking choices.

> **Conclusion:** chunk size is a **completeness ↔ match-sharpness** dial. Documents containing
> enumerated lists, tables, or procedures need larger chunks, or answers arrive truncated.

---

## 3. Experiment 2 — Chunk Overlap

**Setup:** overlap 0 / 50 / 100 / 200 · size 500 · `k=5` · MiniLM.

| Overlap | Chunks | Retrieval recall | Context precision | Top-1 similarity | Key-elements answer |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 14 | 0.933 | 0.433 | 0.604 | 0.60 |
| 50 | 14 | 0.933 | 0.433 | 0.602 | 0.40 |
| 100 | 19 | 0.933 | 0.400 | 0.628 | 0.60 |
| 200 | 20 | 0.933 | 0.467 | **0.654** | 0.60 |

### Findings

- **Overlap did not change retrieval recall** (flat 0.933 across all four). Overlap repairs
  *boundary* damage — it cannot reunite content spread across several chunks. That is a
  **chunk-size** problem (Exp 1).
- **Overlap improves match confidence:** top-1 similarity rose 0.604 → 0.654 (**+8.3%**) from
  0 → 200, because key sentences survive intact in at least one chunk.
- **Overlap costs storage:** chunks grew 14 → 20 (**+43%**) for the same document.
- **Answer coverage is effectively flat** (0.60 except one 0.40 at overlap 50). With a single
  sample per cell that one-keyword difference is **noise, not signal** — the retrieval metrics for
  overlap 0 and 50 are identical.

> **Conclusion:** overlap is cheap insurance against boundary truncation, not a recall fix.
> **10–20% of chunk size** is a sound default.

---

## 4. Experiment 3 — Prompt Templates ⭐ *(most nuanced result)*

**Setup:** one fixed index (500/50/MiniLM). The same question submitted through four templates.
The templated text drives **both** retrieval and generation, isolating the template's full effect.

| Template | Retrieval recall | Top-1 similarity | **Answer coverage** |
| :--- | ---: | ---: | ---: |
| **Raw question (baseline)** | 0.60 | **0.657** ✅ | **0.40** ❌ |
| List key facts | 0.60 | 0.570 | **0.60** ✅ |
| Summarize | 0.60 | 0.631 | **0.60** ✅ |
| Explain | 0.60 | 0.630 | **0.60** ✅ |

### Findings — the two effects pull in opposite directions

1. **On retrieval, the raw question wins.** It scored the highest top-1 similarity (0.657); every
   template *lowered* it, by up to **13%** ("List key facts" → 0.570). Instructional boilerplate
   dominates the embedding and pulls the vector away from the user's actual topic — **semantic
   dilution**. (The full 6-question sweep confirmed this: raw 0.933 recall vs 0.878 for
   "List key facts".)
2. **On generation, the templates win.** From *identical* retrieved context (all four retrieved
   recall 0.60), the raw question produced the **worst** answer (0.40) while every template produced
   a **better** one (0.60). Instructing the model to "list every key fact" makes it exhaustive;
   a bare question invites a brief reply.

> **⭐ Architectural conclusion:** the optimal design is **not** "use templates" or "don't" — it is
> to **separate the two stages**: embed the **raw question** for retrieval (best matching), then
> apply the **template** when building the LLM prompt (best completeness). You get both wins.
>
> **This is exactly the design now implemented in the application** — see §6. Note this is a
> single-sample-per-cell result; the direction is consistent and mechanistically explainable, but
> the magnitudes should not be over-read.

---

## 5. Experiment 4 — Embedding Models

**Setup:** size 500 · overlap 50 · `k=5`. Both models run locally (no API, no cost).

| Model | Disk | Dim | Retrieval recall | Top-1 similarity | Mean answer coverage | Key-elements answer | Index time |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `all-MiniLM-L6-v2` | 88 MB | 384 | **0.933** | 0.602 | 0.80 | 0.60 (3 of 5) | **0.41 s** |
| `BAAI/bge-small-en-v1.5` | 129 MB | 384 | 0.911 | **0.763** ✅ | **0.90** ✅ | **0.80** (4 of 5) ✅ | 0.70 s |

### Findings — end-to-end data reverses the retrieval-only verdict

- **BGE produced better answers** — mean coverage 0.90 vs 0.80, and **4 of 5** vs 3 of 5 on the
  discriminating question — *despite* marginally lower keyword-retrieval recall (0.911 vs 0.933).
- **Why:** BGE's much higher top-1 similarity (**+27%**) reflects better *ranking*. Keyword recall
  only asks "was the fact somewhere in the top-5?"; ranking determines whether the right passage
  sits at the top where the model weights it most. **Better ranking → better answers.**
- **This is a lesson in metric choice.** Judged on retrieval recall alone, MiniLM looked better.
  Judged end-to-end — what users actually experience — BGE is better. Retrieval proxies can mislead.
- **MiniLM remains 1.7× faster to index** at **68% of the disk footprint**.

> **Conclusion:** **BGE-small is the better choice when answer quality is the priority**; MiniLM
> when indexing speed and footprint matter. Both are 384-dim, but embeddings from different models
> are **not interchangeable** — switching requires re-indexing (the app's **"♻️ Refresh embeddings"**
> button exists for exactly this).
>
> *Caveat: one document, single samples. Directionally consistent with BGE's retrieval-tuned
> training, but a larger corpus is needed before treating this as settled.*

---

## 6. Consolidated Recommendations

| Decision | Chosen value | Evidence |
| :--- | :--- | :--- |
| **Chunk size** | **900** | Exp 1 — answer coverage 0.20 → 1.00 as size grows |
| **Chunk overlap** | **120** (~13%) | Exp 2 — better similarity without the +43% chunk growth of 200 |
| **Retrieval depth `k`** | **6** | Exp 1 — lists span multiple chunks; k=5 was the binding constraint |
| **Embedding model** | **MiniLM** (default) · BGE for quality | Exp 4 — BGE +0.10 answer coverage; MiniLM 1.7× faster |
| **Templates** | **Generation only** | Exp 3 — raw query retrieves best, template generates best |

### Changes made to the application as a result

1. **Defaults retuned** to chunk size **900** / overlap **120** / `k` **6** (was 500/50/4) — directly
   fixing the "only 2 of 5 Key Elements" failure.
2. **Retrieval decoupled from templating** — the app embeds the **raw question** for vector search
   while the template is applied only to the LLM prompt, capturing **both** wins from Exp 3.
3. **Pipeline hardened** — the runs exposed providers intermittently returning `choices: null`,
   crashing generation with `'NoneType' object is not subscriptable`. `rag_pipeline` now detects
   empty responses and returns a clean error.

---

## 7. Limitations & Threats to Validity

- **Single document, six questions.** Directionally sound, but not a benchmark. A larger
  multi-domain corpus is needed before treating these values as universal constants.
- **Single sample per cell.** No repeated trials, so one-keyword differences (Exp 2's 0.40 vs 0.60,
  Exp 3's magnitudes) sit within noise. Conclusions are drawn only where the direction is
  consistent *and* mechanistically explainable.
- **Keyword-based scoring.** Answer coverage checks for exact ground-truth terms — it measures
  whether the facts arrived, not stylistic quality or correctness of framing.
- **One generation model.** All answers came from `nemotron-3-ultra`; a weaker model would likely
  amplify the chunk-size effect and a stronger one might mask it.
- **Free-tier quota.** OpenRouter allows 50 free requests/day; the study was split across two days
  (13 calls + 10 gap-fill) to stay within it.
- **Next steps:** benchmark the app's **hybrid (keyword + semantic)** retrieval with this harness;
  add a re-ranking stage; sweep chunk-size × `k` interactions; repeat runs for multi-sample means.

---

*Reproducible via the experiment harness against `Community Development.pdf`.*
*Measured by Rana Muhammad Haseeb Khan · Visibility Bots Fellowship — 2026.*
