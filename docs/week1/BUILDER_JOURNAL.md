# 📓 Builder Journal — Week 1

### Assignment 6 — Visibility Bots Innovation Lab · Fellowship Week 1

**Author:** Rana Muhammad Haseeb Khan · **Track 2: NLP & AI Agents**
**FAST NUCES (Chiniot-Faisalabad) · Software Engineering**

---

## Why did I choose AI Engineering?

I come from a full-stack (MERN) and C++/DSA background, and for a long time I was happy *consuming* AI — calling an API, getting a response, shipping a feature. What pulled me toward AI Engineering specifically was realizing that the interesting problems aren't in the model, they're in the **system around the model**: how you feed it context, how you keep it reliable, how you recover when it fails, and how you make it *do things* rather than just talk.

That is fundamentally an **engineering** discipline, not a data-science one — it rewards the exact skills I already enjoy (clean architecture, error boundaries, state management) applied to a new, non-deterministic component. Week 1 confirmed this: the hardest parts of my work weren't the prompts, they were the plumbing — streaming, rate limits, and state.

## What type of AI products do I want to build?

I want to build **stateful, tool-using AI agents that ship real work**, not chat toys. Concretely:

- **Developer-productivity agents** — tools that read a codebase, reason over it, and take actions (like the AI Workspace I built this week, but with tool-calling and memory).
- **Full-stack agentic apps on the MERN + Python stack** — a React/Next.js frontend over a Python agent backend, with a vector store for long-term memory.
- **Multi-agent workflows** — orchestrator/worker systems where specialized agents (writer, reviewer, tester) collaborate on a task, backed by structured, schema-validated outputs.

The through-line is **production reliability**: type-safe outputs, graceful failure, and predictable cost.

## What was my biggest learning this week?

**A working demo and a reliable app are two very different things.** My AI Workspace "worked" the first time I ran it — but making it *trustworthy* took most of my effort: handling invalid keys, dead model IDs, rate limits, empty inputs, and stream interruptions without ever crashing or showing a raw stack trace.

The second big lesson was that **prompt engineering is really ambiguity removal.** Across my five experiments, every technique (role, chain-of-thought, few-shot, JSON, optimization) was just a different way of telling the model *who to be, how to think, what shape to output, and what constraints to honour.* Watching a vague "write about AI" prompt sprawl into a generic essay, then a constrained prompt produce a clean production codebase, made that click.

## What challenges did I face?

1. **Dead model IDs → 404s.** My first OpenRouter model slugs were stale; requests failed with `404 No endpoints found` even though my API key was valid.
2. **Free-tier rate limits.** While running my prompt-engineering experiments, the free models kept returning `429` — sometimes every model at once — which stalled my runs.
3. **A stale UI.** My token/message/session metric cards only updated on the *next* message, not when the AI finished replying.
4. **A trapped sidebar.** After I hid the Streamlit header with custom CSS, collapsing the sidebar left no way to reopen it.
5. **Overcrowded diagrams.** My first architecture diagrams (Mermaid) overlapped on some renderers.

## How did I solve them?

1. **404s:** replaced the stale slugs with current valid IDs and added a *"type any model manually"* toggle so the app never gets stuck on a bad list again. I also made the error handler say *"model unavailable — pick another"* instead of dumping the raw 404.
2. **Rate limits:** built a **model-rotation fallback** — the client tries a pool of free models and returns the first that responds, with `max_retries=0` so it fails fast and moves on. That turned an unreliable run into a completable one.
3. **Stale UI:** I learned this was a **render-order** problem — the cards were drawn before the response was processed. Fixing it was a single `st.rerun()` after the reply completes (placed *outside* the try/except so it isn't swallowed).
4. **Trapped sidebar:** instead of hiding the whole header, I hid only the toolbar and **explicitly forced the sidebar expand control visible**.
5. **Diagrams:** I switched to **precisely-aligned ASCII diagrams**, which render identically everywhere.

The common thread: every fix came from understanding *why* it broke, not just patching the symptom.

## What are my goals for Week 2?

- **Add tool-calling** to the AI Workspace so the model can actually *do* things (call a function, hit an API), not just answer.
- **Implement memory** — wire a vector store (Supabase / pgvector) for retrieval-augmented, long-term context beyond the session window.
- **Enforce structured outputs** with Pydantic/JSON-schema validation and a self-correcting retry loop.
- **Prototype a two-agent workflow** (a worker + a reviewer) to feel out orchestration.
- **Deepen the fundamentals** behind the ReAct and Reflexion papers I referenced, and turn my Week 1 error-handling patterns into a reusable module.

---

*Builder Journal by Rana Muhammad Haseeb Khan · Visibility Bots Fellowship — 2026.*
