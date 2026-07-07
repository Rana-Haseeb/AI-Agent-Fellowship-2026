# ⚙️ Installation Guide — AI Workspace

A step-by-step guide to run the **AI Workspace** app locally.

---

## 1. Prerequisites

- **Python 3.10+** (developed on 3.13)
- **pip** and **git**
- An API key from **[OpenRouter](https://openrouter.ai/keys)** (free models available) *or* **[OpenAI](https://platform.openai.com/api-keys)** (paid) — optional, since the app also ships a keyless **Demo mode**.

---

## 2. Clone the Repository

```bash
git clone https://github.com/Rana-Haseeb/AI-Agent-Fellowship-2026.git
cd AI-Agent-Fellowship-2026
```

---

## 3. Create a Virtual Environment (recommended)

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 4. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 5. Configure Your API Key

Copy the example env file and add your key(s):

```bash
cp .env.example .env
```

Then edit `.env`:

```env
OPENROUTER_API_KEY=sk-or-your-key-here
OPENAI_API_KEY=sk-your-openai-key-here   # optional
```

> 🔒 The `.env` file is git-ignored and never committed. You can also paste a key directly into the app's sidebar at runtime.
> 🧪 **No key? No problem.** Select **Demo (Simulated)** as the provider to try the full UI without any API key.

---

## 6. Run the App

```bash
streamlit run app.py
```

The app opens automatically at **http://localhost:8501**.

---

## 7. Using the App

1. Pick a **Provider** (OpenRouter · OpenAI · Demo) and a **Model** in the sidebar — or toggle **✏️ Enter model ID manually**.
2. Optionally set a **System Prompt** persona and choose a **Prompt Template**.
3. Type your question in the chat box and press **Enter**.
4. Use the sidebar for **Dark Mode**, **multiple chat sessions**, **export**, and **custom templates**.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Missing API key` | Add a key in the sidebar, or switch Provider to **Demo (Simulated)**. |
| `Model unavailable (404)` | The model ID is stale — pick another, or use **manual model entry**. |
| `Rate limit (429)` | Free models are busy; the app auto-rotates, or try a different model. |
| Port 8501 in use | Run `streamlit run app.py --server.port 8502`. |

---

*Installation guide by Rana Muhammad Haseeb Khan · Visibility Bots Fellowship — 2026.*
