"""
AI Workspace — A unified interface for interacting with AI models.
Visibility Bots Innovation Lab · Fellowship Week 1 · Assignment 3
Author: Rana Muhammad Haseeb Khan
"""

import os
import sys
import time

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# Make the repo root importable so `theme` resolves whether run via the router or directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from theme import inject_css, page_icon, render_hero, sidebar_brand, appearance_toggle, nav_links

load_dotenv()

# ==================================================================================
#  PAGE CONFIG
# ==================================================================================
st.set_page_config(
    page_title="AI Workspace",
    page_icon=page_icon(),
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
    "Google AI Studio": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "env": "GOOGLE_API_KEY",
        "note": "🔑 Get a **free** key at aistudio.google.com/apikey (Gemini API).",
        "models": {
            "Gemini 1.5 Flash · Free tier": "gemini-1.5-flash",
            "Gemini 1.5 Pro · Free tier": "gemini-1.5-pro",
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
#  SESSION STATE  (this page keeps its own chat state, independent of other pages)
# ==================================================================================
def _new_chat_obj():
    return {"messages": [], "tokens": 0}

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
    sidebar_brand("AI Workspace", "Unified interface for AI models")

    # ---- Appearance ----
    appearance_toggle()

    st.divider()
    nav_links()
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
render_hero(
    "AI Workspace",
    "A unified, professional interface for interacting with AI models.",
    f"● {provider} · {model_option}",
)

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
