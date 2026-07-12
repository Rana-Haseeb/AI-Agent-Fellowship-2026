"""
Document Intelligence — RAG over your own documents.
Visibility Bots Innovation Lab · Fellowship Week 2
Author: Rana Muhammad Haseeb Khan

A superset of the AI Workspace: it carries over the Week 1 features —
multiple chat sessions, system-prompt personas, prompt templates, full
model/connection controls, and chat export — and adds the RAG stack on top
(upload → index → retrieve → grounded, citation-backed answers).

Backend modules:
    src.document_processor  — parse + chunk uploaded files
    src.vector_store        — persistent Chroma embeddings (index / search / delete)
    src.rag_pipeline        — grounded, citation-backed generation

State is page-isolated (rag_*), so it never mixes with the Week 1 workspace.
"""

import html
import os
import sys

import streamlit as st

# Make the repo root importable so `theme` and `src` resolve on any page.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from theme import inject_css, page_icon, render_hero, sidebar_brand, appearance_toggle, nav_links

from src.document_processor import extract_text_and_metadata, chunk_documents
from src.vector_store import get_store
from src.rag_pipeline import RAGPipeline

# ==================================================================================
#  PAGE CONFIG
# ==================================================================================
st.set_page_config(
    page_title="Document Intelligence",
    page_icon=page_icon(),
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Answer-engine (LLM) providers for grounded generation ----
LLM_PROVIDERS = {
    "OpenRouter": {
        "provider": "openrouter", "env": "OPENROUTER_API_KEY",
        "note": "🟢 Free models — test at zero cost.",
        "models": {
            "NVIDIA Nemotron 3 Ultra · Free (1M ctx)": "nvidia/nemotron-3-ultra-550b-a55b:free",
            "Qwen3 Coder 480B · Free (best for code)": "qwen/qwen3-coder-480b-a35b:free",
            "OpenAI gpt-oss-120b · Free": "openai/gpt-oss-120b:free",
            "Meta Llama 3.3 70B · Free (reliable)": "meta-llama/llama-3.3-70b-instruct:free",
            "Cohere North Mini Code · Free (fastest)": "cohere/north-mini-code:free",
        },
    },
    "OpenAI": {
        "provider": "openai", "env": "OPENAI_API_KEY",
        "note": "💳 Requires a paid OpenAI key.",
        "models": {"GPT-4o mini · Paid": "gpt-4o-mini", "GPT-4o · Paid": "gpt-4o"},
    },
    "Google AI Studio": {
        "provider": "google", "env": "GOOGLE_API_KEY",
        "note": "🔑 Free key at aistudio.google.com/apikey.",
        "models": {"Gemini 2.0 Flash": "gemini-2.0-flash", "Gemini 2.5 Flash": "gemini-2.5-flash"},
    },
}

DEFAULT_TEMPLATES = {
    "— None —": "",
    "📝 Summarize": "Summarize what the documents say about the following, as concise bullet points:\n\n",
    "📋 List key facts": "List every key fact the documents state about the following:\n\n",
    "🔍 Explain": "Explain the following using only the documents, with examples if present:\n\n",
    "⚖️ Compare": "Using only the documents, compare and contrast the following:\n\n",
    "🧭 Step-by-step": "Lay out, step by step, what the documents say about:\n\n",
}

# ==================================================================================
#  SESSION STATE  (page-isolated)
# ==================================================================================
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True
if "rag_sessions" not in st.session_state:
    st.session_state.rag_sessions = {"Chat 1": {"messages": []}}
    st.session_state.rag_current = "Chat 1"
if "doc_system_prompt" not in st.session_state:
    st.session_state.doc_system_prompt = (
        "You are a precise document analyst. Answer strictly from the documents, clearly and factually."
    )
if "doc_custom_templates" not in st.session_state:
    st.session_state.doc_custom_templates = {}

inject_css(st.session_state.dark_mode)

store = get_store()  # shared persistent VectorStore singleton


def current_messages():
    return st.session_state.rag_sessions[st.session_state.rag_current]["messages"]


# ---------- Callbacks (keep clicks snappy, avoid recompute on rerun) ---------- #
def _delete_source(name: str):
    removed = store.delete_document_from_store(name)
    st.toast(f"Removed '{name}' ({removed} chunk(s)).", icon="🗑️")


def _clear_library():
    store.clear_all_vectors()
    st.toast("Cleared the whole knowledge base.", icon="🧹")


def _clear_chat():
    st.session_state.rag_sessions[st.session_state.rag_current]["messages"] = []


# ==================================================================================
#  SIDEBAR
# ==================================================================================
with st.sidebar:
    sidebar_brand("Doc Intelligence", "RAG over your documents")
    appearance_toggle()

    st.divider()
    nav_links()
    st.divider()

    # ---- Chat sessions (carried from Week 1) ------------------------------- #
    st.markdown('<div class="side-title">Chat Sessions</div>', unsafe_allow_html=True)
    sess_names = list(st.session_state.rag_sessions.keys())
    st.session_state.rag_current = st.radio(
        "Active session", sess_names,
        index=sess_names.index(st.session_state.rag_current), label_visibility="collapsed",
    )
    cs1, cs2 = st.columns(2)
    if cs1.button("➕ New", use_container_width=True):
        new_name = f"Chat {len(st.session_state.rag_sessions) + 1}"
        st.session_state.rag_sessions[new_name] = {"messages": []}
        st.session_state.rag_current = new_name
        st.rerun()
    if cs2.button("🗑️ Delete", use_container_width=True, disabled=len(sess_names) <= 1):
        del st.session_state.rag_sessions[st.session_state.rag_current]
        st.session_state.rag_current = list(st.session_state.rag_sessions.keys())[0]
        st.rerun()

    st.divider()

    # ---- Knowledge base (ingest) ------------------------------------------- #
    st.markdown('<div class="side-title">📥 Knowledge Base</div>', unsafe_allow_html=True)
    with st.form("ingest_form", clear_on_submit=True):
        uploads = st.file_uploader(
            "Upload documents", type=["pdf", "txt", "md"],
            accept_multiple_files=True,
            help="PDF, TXT, or MD. Parsed, chunked, embedded, and indexed.",
        )
        chunk_size = st.slider("Chunk size (chars)", 200, 1500, 900, 50)
        chunk_overlap = st.slider("Chunk overlap (chars)", 0, 400, 120, 10)
        process = st.form_submit_button("⚙️ Process & Index", use_container_width=True)

    if process:
        if not uploads:
            st.warning("Add at least one file before processing.")
        else:
            added_total, ok_files = 0, 0
            with st.spinner("Parsing, embedding, and indexing… (first run downloads the model)"):
                for f in uploads:
                    records = extract_text_and_metadata(f)
                    if not records:
                        st.warning(f"Skipped '{f.name}' (no extractable text).")
                        continue
                    chunks = chunk_documents(records, chunk_size, chunk_overlap)
                    added = store.add_documents_to_store(chunks)
                    added_total += added
                    ok_files += 1 if added else 0
            if added_total:
                st.success(f"Indexed {ok_files} file(s) → {added_total} chunk(s).")
            else:
                st.error("Nothing was indexed. Check the logs (embedding model / file content).")

    st.divider()

    # ---- Library ----------------------------------------------------------- #
    st.markdown('<div class="side-title">📚 Library</div>', unsafe_allow_html=True)
    sources = store.list_sources()
    total_chunks = store.count()
    if sources:
        for name in sources:
            col_name, col_del = st.columns([5, 1])
            col_name.markdown(
                f"<div style='font-size:.85rem;color:var(--text);padding-top:6px;'>📄 {html.escape(name)}</div>",
                unsafe_allow_html=True,
            )
            col_del.button("🗑️", key=f"del::{name}", help=f"Delete {name}",
                           on_click=_delete_source, args=(name,))
        st.button("🧹 Clear all documents", use_container_width=True, on_click=_clear_library)
    else:
        st.caption("No documents indexed yet.")
    st.markdown(
        f"<div style='margin-top:8px;font-size:.78rem;color:var(--muted);'>"
        f"Total items: <b style='color:var(--text)'>{len(sources)}</b> &nbsp;·&nbsp; "
        f"Total chunks: <b style='color:var(--text)'>{total_chunks}</b></div>",
        unsafe_allow_html=True,
    )

    st.divider()

    # ---- Retrieval --------------------------------------------------------- #
    st.markdown('<div class="side-title">🔎 Retrieval</div>', unsafe_allow_html=True)
    top_k = st.slider("Chunks to retrieve (k)", 1, 15, 6)
    scope = st.selectbox("Search scope", ["All documents"] + sources)
    filter_dict = None if scope == "All documents" else {"source": scope}

    st.divider()

    # ---- Answer engine (Model & Connection, carried from Week 1) ----------- #
    st.markdown('<div class="side-title">🤖 Answer Engine</div>', unsafe_allow_html=True)
    prov_label = st.selectbox("Provider", list(LLM_PROVIDERS.keys()))
    prov_cfg = LLM_PROVIDERS[prov_label]
    manual = st.toggle("✏️ Enter model ID manually", value=False,
                       help="Type any exact model ID for this provider.")
    if manual:
        model = st.text_input("Model ID", value=list(prov_cfg["models"].values())[0])
    else:
        model_label = st.selectbox("Model", list(prov_cfg["models"].keys()))
        model = prov_cfg["models"][model_label]
    st.caption(prov_cfg["note"])
    api_key = st.text_input(
        "API Key", value=os.getenv(prov_cfg["env"], ""), type="password",
        help="Used only to generate the final answer. Stored only in this session.",
    )

    st.divider()

    # ---- System prompt / persona (carried from Week 1) --------------------- #
    st.markdown('<div class="side-title">System Prompt (Persona)</div>', unsafe_allow_html=True)
    persona_presets = {
        "Custom": st.session_state.doc_system_prompt,
        "📄 Document Analyst": "You are a meticulous document analyst. Extract and explain information precisely and completely.",
        "🎓 Study Assistant": "You are a study assistant who explains document content clearly and simply for learning.",
        "⚖️ Contract/Policy Reviewer": "You are a careful reviewer who surfaces obligations, terms, dates, and risks stated in the documents.",
        "🔬 Research Assistant": "You are a research assistant who synthesizes findings from the documents rigorously.",
    }
    preset = st.selectbox("Preset", list(persona_presets.keys()))
    persona = st.text_area(
        "Define the AI's role", value=persona_presets[preset], height=90,
        help="Sets tone/role. Grounding rules always stay enforced.",
    )
    if persona != st.session_state.doc_system_prompt:
        st.session_state.doc_system_prompt = persona

    st.divider()

    # ---- Prompt templates (carried from Week 1) ---------------------------- #
    st.markdown('<div class="side-title">Prompt Templates</div>', unsafe_allow_html=True)
    all_templates = {**DEFAULT_TEMPLATES, **st.session_state.doc_custom_templates}
    selected_template = st.selectbox("Quick template", list(all_templates.keys()))
    with st.expander("💾 Save a custom template"):
        t_name = st.text_input("Template name", placeholder="e.g. 📅 Find deadlines")
        t_body = st.text_area("Template prompt", placeholder="Find all dates and deadlines about:\n\n", height=70)
        if st.button("Save Template", use_container_width=True):
            if t_name.strip() and t_body.strip():
                st.session_state.doc_custom_templates[t_name.strip()] = t_body
                st.toast(f"Saved template: {t_name}", icon="💾")
                st.rerun()
            else:
                st.warning("Both name and prompt are required.")


# ==================================================================================
#  MAIN
# ==================================================================================
render_hero(
    "Document Intelligence",
    "Upload files and query them through a grounded, citation-backed RAG pipeline.",
    f"● {prov_label} · {model}",
)

messages = current_messages()
n_questions = len([m for m in messages if m["role"] == "user"])
st.markdown(f"""
<div class="metric-row">
    <div class="metric"><div class="v">{len(sources)}</div><div class="l">Documents</div></div>
    <div class="metric"><div class="v">{total_chunks}</div><div class="l">Chunks</div></div>
    <div class="metric"><div class="v">{n_questions}</div><div class="l">Questions</div></div>
    <div class="metric"><div class="v">{len(st.session_state.rag_sessions)}</div><div class="l">Sessions</div></div>
</div>
""", unsafe_allow_html=True)

# ---- Action row: clear / export (carried from Week 1) ---- #
a1, a2, a3 = st.columns([1, 1, 4])
a1.button("🗑️ Clear Chat", use_container_width=True, on_click=_clear_chat)

if messages:
    export_md = f"# Document Intelligence — {st.session_state.rag_current}\n\n"
    export_md += f"*Persona:* {st.session_state.doc_system_prompt}\n\n---\n\n"
    for m in messages:
        if m["role"] == "user":
            export_md += f"### 🧑 You\n\n{m['content']}\n\n"
        else:
            export_md += f"### 📄 Assistant\n\n{m['content']}\n\n"
            for c in (m.get("citations") or []):
                tag = " (cited)" if c.get("cited") else ""
                export_md += f"> 📄 {c.get('source','?')} · page {c.get('page','?')}{tag}\n"
            export_md += "\n"
    a2.download_button("📥 Export", export_md, file_name=f"{st.session_state.rag_current}.md",
                       mime="text/markdown", use_container_width=True)
else:
    a2.button("📥 Export", use_container_width=True, disabled=True)


# ---------- Render helpers ---------------------------------------------------- #
def _render_retrieved(retrieved):
    if not retrieved:
        return
    with st.expander(f"🔍 Retrieved context ({len(retrieved)} segment(s))", expanded=False):
        for i, hit in enumerate(retrieved, start=1):
            meta = hit.get("metadata", {}) or {}
            src = meta.get("source", "unknown")
            page = meta.get("page", "?")
            score = hit.get("score")
            score_txt = f" · similarity {score}" if score is not None else ""
            st.markdown(f"**[Source {i}]** — `{src}` · page {page}{score_txt}")
            st.markdown(
                f"<div style='color:var(--muted);font-size:.85rem;white-space:pre-wrap;"
                f"border-left:2px solid var(--border);padding-left:10px;margin:2px 0 10px;'>"
                f"{html.escape(hit.get('text',''))}</div>",
                unsafe_allow_html=True,
            )


def _render_citations(citations):
    if not citations:
        return
    rows = []
    for c in citations:
        badge = '<span class="cite-badge">cited</span>' if c.get("cited") else ""
        rows.append(
            f"<div class='cite-item'><span class='cite-src'>📄 {html.escape(str(c.get('source','?')))}</span>"
            f" · page {html.escape(str(c.get('page','?')))}{badge}"
            f"<div class='cite-snip'>{html.escape(str(c.get('snippet','')))}</div></div>"
        )
    st.markdown(
        f"<div class='cite-card'><div class='ct'>📎 Sources</div>{''.join(rows)}</div>",
        unsafe_allow_html=True,
    )


# ---------- Empty state ------------------------------------------------------- #
if not messages:
    st.markdown("""
    <div class="empty">
        <div class="big">📄</div>
        <div style="font-size:1.15rem;font-weight:600;">Chat with your documents</div>
        <div style="margin-top:6px;">Upload files, click <b>Process &amp; Index</b>, then ask — grounded answers with sources.</div>
    </div>
    """, unsafe_allow_html=True)

# ---------- Chat history ------------------------------------------------------ #
for m in messages:
    avatar = "🧑" if m["role"] == "user" else "📄"
    with st.chat_message(m["role"], avatar=avatar):
        if m["role"] == "assistant":
            _render_retrieved(m.get("retrieved"))
        st.markdown(m["content"])
        if m["role"] == "assistant":
            _render_citations(m.get("citations"))
            if m.get("meta"):
                st.caption(m["meta"])

# ==================================================================================
#  QUERY PIPELINE
# ==================================================================================
placeholder = "Ask a question about your documents…" if selected_template == "— None —" \
    else "Template active — add your topic here…"
question = st.chat_input(placeholder)

if question is not None and question.strip():
    final_q = question if selected_template == "— None —" else all_templates[selected_template] + question
    messages.append({"role": "user", "content": final_q})

    answer, citations, retrieved, meta = "", [], [], None

    if total_chunks == 0:
        answer = ("📭 **No documents indexed yet.** Upload files in the sidebar and click "
                  "**Process & Index**, then ask your question.")
    elif not api_key:
        answer = ("🔑 **Add an API key** for the Answer Engine (sidebar) to generate a grounded answer. "
                  "Retrieval works without it, but the final answer needs an LLM.")
        retrieved = store.search_similar_chunks(final_q, k=top_k, filter_dict=filter_dict)
    else:
        with st.spinner("Retrieving relevant context and generating a grounded answer…"):
            retrieved = store.search_similar_chunks(final_q, k=top_k, filter_dict=filter_dict)
            history = [{"role": mm["role"], "content": mm["content"]}
                       for mm in messages if mm["role"] in ("user", "assistant")]
            pipeline = RAGPipeline(provider=prov_cfg["provider"], model=model, api_key=api_key)
            result = pipeline.generate_rag_response(
                final_q, retrieved, chat_history=history[:-1],
                persona=st.session_state.doc_system_prompt,
            )
            answer = result["answer"]
            citations = result["citations"]
            if result.get("latency") is not None:
                meta = f"⏱️ {result['latency']}s · 🔌 {prov_label} · 🎯 {model}"

    messages.append({
        "role": "assistant",
        "content": answer,
        "citations": citations,
        "retrieved": retrieved,
        "meta": meta,
    })
    st.rerun()
