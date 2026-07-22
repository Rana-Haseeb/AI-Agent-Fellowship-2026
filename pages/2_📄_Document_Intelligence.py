"""
Document Intelligence — Enterprise RAG platform.
Visibility Bots Innovation Lab · Fellowship Week 2
Author: Rana Muhammad Haseeb Khan

A superset of the AI Workspace: it carries over the Week 1 features (multiple
chat sessions, personas, prompt templates, model/connection controls, export)
and adds the full RAG stack plus every Week 2 bonus feature:

    auth (simulated) · multi-format upload (PDF/TXT/MD/DOCX) · per-document
    processing status (pages/chunks) · refresh embeddings · semantic + hybrid
    search · source citations with chunk references · conversation memory ·
    token & cost dashboard · auto-summarisation · suggested questions ·
    document comparison · light/dark theme

Backend: src.document_processor · src.vector_store · src.rag_pipeline
"""

import html
import os
import sys

import streamlit as st

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

# Rough public pricing (USD per 1M tokens) for the cost estimate.
PRICING = {
    "gpt-4o-mini": (0.15, 0.60), "gpt-4o": (2.50, 10.00),
    "gemini-2.0-flash": (0.075, 0.30), "gemini-2.5-flash": (0.30, 2.50),
}

# ==================================================================================
#  SESSION STATE
# ==================================================================================
defaults = {
    "dark_mode": True,
    "rag_user": None,
    "rag_sessions": {"Chat 1": {"messages": []}},
    "rag_current": "Chat 1",
    "doc_system_prompt": "You are a precise document analyst. Answer strictly from the documents, clearly and factually.",
    "doc_custom_templates": {},
    "rag_tokens": {"prompt": 0, "completion": 0, "total": 0},
    "rag_cost": 0.0,
    "doc_summaries": {},
    "doc_questions": {},
    "pending_question": None,
    "compare_result": None,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

inject_css(st.session_state.dark_mode)
store = get_store()


# ==================================================================================
#  1. USER AUTHENTICATION (simulated session)
# ==================================================================================
if not st.session_state.rag_user:
    render_hero("Document Intelligence", "Sign in to access your private knowledge base.", "🔒 Secure session")
    st.markdown('<div class="login-wrap">', unsafe_allow_html=True)
    with st.form("login_form"):
        st.markdown("#### 👤 Sign in")
        username = st.text_input("Username", placeholder="e.g. haseeb")
        st.text_input("Password", type="password", placeholder="any value (simulated)",
                      help="Demo authentication — no credentials are stored or verified.")
        c1, c2 = st.columns(2)
        signin = c1.form_submit_button("Sign in", use_container_width=True)
        guest = c2.form_submit_button("Continue as guest", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
    if signin and username.strip():
        st.session_state.rag_user = username.strip()
        st.rerun()
    elif signin:
        st.warning("Please enter a username.")
    if guest:
        st.session_state.rag_user = "guest"
        st.rerun()
    st.stop()


def current_messages():
    return st.session_state.rag_sessions[st.session_state.rag_current]["messages"]


def _track_usage(usage, model):
    """Accumulate token counts + rough cost for the dashboard."""
    if not usage:
        return
    tok = st.session_state.rag_tokens
    tok["prompt"] += usage.get("prompt", 0)
    tok["completion"] += usage.get("completion", 0)
    tok["total"] += usage.get("total", 0)
    rate = PRICING.get(model)
    if rate and ":free" not in model:
        st.session_state.rag_cost += (usage.get("prompt", 0) / 1e6) * rate[0] \
                                   + (usage.get("completion", 0) / 1e6) * rate[1]


# ---------- Callbacks ---------- #
def _delete_source(name):
    removed = store.delete_document_from_store(name)
    st.session_state.doc_summaries.pop(name, None)
    st.session_state.doc_questions.pop(name, None)
    st.toast(f"Removed '{name}' ({removed} chunk(s)).", icon="🗑️")


def _clear_library():
    store.clear_all_vectors()
    st.session_state.doc_summaries, st.session_state.doc_questions = {}, {}
    st.toast("Knowledge base cleared.", icon="🧹")


def _clear_chat():
    st.session_state.rag_sessions[st.session_state.rag_current]["messages"] = []


def _sign_out():
    st.session_state.rag_user = None


def _ask(question):
    st.session_state.pending_question = question


# ==================================================================================
#  SIDEBAR
# ==================================================================================
with st.sidebar:
    sidebar_brand("Doc Intelligence", "RAG over your documents")
    appearance_toggle()

    st.divider()
    nav_links()
    st.divider()

    # ---- Account ---- #
    st.markdown('<div class="side-title">Account</div>', unsafe_allow_html=True)
    ac1, ac2 = st.columns([3, 2])
    ac1.markdown(f"<div style='font-size:.85rem;padding-top:6px;color:var(--text);'>👤 <b>{html.escape(st.session_state.rag_user)}</b></div>",
                 unsafe_allow_html=True)
    ac2.button("Sign out", use_container_width=True, on_click=_sign_out)

    st.divider()

    # ---- Chat sessions ---- #
    st.markdown('<div class="side-title">Chat Sessions</div>', unsafe_allow_html=True)
    sess_names = list(st.session_state.rag_sessions.keys())
    st.session_state.rag_current = st.radio(
        "Active session", sess_names,
        index=sess_names.index(st.session_state.rag_current), label_visibility="collapsed")
    cs1, cs2 = st.columns(2)
    if cs1.button("➕ New", use_container_width=True):
        name = f"Chat {len(st.session_state.rag_sessions) + 1}"
        st.session_state.rag_sessions[name] = {"messages": []}
        st.session_state.rag_current = name
        st.rerun()
    if cs2.button("🗑️ Delete", use_container_width=True, disabled=len(sess_names) <= 1):
        del st.session_state.rag_sessions[st.session_state.rag_current]
        st.session_state.rag_current = list(st.session_state.rag_sessions.keys())[0]
        st.rerun()

    st.divider()

    # ---- Knowledge base ---- #
    st.markdown('<div class="side-title">📥 Knowledge Base</div>', unsafe_allow_html=True)
    with st.form("ingest_form", clear_on_submit=True):
        uploads = st.file_uploader(
            "Upload documents", type=["pdf", "txt", "md", "docx"],
            accept_multiple_files=True,
            help="PDF, TXT, Markdown, or DOCX. Parsed, chunked, embedded, and indexed.")
        chunk_size = st.slider("Chunk size (chars)", 200, 1500, 900, 50)
        chunk_overlap = st.slider("Chunk overlap (chars)", 0, 400, 120, 10)
        auto_enrich = st.checkbox("Auto-summarise & suggest questions", value=True,
                                  help="After indexing, generate a summary and starter questions (needs an API key).")
        process = st.form_submit_button("⚙️ Process & Index", use_container_width=True)

    st.divider()

    # ---- Retrieval ---- #
    st.markdown('<div class="side-title">🔎 Retrieval</div>', unsafe_allow_html=True)
    top_k = st.slider("Chunks to retrieve (k)", 1, 15, 6)
    use_hybrid = st.toggle("🔀 Hybrid search (keyword + semantic)", value=False,
                           help="Fuses exact keyword matches with meaning-based matches.")
    sources_now = store.list_sources()
    scope = st.selectbox("Search scope", ["All documents"] + sources_now)
    filter_dict = None if scope == "All documents" else {"source": scope}

    st.divider()

    # ---- Answer engine ---- #
    st.markdown('<div class="side-title">🤖 Answer Engine</div>', unsafe_allow_html=True)
    prov_label = st.selectbox("Provider", list(LLM_PROVIDERS.keys()))
    prov_cfg = LLM_PROVIDERS[prov_label]
    manual = st.toggle("✏️ Enter model ID manually", value=False)
    if manual:
        model = st.text_input("Model ID", value=list(prov_cfg["models"].values())[0])
    else:
        model_label = st.selectbox("Model", list(prov_cfg["models"].keys()))
        model = prov_cfg["models"][model_label]
    st.caption(prov_cfg["note"])
    api_key = st.text_input("API Key", value=os.getenv(prov_cfg["env"], ""), type="password",
                            help="Stored only in this session.")

    st.divider()

    # ---- Persona ---- #
    st.markdown('<div class="side-title">System Prompt (Persona)</div>', unsafe_allow_html=True)
    persona_presets = {
        "Custom": st.session_state.doc_system_prompt,
        "📄 Document Analyst": "You are a meticulous document analyst. Extract and explain information precisely and completely.",
        "🎓 Study Assistant": "You are a study assistant who explains document content clearly and simply for learning.",
        "⚖️ Contract/Policy Reviewer": "You are a careful reviewer who surfaces obligations, terms, dates, and risks stated in the documents.",
        "🔬 Research Assistant": "You are a research assistant who synthesizes findings from the documents rigorously.",
    }
    preset = st.selectbox("Preset", list(persona_presets.keys()))
    persona = st.text_area("Define the AI's role", value=persona_presets[preset], height=90)
    if persona != st.session_state.doc_system_prompt:
        st.session_state.doc_system_prompt = persona

    st.divider()

    # ---- Templates ---- #
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


def make_pipeline():
    return RAGPipeline(provider=prov_cfg["provider"], model=model, api_key=api_key)


# ==================================================================================
#  INGESTION (runs after the sidebar form is submitted)
# ==================================================================================
if process:
    if not uploads:
        st.sidebar.warning("Add at least one file before processing.")
    else:
        newly_indexed = []
        with st.spinner("Parsing, embedding, and indexing… (first run downloads the model)"):
            for f in uploads:
                records = extract_text_and_metadata(f)
                if not records:
                    st.sidebar.warning(f"Skipped '{f.name}' (no extractable text).")
                    continue
                chunks = chunk_documents(records, chunk_size, chunk_overlap)
                added = store.add_documents_to_store(chunks)
                if added:
                    newly_indexed.append((f.name, len(records), added))

        if newly_indexed:
            st.sidebar.success(
                "Indexed " + ", ".join(f"{n} ({p} page(s) → {c} chunk(s))" for n, p, c in newly_indexed))
            # ---- Auto summarisation + suggested questions ----
            if auto_enrich and api_key:
                pipe = make_pipeline()
                with st.spinner("Generating summaries and suggested questions…"):
                    for name, _pages, _chunks in newly_indexed:
                        hits = store.search_similar_chunks("overview summary main topics", k=5,
                                                           filter_dict={"source": name})
                        context = "\n\n".join(h["text"] for h in hits)[:6000]
                        if not context:
                            continue
                        summary, err, usage = pipe.complete(
                            f"Summarise the following document content in 4-6 concise bullet points.\n\n{context}",
                            system="You summarise documents factually, using only the given text.",
                            max_tokens=400)
                        if summary and not err:
                            st.session_state.doc_summaries[name] = summary
                            _track_usage(usage, model)
                        questions, err_q, usage_q = pipe.complete(
                            "Based on the content below, write exactly 4 short questions a reader "
                            "could ask about it. Output one question per line, no numbering.\n\n" + context,
                            system="You generate useful, answerable questions grounded in the given text.",
                            max_tokens=200)
                        if questions and not err_q:
                            qs = [q.strip(" -•0123456789.").strip()
                                  for q in questions.splitlines() if q.strip()][:4]
                            st.session_state.doc_questions[name] = qs
                            _track_usage(usage_q, model)
            elif auto_enrich and not api_key:
                st.sidebar.info("Add an API key to auto-generate summaries and questions.", icon="🔑")
        else:
            st.sidebar.error("Nothing was indexed. Check the file content / embedding model.")


# ==================================================================================
#  LIBRARY (sidebar, rendered after ingestion so counts are fresh)
# ==================================================================================
stats = store.get_source_stats()
sources = sorted(stats.keys())
total_chunks = store.count()
total_pages = sum(s["pages"] for s in stats.values())

with st.sidebar:
    st.divider()
    st.markdown('<div class="side-title">📚 Document Library</div>', unsafe_allow_html=True)
    if sources:
        for name in sources:
            s = stats[name]
            col_a, col_b = st.columns([5, 1])
            col_a.markdown(
                f"<div class='doc-row'><div class='doc-name'>📄 {html.escape(name)}</div>"
                f"<div class='doc-meta'>{s['pages']} page(s) · {s['chunks']} chunk(s) "
                f"<span class='pill-ok'>✅ indexed</span></div></div>",
                unsafe_allow_html=True)
            col_b.button("🗑️", key=f"del::{name}", help=f"Delete {name}",
                         on_click=_delete_source, args=(name,))
        lb1, lb2 = st.columns(2)
        if lb1.button("♻️ Refresh embeddings", use_container_width=True,
                      help="Re-compute embeddings for every stored chunk."):
            with st.spinner("Re-embedding all chunks…"):
                n = store.refresh_embeddings()
            st.success(f"Refreshed {n} chunk(s).") if n else st.error("Refresh failed.")
        lb2.button("🧹 Clear all", use_container_width=True, on_click=_clear_library)
    else:
        st.caption("No documents indexed yet.")
    st.markdown(
        f"<div class='stat-mini' style='margin-top:8px;'>Total items: "
        f"<b style='color:var(--text)'>{len(sources)}</b> · Pages: "
        f"<b style='color:var(--text)'>{total_pages}</b> · Chunks: "
        f"<b style='color:var(--text)'>{total_chunks}</b></div>",
        unsafe_allow_html=True)


# ==================================================================================
#  MAIN
# ==================================================================================
render_hero("Document Intelligence",
            "Upload files and query them through a grounded, citation-backed RAG pipeline.",
            f"● {prov_label} · {model} · 👤 {st.session_state.rag_user}")

messages = current_messages()
tok = st.session_state.rag_tokens
cost_txt = f"${st.session_state.rag_cost:.4f}" if st.session_state.rag_cost else "$0.00"
st.markdown(f"""
<div class="metric-row">
    <div class="metric"><div class="v">{len(sources)}</div><div class="l">Documents</div></div>
    <div class="metric"><div class="v">{total_pages}</div><div class="l">Pages</div></div>
    <div class="metric"><div class="v">{total_chunks}</div><div class="l">Chunks</div></div>
    <div class="metric"><div class="v">{tok['total']}</div><div class="l">Tokens · {cost_txt}</div></div>
</div>
""", unsafe_allow_html=True)

a1, a2, a3 = st.columns([1, 1, 4])
a1.button("🗑️ Clear Chat", use_container_width=True, on_click=_clear_chat)
if messages:
    export_md = f"# Document Intelligence — {st.session_state.rag_current}\n\n"
    export_md += f"*User:* {st.session_state.rag_user}\n\n*Persona:* {st.session_state.doc_system_prompt}\n\n---\n\n"
    for m in messages:
        if m["role"] == "user":
            export_md += f"### 🧑 You\n\n{m['content']}\n\n"
        else:
            export_md += f"### 📄 Assistant\n\n{m['content']}\n\n"
            for c in (m.get("citations") or []):
                tag = " (cited)" if c.get("cited") else ""
                export_md += f"> 📄 {c.get('source','?')} · page {c.get('page','?')} · chunk {c.get('chunk','?')}{tag}\n"
            export_md += "\n"
    a2.download_button("📥 Export", export_md, file_name=f"{st.session_state.rag_current}.md",
                       mime="text/markdown", use_container_width=True)
else:
    a2.button("📥 Export", use_container_width=True, disabled=True)


# ---------- Tools: summaries · suggested questions · comparison ---------- #
if sources:
    with st.expander("🧰 Document tools — summaries, suggested questions, comparison", expanded=False):
        tab_sum, tab_q, tab_cmp = st.tabs(["📝 Summaries", "💡 Suggested questions", "⚖️ Compare documents"])

        with tab_sum:
            if st.session_state.doc_summaries:
                for name, summary in st.session_state.doc_summaries.items():
                    st.markdown(f"<div class='tool-card'><h4>📄 {html.escape(name)}</h4>{summary}</div>",
                                unsafe_allow_html=True)
            else:
                st.caption("No summaries yet — enable auto-summarise when processing, or generate one below.")
            gen_for = st.selectbox("Generate a summary for", sources, key="sum_pick")
            if st.button("Generate summary", key="sum_btn"):
                if not api_key:
                    st.warning("Add an API key in the sidebar first.")
                else:
                    with st.spinner("Summarising…"):
                        hits = store.search_similar_chunks("overview summary main topics", k=6,
                                                           filter_dict={"source": gen_for})
                        ctx = "\n\n".join(h["text"] for h in hits)[:6000]
                        text, err, usage = make_pipeline().complete(
                            f"Summarise this document in 4-6 concise bullet points.\n\n{ctx}",
                            system="You summarise documents factually, using only the given text.")
                    if err:
                        st.error(err)
                    else:
                        st.session_state.doc_summaries[gen_for] = text
                        _track_usage(usage, model)
                        st.rerun()

        with tab_q:
            any_q = False
            for name, qs in st.session_state.doc_questions.items():
                if not qs:
                    continue
                any_q = True
                st.markdown(f"**📄 {html.escape(name)}**")
                for i, q in enumerate(qs):
                    st.button(f"💡 {q}", key=f"q::{name}::{i}", on_click=_ask, args=(q,),
                              use_container_width=True)
            if not any_q:
                st.caption("No suggested questions yet — enable auto-suggest when processing a document.")

        with tab_cmp:
            if len(sources) < 2:
                st.caption("Upload at least two documents to compare them.")
            else:
                c1, c2 = st.columns(2)
                doc_a = c1.selectbox("Document A", sources, key="cmp_a")
                doc_b = c2.selectbox("Document B", sources, index=min(1, len(sources) - 1), key="cmp_b")
                aspect = st.text_input("What should I compare?", value="key topics, purpose, and conclusions",
                                       key="cmp_aspect")
                if st.button("⚖️ Compare", key="cmp_btn"):
                    if doc_a == doc_b:
                        st.warning("Pick two different documents.")
                    elif not api_key:
                        st.warning("Add an API key in the sidebar first.")
                    else:
                        with st.spinner("Comparing documents…"):
                            ha = store.search_similar_chunks(aspect, k=5, filter_dict={"source": doc_a})
                            hb = store.search_similar_chunks(aspect, k=5, filter_dict={"source": doc_b})
                            ctx = (f"=== DOCUMENT A: {doc_a} ===\n" + "\n\n".join(h['text'] for h in ha)[:4000] +
                                   f"\n\n=== DOCUMENT B: {doc_b} ===\n" + "\n\n".join(h['text'] for h in hb)[:4000])
                            text, err, usage = make_pipeline().complete(
                                f"Compare these two documents on: {aspect}.\n"
                                "Give: similarities, differences, and a one-line verdict. "
                                "Use only the provided text.\n\n" + ctx,
                                system="You compare documents factually, using only the given text.",
                                max_tokens=800)
                        if err:
                            st.error(err)
                        else:
                            _track_usage(usage, model)
                            st.session_state.compare_result = f"**{doc_a}** vs **{doc_b}**\n\n{text}"
                if st.session_state.compare_result:
                    st.markdown(f"<div class='tool-card'>{st.session_state.compare_result}</div>",
                                unsafe_allow_html=True)


# ---------- Render helpers ---------- #
def _render_retrieved(retrieved):
    if not retrieved:
        return
    with st.expander(f"🔍 Retrieved context ({len(retrieved)} segment(s))", expanded=False):
        for i, hit in enumerate(retrieved, start=1):
            meta = hit.get("metadata", {}) or {}
            score = hit.get("score")
            bits = f"`{meta.get('source','unknown')}` · page {meta.get('page','?')} · chunk {meta.get('chunk','?')}"
            if score is not None:
                bits += f" · similarity {score}"
            if hit.get("match"):
                bits += f" · via {hit['match']}"
            st.markdown(f"**[Source {i}]** — {bits}")
            st.markdown(
                f"<div style='color:var(--muted);font-size:.85rem;white-space:pre-wrap;"
                f"border-left:2px solid var(--border);padding-left:10px;margin:2px 0 10px;'>"
                f"{html.escape(hit.get('text',''))}</div>", unsafe_allow_html=True)


def _render_citations(citations):
    if not citations:
        return
    rows = []
    for c in citations:
        badge = '<span class="cite-badge">cited</span>' if c.get("cited") else ""
        match = f'<span class="match-badge">{html.escape(str(c["match"]))}</span>' if c.get("match") else ""
        rows.append(
            f"<div class='cite-item'><span class='cite-src'>📄 {html.escape(str(c.get('source','?')))}</span>"
            f" · page {html.escape(str(c.get('page','?')))} · chunk {html.escape(str(c.get('chunk','?')))}"
            f"{badge}{match}<div class='cite-snip'>{html.escape(str(c.get('snippet','')))}</div></div>")
    st.markdown(f"<div class='cite-card'><div class='ct'>📎 Sources</div>{''.join(rows)}</div>",
                unsafe_allow_html=True)


# ---------- Empty state ---------- #
if not messages:
    st.markdown("""
    <div class="empty">
        <div class="big">📄</div>
        <div style="font-size:1.15rem;font-weight:600;">Chat with your documents</div>
        <div style="margin-top:6px;">Upload files, click <b>Process &amp; Index</b>, then ask — grounded answers with sources.</div>
    </div>
    """, unsafe_allow_html=True)

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
typed = st.chat_input(placeholder)

question = typed if (typed and typed.strip()) else st.session_state.pending_question
st.session_state.pending_question = None

if question:
    # Templates shape the LLM prompt, but retrieval embeds the RAW question.
    # Measured in Week 2 Experiment 3: templating the retrieval query dilutes the
    # embedding and cut top-1 similarity by up to 10.5% (and recall on one question).
    final_q = question if selected_template == "— None —" else all_templates[selected_template] + question
    retrieval_query = question
    messages.append({"role": "user", "content": final_q})

    answer, citations, retrieved, meta = "", [], [], None

    if total_chunks == 0:
        answer = ("📭 **No documents indexed yet.** Upload files in the sidebar and click "
                  "**Process & Index**, then ask your question.")
    elif not api_key:
        answer = ("🔑 **Add an API key** for the Answer Engine (sidebar) to generate a grounded answer. "
                  "Retrieval works without it, but the final answer needs an LLM.")
        retrieved = (store.hybrid_search if use_hybrid else store.search_similar_chunks)(
            retrieval_query, k=top_k, filter_dict=filter_dict)
    else:
        with st.spinner("Retrieving relevant context and generating a grounded answer…"):
            retrieved = (store.hybrid_search if use_hybrid else store.search_similar_chunks)(
                retrieval_query, k=top_k, filter_dict=filter_dict)
            history = [{"role": mm["role"], "content": mm["content"]}
                       for mm in messages if mm["role"] in ("user", "assistant")]
            result = make_pipeline().generate_rag_response(
                final_q, retrieved, chat_history=history[:-1],
                persona=st.session_state.doc_system_prompt)
            answer = result["answer"]
            citations = result["citations"]
            _track_usage(result.get("usage"), model)
            if result.get("latency") is not None:
                mode = "hybrid" if use_hybrid else "semantic"
                meta = f"⏱️ {result['latency']}s · 🔌 {prov_label} · 🎯 {model} · 🔎 {mode}"

    messages.append({"role": "assistant", "content": answer, "citations": citations,
                     "retrieved": retrieved, "meta": meta})
    st.rerun()
