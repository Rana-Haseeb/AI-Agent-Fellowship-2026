# 📓 Builder Journal — Week 2

### Assignment 5 · Building a Production-Grade RAG Application

**Author:** Rana Muhammad Haseeb Khan · **Track 2: NLP & AI Agents**
**FAST NUCES (Chiniot-Faisalabad) · Visibility Bots Innovation Lab**

---

## What worked well

**Separating the backend from the UI.** I put the whole pipeline in `src/` — `document_processor`,
`vector_store`, `rag_pipeline` — with a hard rule that no module there imports Streamlit. That
decision paid for itself twice: I could unit-test each module in isolation, and when it came time to
run experiments I drove the *exact same code* from a script instead of clicking through the UI. The
numbers in my experiment report describe the real system, not a reimplementation of it.

**Making the LLM client and embeddings injectable.** Both `VectorStore` and `RAGPipeline` accept an
optional pre-built dependency, so I could test ChromaDB logic with a fake embedder and the whole
grounding/citation flow with a fake LLM — no API key, no network, no cost. I caught several bugs
this way before spending a single token.

**Transparency as a feature.** Showing the retrieved chunks — source, page, chunk index, similarity
score — *before* the answer turned the system from a black box into something I could debug by
looking at it. That one panel explained more failures than any log line.

---

## What challenges I faced

**1. The answer was confidently incomplete.** My document listed five "Key Elements of Community
Development." The app returned two. My first instinct was that the PDF hadn't fully indexed — the
library showed only 14 chunks for a 153 KB file, which *looked* wrong.

**2. The live deployment crashed on Streamlit Cloud** with `ModuleNotFoundError` while working
perfectly on my machine.

**3. The app hung on first load** — a blank main area and a half-rendered sidebar, with hundreds of
`torchvision` errors in the log.

**4. Google Gemini returned `403 PERMISSION_DENIED`** even after I enabled the Generative Language
API in Cloud Console.

**5. Light mode had invisible buttons** — "Browse files" and "Process & Index" rendered dark-on-dark.

**6. The free tier ran out mid-experiment**, blocking the generation half of two experiments.

---

## How I debugged them

The habit I built this week: **measure before concluding.** Every one of these was solved by
gathering evidence rather than guessing at a fix.

**The incomplete answer.** Instead of tweaking parameters, I ran my own parser over the actual PDF
and counted: 7 pages, 6,046 characters, 14 chunks — and confirmed all five elements *were* present
in the extracted text. So indexing was fine. That reframed the question from "why didn't it index?"
to "why didn't retrieval return it?" I then built a harness that swept chunk size 300/500/1000
against ground-truth keywords. The result was unambiguous: the answer contained **1 of 5** elements
at size 300 and **5 of 5** at 1000. The five-item list spanned ~900 characters and was being
**split across chunks**; with `k=5` the model only ever received a fragment. Not an indexing bug —
a chunking-and-retrieval bug, proven with numbers.

**The Cloud crash.** I read the traceback carefully instead of skimming it. It failed on line 31 —
my *fallback* import — which meant the primary import had already failed silently in the `except`.
Both `langchain_text_splitters` and `langchain.text_splitter` were unavailable, so the bare
`langchain` package hadn't pulled the sub-package I actually import. Fix: list the exact
sub-packages (`langchain-core`, `langchain-text-splitters`, `langchain-huggingface`) instead of
trusting a meta-package's transitive dependencies.

**The hang.** The main-area blank plus a stalled sidebar told me the script wasn't crashing — it was
still *running*. Filtering the log showed Streamlit's file-watcher walking `transformers`' hundreds
of lazy modules, each attempting a `torchvision` import. Not my code at all. Setting
`fileWatcherType = "none"` took the log from hundreds of error lines to zero.

**The Gemini 403.** I read the status code as data. A `401` means a bad key; a `404` means a bad
model; a **`403`** means the key is fine but the *project* is denied. I verified by calling
`/models` — which returned 200 and listed models — then `/chat/completions`, which returned 403. So
the key authenticated and could read metadata but couldn't run inference: a project/region
restriction, not something I could fix in code. I routed Gemini through OpenRouter instead.

**The invisible buttons.** Rather than guessing selectors, I queried the computed styles directly in
a headless browser and found the file-uploader and form-submit buttons still carrying Streamlit's
dark base theme — two testids my CSS had never targeted.

---

## What I would improve

- **Add a cross-encoder re-ranker** between retrieval and generation. My measurements showed
  `bge-small` had *lower* keyword recall than MiniLM yet produced *better answers* — because its
  ranking was better. Ranking, not recall, was the real bottleneck, and re-ranking attacks it
  directly.
- **Chunk on document structure, not character counts.** The failure that started this whole
  investigation was a numbered list severed mid-list. A splitter that respects headings and list
  boundaries would have prevented it entirely.
- **Turn the experiment harness into CI.** I have ground-truth questions and a scoring function
  already; running them on every config change would catch retrieval regressions automatically.
- **Run multiple samples per configuration.** Single samples meant some differences (0.4 vs 0.6)
  sat within noise, and I had to report them as inconclusive rather than as findings.
- **Isolate the vector store per user.** Right now all users share one Chroma collection — fine for
  a demo, unacceptable for a real multi-tenant product, where metadata filtering would become the
  access-control boundary.

---

## What I learned about RAG

**The most dangerous RAG failure is not hallucination — it is silent incompleteness.** A fabricated
answer is obvious and testable. But the answer that listed *two of five* elements was fluent,
correctly grounded, properly cited, and confidently wrong-by-omission. Nothing in the system flagged
it. I only caught it because I happened to know the document. That reframed how I think about
evaluation: I now measure **retrieval recall** (did we find the facts?) *and* **answer coverage**
(did the user receive them?), because the gap between those two is exactly where these systems fail
quietly.

**Grounding and completeness are different problems.** My out-of-document control question was
correctly refused in 3 of 3 configurations — the grounding prompt is genuinely robust. But that same
robust prompt cheerfully produced a one-of-five answer, because the model can only be faithful to
the context it is handed. **Retrieval quality is the ceiling on answer quality**; no prompt
engineering raises it.

**Proxy metrics can point the wrong way.** Judged on retrieval recall alone, MiniLM beat BGE.
Judged end-to-end on the answers users actually read, BGE won. If I had stopped at the retrieval
metric I would have made the wrong call — a lesson that generalizes well beyond RAG.

**The same knob helps in one stage and hurts in another.** Prompt templates *lowered* retrieval
quality (they dilute the query embedding) while *raising* answer quality (they instruct the model to
be exhaustive). The right answer wasn't to pick a side — it was to split the stages: embed the raw
question, template only the generation prompt. Good architecture often means refusing a false
either/or.

**RAG is a systems discipline, not a prompting trick.** Connecting an LLM to a vector store took an
afternoon. Making it *reliable* — correct chunking, encoding fallbacks, upsert semantics, graceful
provider errors, honest refusals, visible provenance — took the rest of the week. That gap is the
actual job.

---

*Written by Rana Muhammad Haseeb Khan · Visibility Bots Fellowship — Week 2, 2026.*
