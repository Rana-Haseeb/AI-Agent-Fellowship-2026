# 🏗️ AI Application Architecture — AI Workspace

### Assignment 5 — Visibility Bots Innovation Lab · Fellowship Week 1

**Author:** Rana Muhammad Haseeb Khan · **Track 2: NLP & AI Agents**

This document maps the execution pipeline of the **AI Workspace** app (Assignment 3): a Streamlit frontend, a Python backend, and a pluggable external LLM engine (OpenAI / OpenRouter).

---

## 1. System Topology Diagram

The diagram below details the structural components and directional data-flow pathways defining the request/response pipeline. Numbers `[1]–[6]` trace one full round trip.

```text
+------------------------------------------------------+
|                     USER BROWSER                     |
+------------------------------------------------------+
                            |
      [1] Submit prompt     |   [6] Render markdown
                            v
+------------------------------------------------------+
|             FRONTEND APPLICATION ENGINE              |
|                  (Streamlit App UI)                  |
+------------------------------------------------------+
                            |
      [2] Validate input    |   [5] Update session state
                            v
+------------------------------------------------------+
|               BACKEND EXECUTION LAYER                |
|               (Python Runtime Engine)                |
+------------------------------------------------------+
                            |
      [3] JSON payload      |   [4] Stream inference tokens
                            v
+------------------------------------------------------+
|             EXTERNAL LLM ENGINE PROVIDER             |
|             (OpenAI / OpenRouter Cloud)              |
+------------------------------------------------------+
```

**Linear view:** `User → Frontend → Backend → LLM API → Response`

---

## 2. Structural Component Matrix

| Tier | Layer / Component | Functional Accountability |
|------|-------------------|---------------------------|
| **Client Tier** | User Browser Interface | Captures natural-language input, renders formatted Markdown, and handles template/persona selection. |
| **Presentation Tier** | Frontend (Streamlit Engine) | Initializes session-state arrays, intercepts input strings, and lays out the UI configuration. |
| **Application Tier** | Backend (Python Runtime) | Enforces input validation, loads secrets via `dotenv`, assembles and encodes the API payload. |
| **Integration Tier** | External API Gateway | Runs inference across foundational models (e.g. `gpt-4o-mini`, `gpt-oss-120b`, `llama-3.3-70b`). |

---

## 3. Data Pipeline & Protocol Verification

### A. Request Flow Pipeline

1. **Instruction Capture.** The user interacts with the workspace panel — optionally choosing a quick template (e.g. *💻 Explain Code*) and a persona — then submits text into the chat field.
2. **State & Concurrency Check.** The system intercepts the transaction and validates the input. Empty/whitespace prompts are rejected; valid prompts are appended to the `st.session_state.messages` array.
3. **Context Assembly.** The execution thread reads the configured system prompt (e.g. *"You are a senior software engineer"*) and positions it at **index 0** of a new outbound message payload, followed by prior history and the new user turn.
4. **API Dispatch.** The backend initializes an authenticated client wrapper, compiles the message array plus generation parameters (temperature, `stream=True`), and sends an **HTTPS `POST /chat/completions`** with the API key in the `Authorization` header.

### B. Response Flow Pipeline

1. **Token Streaming Ingestion.** The external cloud authenticates the bearer token and begins generating **streamed token deltas** (Server-Sent Events) rather than one bulk payload.
2. **Payload Collection.** Deltas travel back over a secure **TLS** channel into the application server loop and are concatenated incrementally.
3. **Telemetry Interception.** The thread catches the stream, reads a high-resolution timer to compute **end-to-end latency**, and estimates **token totals**.
4. **State Commit & Visual Render.** The completed text is committed to session history, triggering a Streamlit **re-render** so the Markdown engine displays clean tables/code blocks and the metric cards refresh instantly with the new totals.

---

## 4. Defensive API Integration & Exception Boundaries

To keep runtime operations stable under high-traffic testing, the backend wraps the call in a **try-except** boundary and branches on validation state:

```text
                     +-------------------------------+
                     |      USER SUBMITS PROMPT      |
                     +---------------+---------------+
                                     |
                                     v
                     +-------------------------------+
                     |  Empty / whitespace prompt?   |
                     +-------+---------------+-------+
                          [Yes]           [No]
                             |               |
                             v               v
                  +------------------+  +-------------------------+
                  |  Skip API call;  |  |    API key present?     |
                  |  inline warning  |  +-----+-------------+-----+
                  +------------------+     [No]           [Yes]
                                             |              |
                                             v              v
                              +------------------+  +------------------------+
                              | Prompt: add key  |  |  Execute API call in   |
                              | or use Demo mode |  |  try-except boundary   |
                              +------------------+  +-----------+------------+
                                                                |
                                                                v
                                                  +-------------+-------------+
                                                  |     Call succeeded?       |
                                                  +------+-------------+------+
                                                      [No]           [Yes]
                                                         |             |
                                                         v             v
                                            +------------------+  +------------------+
                                            | Catch exception; |  | Stream response, |
                                            | render alert box |  | render markdown  |
                                            +------------------+  +------------------+
```

**Handled Core Failure Exceptions**

| Exception | Trigger | Behavior |
|-----------|---------|----------|
| **Empty Prompt** | blank / whitespace input | Skips the API step entirely — prevents wasted requests and token-billing leakage. |
| **Credential Failure** | `401` / auth mismatch | Terminates the thread and shows: *❌ Invalid or missing credentials.* |
| **Model Unavailable** | `404` / no endpoints | Shows: *🚫 Model unavailable — pick a different model.* |
| **Rate Limit / Quota** | `429` | Shows: *⏳ Rate limit reached* — and **rotates** to the next free model automatically. |
| **Transport Failure** | connection / timeout | Insulates the thread from a fatal traceback; renders: *⚠️ Network fault — connection failed.* |

---

## 5. API Integration

- **Unified client.** The OpenAI Python SDK is the single integration point; switching providers is just a different `base_url` + key, since OpenRouter is OpenAI-API-compatible (no code fork).
- **Provider abstraction.** A `PROVIDERS` config maps each provider to its `base_url`, env-var key name, and model catalog (OpenAI = paid, OpenRouter = free, Demo = simulated).
- **Secrets.** Keys load from environment variables / `.env` (or the sidebar at runtime) — **never hard-coded**, and excluded from git via `.gitignore`.
- **Streaming contract.** `stream=True` yields `choices[0].delta.content` chunks; `max_retries=0` hands retry control to the app's own model-rotation logic for predictable behavior.
- **Stateless API, stateful app.** The LLM holds no memory — conversational continuity comes from the backend **replaying the full message history** on every request.

---

*Architecture documented by Rana Muhammad Haseeb Khan · Visibility Bots Fellowship — 2026.*
