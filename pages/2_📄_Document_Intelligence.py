"""
Document Intelligence — RAG over your own documents.
Visibility Bots Innovation Lab · Fellowship Week 2
Author: Rana Muhammad Haseeb Khan

SCAFFOLD ONLY (for now):
  • reuses the shared theme (theme.py) so the look matches AI Workspace
  • keeps its OWN independent session state (doc_*) — chat here never leaks
    into the Week 1 AI Workspace page, and vice-versa
  • lays out the upload → index → chat structure that the RAG pipeline
    (parser, embeddings, vector store, retrieval loop) will plug into next.
"""

import os
import sys

import streamlit as st

# Make the repo root importable so `theme` resolves whether run via the router or directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from theme import inject_css, page_icon, render_hero, sidebar_brand, appearance_toggle, nav_links

# ==================================================================================
#  PAGE CONFIG
# ==================================================================================
st.set_page_config(
    page_title="Document Intelligence",
    page_icon=page_icon(),
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==================================================================================
#  SESSION STATE  (independent from the AI Workspace page)
# ==================================================================================
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True
if "doc_messages" not in st.session_state:
    st.session_state.doc_messages = []      # this page's own chat history
if "doc_files" not in st.session_state:
    st.session_state.doc_files = []         # names of uploaded documents
if "doc_indexed" not in st.session_state:
    st.session_state.doc_indexed = False    # has the knowledge base been built?

inject_css(st.session_state.dark_mode)

# ==================================================================================
#  SIDEBAR — Knowledge base controls
# ==================================================================================
with st.sidebar:
    sidebar_brand("Doc Intelligence", "RAG over your documents")
    appearance_toggle()

    st.divider()
    nav_links()
    st.divider()

    st.markdown('<div class="side-title">Knowledge Base</div>', unsafe_allow_html=True)
    uploads = st.file_uploader(
        "Upload documents",
        type=["pdf", "txt", "md", "docx"],
        accept_multiple_files=True,
        help="These will be parsed, embedded, and indexed for retrieval.",
    )
    if uploads:
        st.session_state.doc_files = [f.name for f in uploads]

    if st.button("⚙️ Build Index", use_container_width=True, disabled=not uploads):
        # TODO (next step): parse -> chunk -> embed -> store in vector DB.
        st.session_state.doc_indexed = True
        st.toast("Knowledge base ready (placeholder).", icon="✅")

    if st.session_state.doc_files:
        st.caption("Loaded: " + ", ".join(st.session_state.doc_files))

    st.divider()

    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.doc_messages = []
        st.rerun()

# ==================================================================================
#  MAIN
# ==================================================================================
render_hero(
    "Document Intelligence",
    "Upload files and query them through a production-grade RAG pipeline.",
    "🚧 Week 2 · scaffold",
)

n_docs = len(st.session_state.doc_files)
n_msgs = len([m for m in st.session_state.doc_messages if m["role"] == "user"])
st.markdown(f"""
<div class="metric-row">
    <div class="metric"><div class="v">{n_docs}</div><div class="l">Documents</div></div>
    <div class="metric"><div class="v">{n_msgs}</div><div class="l">Questions</div></div>
    <div class="metric"><div class="v">{'✅' if st.session_state.doc_indexed else '—'}</div><div class="l">Indexed</div></div>
    <div class="metric"><div class="v">RAG</div><div class="l">Pipeline</div></div>
</div>
""", unsafe_allow_html=True)

st.info("🚧 **Scaffold** — the RAG pipeline (parsing, embeddings, vector search, "
        "retrieval) isn't wired up yet. Upload documents in the sidebar to preview the flow.", icon="🧩")

# ---- Chat history (this page's own state) ----
if not st.session_state.doc_messages:
    st.markdown("""
    <div class="empty">
        <div class="big">📄</div>
        <div style="font-size:1.15rem;font-weight:600;">Chat with your documents</div>
        <div style="margin-top:6px;">Upload files in the sidebar, build the index, then ask questions.</div>
    </div>
    """, unsafe_allow_html=True)

for m in st.session_state.doc_messages:
    avatar = "🧑" if m["role"] == "user" else "📄"
    with st.chat_message(m["role"], avatar=avatar):
        st.markdown(m["content"])

# ---- Input (placeholder response until the RAG pipeline is implemented) ----
question = st.chat_input("Ask a question about your documents…")
if question is not None:
    if not question.strip():
        st.error("⚠️ Cannot send an empty question.")
    else:
        st.session_state.doc_messages.append({"role": "user", "content": question})
        placeholder_answer = (
            "_The RAG pipeline isn't implemented yet — this page is a scaffold._\n\n"
            "Once wired up, I'll parse your uploaded documents, retrieve the most "
            "relevant passages, and answer grounded in them (with citations)."
        )
        st.session_state.doc_messages.append({"role": "assistant", "content": placeholder_answer})
        st.rerun()
