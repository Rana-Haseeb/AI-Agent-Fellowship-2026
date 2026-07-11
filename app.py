"""
AI Agent Fellowship 2026 — Router / Home.
Entry point for the multipage app. Streamlit auto-lists everything in pages/
in the sidebar; this landing page welcomes evaluators and links to each workspace.
Author: Rana Muhammad Haseeb Khan · Visibility Bots Innovation Lab · Track 2
"""

import streamlit as st
from theme import inject_css, page_icon, render_hero, sidebar_brand, appearance_toggle, nav_links

st.set_page_config(
    page_title="AI Agent Fellowship 2026",
    page_icon=page_icon(),
    layout="wide",
    initial_sidebar_state="expanded",
)

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True
inject_css(st.session_state.dark_mode)

# ---------------------------------------------------------------- Sidebar
with st.sidebar:
    sidebar_brand("Fellowship Hub", "Track 2 · NLP & AI Agents")
    appearance_toggle()
    st.divider()
    nav_links()

# ---------------------------------------------------------------- Main
render_hero(
    "AI Agent Fellowship 2026",
    "Visibility Bots Innovation Lab — Track 2: NLP & AI Agents · by Rana Muhammad Haseeb Khan",
)

st.markdown("#### Available workspaces")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="nav-card">
        <span class="nav-badge">Week 1 · Live</span>
        <h3>🚀 AI Workspace</h3>
        <p>A unified interface for AI models — custom system-prompt personas, prompt
        templates, multiple providers, streaming markdown, multi-session history,
        dark/light mode, and telemetry.</p>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/1_🚀_AI_Workspace.py", label="Open AI Workspace  →", use_container_width=True)

with col2:
    st.markdown("""
    <div class="nav-card">
        <span class="nav-badge">Week 2 · In progress</span>
        <h3>📄 Document Intelligence</h3>
        <p>Upload your documents and query them through a production-grade
        Retrieval-Augmented Generation (RAG) pipeline — parsing, embeddings,
        vector search, and conversational retrieval.</p>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/2_📄_Document_Intelligence.py", label="Open Document Intelligence  →", use_container_width=True)

st.markdown("")
st.caption("Use the sidebar to switch between workspaces at any time. Each page keeps its own independent session state.")
