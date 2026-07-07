"""
AI Workspace — A unified interface for interacting with AI models.
Visibility Bots Innovation Lab · Fellowship Week 1 · Assignment 3
Author: Rana Muhammad Haseeb Khan
"""

import os
import time
import json
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ==================================================================================
#  PAGE CONFIG
# ==================================================================================
st.set_page_config(
    page_title="AI Workspace",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==================================================================================
#  MODEL CATALOG & PROVIDERS
# ==================================================================================
PROVIDERS = {
    "OpenAI": {
        "base_url": None,
        "env": "OPENAI_API_KEY",
        "note": "💳 OpenAI models require a **paid** OpenAI API key (platform.openai.com).",
        # label shown in dropdown  ->  actual model id sent to the API
        "models": {
            "GPT-5.5 Pro · Paid": "gpt-5.5-pro",
            "GPT-5.5 · Paid": "gpt-5.5",
            "GPT-5.4 Nano · Paid": "gpt-5.4-nano",
            "GPT Latest (auto) · Paid": "gpt-latest",
            "GPT Mini Latest (auto) · Paid": "gpt-mini-latest",
        },
    },
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "env": "OPENROUTER_API_KEY",
        "note": "🟢 These are **free** models — test at zero cost.",
        "models": {
            "NVIDIA Nemotron 3 Ultra · Free (1M ctx)": "nvidia/nemotron-3-ultra-550b-a55b:free",
            "Qwen3 Coder 480B · Free (best for code)": "qwen/qwen3-coder-480b-a35b:free",
            "OpenAI gpt-oss-120b · Free": "openai/gpt-oss-120b:free",
            "Meta Llama 3.3 70B · Free (reliable)": "meta-llama/llama-3.3-70b-instruct:free",
            "Cohere North Mini Code · Free (fastest)": "cohere/north-mini-code:free",
        },
    },
    "Demo (Simulated)": {
        "base_url": None,
        "env": None,
        "note": None,
        "models": {"demo-sim-1 (no key needed)": "demo-sim-1"},
    },
}

DEFAULT_TEMPLATES = {
    "— None —": "",
    "📝 Summarize Text": "Summarize the following text concisely, capturing the key takeaways as bullet points:\n\n",
    "💻 Explain Code": "Act as a senior software engineer. Explain the following code step-by-step and suggest optimizations:\n\n",
    "💡 Generate Ideas": "Brainstorm 5 unique, creative, and actionable ideas for the following topic:\n\n",
    "✍️ Rewrite Content": "Rewrite the following content for clarity, flow, and professionalism while preserving its meaning:\n\n",
    "🌐 Translate": "Translate the following text into natural, fluent English (or the language I specify):\n\n",
    "📧 Create Email": "Draft a clear, professional, and actionable email based on these points:\n\n",
    "🧠 Brainstorm": "Let's brainstorm deep strategies and conceptual angles for the following problem:\n\n",
}

# ==================================================================================
#  SESSION STATE
# ==================================================================================
def _new_chat_obj():
    return {"messages": [], "tokens": 0, "created": datetime.now().strftime("%H:%M")}

if "sessions" not in st.session_state:
    st.session_state.sessions = {"Chat 1": _new_chat_obj()}
    st.session_state.current = "Chat 1"
if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = "You are a helpful, precise AI assistant."
if "custom_templates" not in st.session_state:
    st.session_state.custom_templates = {}
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

def current_chat():
    return st.session_state.sessions[st.session_state.current]

# ==================================================================================
#  THEME / CSS  (custom professional GUI)
# ==================================================================================
def inject_css(dark: bool):
    if dark:
        c = dict(bg="#0e1117", panel="#161a23", panel2="#1c2230", text="#e6e9ef",
                 muted="#9aa4b2", border="#262d3d", user="#1f6feb", user2="#388bfd",
                 bot="#20293a", accent="#7c5cff", accent2="#00d4ff")
    else:
        c = dict(bg="#f4f6fb", panel="#ffffff", panel2="#f0f3fa", text="#1a1f2e",
                 muted="#5b6472", border="#e2e8f2", user="#2563eb", user2="#3b82f6",
                 bot="#eef2fb", accent="#6d4bff", accent2="#0ea5e9")

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {{
        --bg:{c['bg']}; --panel:{c['panel']}; --panel2:{c['panel2']};
        --text:{c['text']}; --muted:{c['muted']}; --border:{c['border']};
        --user:{c['user']}; --user2:{c['user2']}; --bot:{c['bot']};
        --accent:{c['accent']}; --accent2:{c['accent2']};
    }}

    .stApp {{ background: var(--bg); color: var(--text);
        font-family:'Inter',sans-serif; }}
    /* Hide the menu/toolbar & footer, but KEEP the sidebar expand arrow usable */
    #MainMenu, footer {{ visibility:hidden; }}
    [data-testid="stToolbar"] {{ visibility:hidden; }}
    [data-testid="stDecoration"] {{ display:none; }}
    header[data-testid="stHeader"] {{ background:transparent; }}
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stExpandSidebarButton"] {{
        visibility:visible !important; display:flex !important; z-index:1000; }}
    [data-testid="stSidebarCollapsedControl"] button,
    [data-testid="stExpandSidebarButton"] button {{
        background:var(--panel2)!important; border:1px solid var(--border)!important;
        color:var(--accent)!important; border-radius:8px!important; }}
    .block-container {{ padding-top:1.2rem; max-width:1200px; }}

    /* ---------- Hero banner ---------- */
    .hero {{
        background: linear-gradient(120deg, var(--accent) 0%, var(--accent2) 100%);
        border-radius:18px; padding:22px 28px; margin-bottom:18px;
        box-shadow:0 10px 30px -10px rgba(124,92,255,.55); position:relative; overflow:hidden;
    }}
    .hero::after {{ content:""; position:absolute; top:-40%; right:-5%; width:220px; height:220px;
        background:rgba(255,255,255,.15); border-radius:50%; filter:blur(6px); }}
    .hero h1 {{ color:#fff; font-size:1.9rem; font-weight:800; margin:0; letter-spacing:-.5px; }}
    .hero p {{ color:rgba(255,255,255,.9); margin:.25rem 0 0; font-size:.95rem; font-weight:500; }}
    .hero .pill {{ display:inline-block; background:rgba(255,255,255,.2); color:#fff;
        padding:3px 12px; border-radius:20px; font-size:.72rem; font-weight:600; margin-top:10px;
        backdrop-filter:blur(6px); }}

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {{ background:var(--panel); border-right:1px solid var(--border); }}
    section[data-testid="stSidebar"] * {{ color:var(--text); }}
    .side-card {{ background:var(--panel2); border:1px solid var(--border); border-radius:12px;
        padding:12px 14px; margin-bottom:12px; }}
    .side-title {{ font-size:.7rem; text-transform:uppercase; letter-spacing:1.2px;
        color:var(--muted); font-weight:700; margin-bottom:8px; }}

    /* ---------- Inputs ---------- */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"]>div {{
        background:var(--panel2)!important; color:var(--text)!important;
        border:1px solid var(--border)!important; border-radius:10px!important; }}
    .stTextInput input:focus, .stTextArea textarea:focus {{ border-color:var(--accent)!important;
        box-shadow:0 0 0 2px rgba(124,92,255,.25)!important; }}

    /* ---------- Buttons ---------- */
    .stButton>button, .stDownloadButton>button {{
        background:var(--panel2); color:var(--text); border:1px solid var(--border);
        border-radius:10px; font-weight:600; transition:all .15s ease; }}
    .stButton>button:hover, .stDownloadButton>button:hover {{
        border-color:var(--accent); color:var(--accent); transform:translateY(-1px); }}

    /* ---------- Metric cards ---------- */
    .metric-row {{ display:flex; gap:10px; margin-bottom:6px; }}
    .metric {{ flex:1; background:var(--panel2); border:1px solid var(--border);
        border-radius:12px; padding:10px 12px; text-align:center; }}
    .metric .v {{ font-size:1.15rem; font-weight:800;
        background:linear-gradient(90deg,var(--accent),var(--accent2));
        -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
    .metric .l {{ font-size:.66rem; color:var(--muted); text-transform:uppercase;
        letter-spacing:.5px; font-weight:600; margin-top:2px; }}

    /* ---------- Chat bubbles ---------- */
    [data-testid="stChatMessage"] {{ background:var(--bot); border:1px solid var(--border);
        border-radius:14px; padding:6px 14px; margin:8px 0; box-shadow:0 2px 8px -4px rgba(0,0,0,.2); }}
    [data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li {{ color:var(--text); }}
    [data-testid="stChatMessage"] code {{ font-family:'JetBrains Mono',monospace;
        background:rgba(124,92,255,.12); padding:2px 6px; border-radius:6px; }}
    [data-testid="stChatInput"] textarea {{ background:var(--panel2)!important; color:var(--text)!important; }}

    /* ---------- Empty state ---------- */
    .empty {{ text-align:center; padding:52px 20px; color:var(--muted); }}
    .empty .big {{ font-size:3rem; margin-bottom:8px; }}
    .chip {{ display:inline-block; background:var(--panel2); border:1px solid var(--border);
        color:var(--text); padding:8px 14px; border-radius:22px; margin:5px; font-size:.85rem; font-weight:500; }}
    .stMetric {{ background:var(--panel2); border:1px solid var(--border); border-radius:12px; padding:8px 12px; }}
    </style>
    """, unsafe_allow_html=True)

inject_css(st.session_state.dark_mode)

# ==================================================================================
#  DEMO / SIMULATED ENGINE  (works with zero API keys)
# ==================================================================================
def simulate_response(prompt: str, persona: str) -> str:
    snippet = prompt.strip()[:120] + ("…" if len(prompt.strip()) > 120 else "")
    body = (
        f"> **🧪 Demo Mode** — this is a *simulated* response (no live API key required).\n\n"
        f"Acting as: _{persona}_\n\n"
        f"You asked about:\n> {snippet}\n\n"
        "Here is how a real model would structure an answer:\n\n"
        "1. **Understand** the intent behind your request.\n"
        "2. **Reason** through the relevant steps.\n"
        "3. **Respond** with a clear, formatted answer.\n\n"
    )
    if any(k in prompt.lower() for k in ("code", "python", "function", "bug", "def ")):
        body += "```python\ndef greet(name: str) -> str:\n    return f'Hello, {name}! 👋'\n```\n\n"
    body += "*Add an OpenAI or OpenRouter API key in the sidebar to get live responses.*"
    return body

def stream_words(text: str):
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.012)

# ==================================================================================
#  SIDEBAR
# ==================================================================================
with st.sidebar:
    st.markdown("### 🧠 AI Workspace")
    st.caption("Unified interface for AI models")

    # ---- Appearance ----
    st.markdown('<div class="side-title">Appearance</div>', unsafe_allow_html=True)
    dm = st.toggle("🌙 Dark Mode", value=st.session_state.dark_mode)
    if dm != st.session_state.dark_mode:
        st.session_state.dark_mode = dm
        st.rerun()

    st.divider()

    # ---- Chat Sessions (bonus: multiple sessions) ----
    st.markdown('<div class="side-title">Chat Sessions</div>', unsafe_allow_html=True)
    sess_names = list(st.session_state.sessions.keys())
    picked = st.radio("Active session", sess_names,
                      index=sess_names.index(st.session_state.current), label_visibility="collapsed")
    st.session_state.current = picked

    cs1, cs2 = st.columns(2)
    if cs1.button("➕ New", use_container_width=True):
        new_name = f"Chat {len(st.session_state.sessions) + 1}"
        st.session_state.sessions[new_name] = _new_chat_obj()
        st.session_state.current = new_name
        st.rerun()
    if cs2.button("🗑️ Delete", use_container_width=True, disabled=len(sess_names) <= 1):
        del st.session_state.sessions[st.session_state.current]
        st.session_state.current = list(st.session_state.sessions.keys())[0]
        st.rerun()

    st.divider()

    # ---- Connection ----
    st.markdown('<div class="side-title">Model & Connection</div>', unsafe_allow_html=True)
    provider = st.selectbox("Provider", list(PROVIDERS.keys()))
    pcfg = PROVIDERS[provider]
    demo_mode = provider == "Demo (Simulated)"

    # Pick from the curated list, or type any model ID manually
    manual = st.toggle("✏️ Enter model ID manually", value=False, disabled=demo_mode,
                       help="Type any exact model ID supported by this provider.")
    if manual and not demo_mode:
        model_option = st.text_input(
            "Model ID", value=list(pcfg["models"].values())[0],
            placeholder="e.g. google/gemma-4-31b:free",
        )
    else:
        model_label = st.selectbox("Model", list(pcfg["models"].keys()))
        model_option = pcfg["models"][model_label]

    if pcfg.get("note") and not demo_mode:
        st.caption(pcfg["note"])

    if demo_mode:
        api_key_input = ""
        st.info("Demo mode active — no API key needed.", icon="🧪")
    else:
        api_key_input = st.text_input(
            "API Key", value=os.getenv(pcfg["env"], ""), type="password",
            help="Stored only in this session — never saved to disk.",
        )

    st.divider()

    # ---- Persona / system prompt ----
    st.markdown('<div class="side-title">System Prompt (Persona)</div>', unsafe_allow_html=True)
    persona_presets = {
        "Custom": st.session_state.system_prompt,
        "👨‍💻 Software Engineer": "You are a professional senior software engineer. Give precise, production-grade, well-explained answers with code where useful.",
        "🔬 AI Research Assistant": "You are an AI research assistant. Be rigorous, cite reasoning, and structure answers academically.",
        "✍️ Creative Writer": "You are a creative writer with a vivid, engaging voice.",
        "📊 Data Analyst": "You are a data analyst. Be quantitative, structured, and insight-driven.",
    }
    preset = st.selectbox("Preset", list(persona_presets.keys()))
    system_prompt = st.text_area(
        "Define the AI's role", value=persona_presets[preset], height=110,
        help="Controls the model's behavior behind the scenes.",
    )
    if system_prompt != st.session_state.system_prompt:
        st.session_state.system_prompt = system_prompt

    st.divider()

    # ---- Templates (bonus: save custom templates) ----
    st.markdown('<div class="side-title">Prompt Templates</div>', unsafe_allow_html=True)
    all_templates = {**DEFAULT_TEMPLATES, **st.session_state.custom_templates}
    selected_template = st.selectbox("Quick template", list(all_templates.keys()))
    with st.expander("💾 Save a custom template"):
        t_name = st.text_input("Template name", placeholder="e.g. 🐞 Debug Helper")
        t_body = st.text_area("Template prompt", placeholder="Find and fix bugs in:\n\n", height=70)
        if st.button("Save Template", use_container_width=True):
            if t_name.strip() and t_body.strip():
                st.session_state.custom_templates[t_name.strip()] = t_body
                st.toast(f"Saved template: {t_name}", icon="💾")
                st.rerun()
            else:
                st.warning("Both name and prompt are required.")

# ==================================================================================
#  MAIN — HERO + TELEMETRY
# ==================================================================================
st.markdown(f"""
<div class="hero">
    <h1>🧠 AI Workspace</h1>
    <p>A unified, professional interface for interacting with AI models.</p>
    <span class="pill">● {provider} · {model_option}</span>
</div>
""", unsafe_allow_html=True)

chat = current_chat()
msg_count = len([m for m in chat["messages"] if m["role"] == "user"])
st.markdown(f"""
<div class="metric-row">
    <div class="metric"><div class="v">{msg_count}</div><div class="l">Messages</div></div>
    <div class="metric"><div class="v">{chat['tokens']}</div><div class="l">Tokens (est.)</div></div>
    <div class="metric"><div class="v">{len(st.session_state.sessions)}</div><div class="l">Sessions</div></div>
    <div class="metric"><div class="v">{'🧪' if demo_mode else '🔌'}</div><div class="l">{'Demo' if demo_mode else 'Live'}</div></div>
</div>
""", unsafe_allow_html=True)

# ---- Action row: export / clear ----
a1, a2, a3 = st.columns([1, 1, 4])
if a1.button("🗑️ Clear Chat", use_container_width=True):
    chat["messages"] = []
    chat["tokens"] = 0
    st.rerun()

if chat["messages"]:
    export_md = f"# AI Workspace — {st.session_state.current}\n\n"
    export_md += f"*System prompt:* {st.session_state.system_prompt}\n\n---\n\n"
    for m in chat["messages"]:
        who = "🧑 **You**" if m["role"] == "user" else "🤖 **Assistant**"
        export_md += f"### {who}\n\n{m['content']}\n\n"
    a2.download_button("📥 Export", export_md, file_name=f"{st.session_state.current}.md",
                       mime="text/markdown", use_container_width=True)
else:
    a2.button("📥 Export", use_container_width=True, disabled=True)

# ==================================================================================
#  CHAT HISTORY RENDER
# ==================================================================================
if not chat["messages"]:
    st.markdown("""
    <div class="empty">
        <div class="big">💬</div>
        <div style="font-size:1.15rem;font-weight:600;">Start a conversation</div>
        <div style="margin-top:6px;">Ask anything, pick a template, or switch on Demo Mode to try it instantly.</div>
        <div style="margin-top:18px;">
            <span class="chip">📝 Summarize</span><span class="chip">💻 Explain Code</span>
            <span class="chip">💡 Generate Ideas</span><span class="chip">🌐 Translate</span>
            <span class="chip">📧 Create Email</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

for m in chat["messages"]:
    avatar = "🧑" if m["role"] == "user" else "🤖"
    with st.chat_message(m["role"], avatar=avatar):
        st.markdown(m["content"])
        if m.get("meta"):
            st.caption(m["meta"])

# ==================================================================================
#  CHAT INPUT PIPELINE
# ==================================================================================
placeholder = "Ask anything…" if selected_template == "— None —" else "Template active — add your text here…"
user_input = st.chat_input(placeholder)

if user_input is not None:
    # Error handling: empty prompt
    if not user_input.strip():
        st.error("⚠️ Cannot send an empty prompt. Please type something.")
    else:
        final_prompt = user_input
        if selected_template != "— None —":
            final_prompt = all_templates[selected_template] + user_input

        chat["messages"].append({"role": "user", "content": final_prompt})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(final_prompt)

        with st.chat_message("assistant", avatar="🤖"):
            placeholder_box = st.empty()

            # ---------- DEMO MODE ----------
            if demo_mode:
                sim = simulate_response(final_prompt, st.session_state.system_prompt)
                acc = ""
                t0 = time.time()
                for chunk in stream_words(sim):
                    acc += chunk
                    placeholder_box.markdown(acc + "▌")
                latency = time.time() - t0
                chat["messages"].append({
                    "role": "assistant", "content": sim,
                    "meta": f"⏱️ {latency:.2f}s · 🧪 Demo (simulated) · 🎯 {model_option}",
                })
                chat["tokens"] += int(len(final_prompt.split()) * 1.3 + len(sim.split()) * 1.3)
                st.rerun()  # repaint so metric cards reflect the new totals

            # ---------- ERROR: missing key ----------
            elif not api_key_input:
                st.error("❌ **Missing API key.** Add your key in the sidebar, or switch Provider to "
                         "**Demo (Simulated)** to try the app without one.")

            # ---------- LIVE API ----------
            else:
                responded = False
                try:
                    client = OpenAI(api_key=api_key_input, base_url=pcfg["base_url"])
                    api_messages = [{"role": "system", "content": st.session_state.system_prompt}]
                    api_messages += [{"role": m["role"], "content": m["content"]} for m in chat["messages"]]

                    t0 = time.time()
                    stream = client.chat.completions.create(
                        model=model_option, messages=api_messages,
                        temperature=0.7, stream=True,
                    )
                    acc = ""
                    for part in stream:
                        delta = part.choices[0].delta.content or ""
                        acc += delta
                        placeholder_box.markdown(acc + "▌")
                    latency = time.time() - t0

                    chat["messages"].append({
                        "role": "assistant", "content": acc,
                        "meta": f"⏱️ {latency:.2f}s · 🔌 {provider} · 🎯 {model_option}",
                    })
                    chat["tokens"] += int(len(final_prompt.split()) * 1.3 + len(acc.split()) * 1.3)
                    responded = True

                except Exception as e:
                    err = str(e)
                    low = err.lower()
                    if "api_key" in low or "authentication" in low or "401" in low or "invalid_api_key" in low:
                        st.error("🔑 **Invalid API key.** Please check your credentials and try again.")
                    elif "404" in low or "no endpoints" in low or "not found" in low:
                        st.error(f"🚫 **Model unavailable.** `{model_option}` isn't offered by "
                                 f"{provider} right now. Pick a different model from the sidebar.")
                    elif "429" in low or "rate limit" in low or "quota" in low:
                        st.error("⏳ **Rate limit / quota reached.** Wait a moment or try another model.")
                    elif "connection" in low or "timeout" in low or "network" in low:
                        st.error("🌐 **Connection failed.** Check your internet connection and retry.")
                    else:
                        st.error(f"⚠️ **Something went wrong:** {err}")

                if responded:
                    st.rerun()  # repaint so metric cards reflect the new totals
