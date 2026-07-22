# 🚀 AI Agent Fellowship 2026

### _Visibility Bots Innovation Lab — Track 2: NLP & AI Agents_

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)
![Git](https://img.shields.io/badge/git-%23F05033.svg?style=for-the-badge&logo=git&logoColor=white)

Welcome to my official engineering repository for the **Visibility Bots Innovation Lab AI Summer Fellowship**. This space documents my transition from an AI consumer to an AI systems builder—housing enterprise-ready prototypes, system architecture schematics, and production-grade research logs.

> 🛠️ **Engineering Directive:** Week 1 focuses on building core developer habits, mastering deterministic LLM outputs, establishing error boundaries, and deploying unified workspace dashboards.

---

## 👤 Engineering Profile

### Core Information

- 🆔 **Name:** Rana Muhammad Haseeb Khan
- 🎓 **University:** FAST National University of Computer and Emerging Sciences _(Chiniot-Faisalabad Campus)_
- 🔍 **Current Focus:** Software Engineering — 6th Semester (Expected Graduation: 2027)
- 🎯 **Fellowship Track:** Track 2: NLP & AI Agents

### 🚀 Career Goals & Trajectory

I am a Software Engineer dedicated to architecting scalable, high-throughput intelligent software systems. My career trajectory focuses on bridging the gap between traditional robust backend microservices and next-generation autonomous models. I aim to build latency-optimized applications, full-stack data platforms, and real-time stateful multi-agent systems designed for predictable production deployment.

---

## 🛠️ Core Technical Stack

| Category                     | Technologies & Tools                                                     |
| :--------------------------- | :----------------------------------------------------------------------- |
| **Languages & Core**         | Python `3.11+`, JavaScript, TypeScript, PHP                              |
| **Frontend Frameworks**      | Next.js, React, Streamlit, Tailwind CSS                                  |
| **Backend & Databases**      | Node.js (MERN Stack), REST APIs, Supabase, MongoDB                       |
| **AI & Workflow Automation** | OpenAI API, Google Gemini API, LangChain, RAG Frameworks, n8n Automation |
| **DevOps & Environments**    | Docker, Git/GitHub, Linux (Kali/Ubuntu dual-boot systems)                |

---

## 🖥️ AI Workspace — Live Application

**AI Workspace** is a unified, professional interface for interacting with AI models — built with Streamlit. It supports multiple providers (OpenRouter · OpenAI · a keyless Demo mode), custom system-prompt personas, prompt templates, streaming markdown responses, multiple chat sessions, dark/light mode, token & latency telemetry, and robust error handling.

### 📸 Screenshots

**Dark Mode — Home**
![AI Workspace — Home (Dark Mode)](docs/week1/screenshots/01-home-dark.png)

**Live Conversation (Demo Mode) — streaming markdown & telemetry**
![AI Workspace — Demo Conversation](docs/week1/screenshots/02-demo-chat.png)

**Light Mode — Home**
![AI Workspace — Home (Light Mode)](docs/week1/screenshots/03-light-mode.png)

### ⚙️ Quick Start

Full instructions in **[INSTALLATION.md](INSTALLATION.md)**.

```bash
pip install -r requirements.txt
streamlit run app.py
```

> 🧪 No API key? Select **Demo (Simulated)** as the provider to try the full UI instantly.

---

## 🎯 Specific Fellowship Learning Goals

1. **Stateful Agentic Architecture:** Evolve past elementary API wrappers to engineer autonomous, deterministic loop frameworks using advanced contextual memory layers and self-reflection mechanics.
2. **Production-Grade Prompt Engineering:** Master advanced structured output controls (forcing rigid JSON schemas via Pydantic parsing) and structural tool execution patterns while maintaining strict token/cost efficiency.
3. **Rigorous System Documentation:** Cultivate clean, industry-standard code discipline by backing all structural updates with comprehensive sequence flowcharts, metrics logs, and detailed research papers.

---

## 📂 Fellowship Phase Tracking

### 🗓️ Week 1 — From AI User to AI Builder

- **Assignment 1:** Professional Environment Validation & Repository Architecture
- **Assignment 2:** [Technical Research Report](docs/week1/RESEARCH_REPORT.md) — _"The Evolution of AI Agents and Modern AI Engineering"_
- **Assignment 3:** [AI Workspace](pages/1_🚀_AI_Workspace.py) — _Unified UI with model toggling and custom system-prompt profiles._
- **Assignment 4:** [Prompt Engineering Experiments](docs/week1/PROMPT_EXPERIMENTS.md) — _Role, CoT, Few-Shot, JSON, and optimization trials._
- **Assignment 5:** [Application Architecture](docs/week1/ARCHITECTURE.md) — _Request/response pipeline diagrams._
- **Assignment 6:** [Builder Journal](docs/week1/BUILDER_JOURNAL.md)

### 🗓️ Week 2 — Production-Grade RAG Application

- **Assignment 1:** [Document Intelligence](pages/2_📄_Document_Intelligence.py) — _Enterprise RAG platform (upload → index → retrieve → grounded answers with citations)._
- **Assignment 2:** [Research Report](docs/week2/RESEARCH_REPORT.md) — _"Designing Enterprise Retrieval-Augmented Generation Systems"_
- **Assignment 3:** [RAG Architecture](docs/week2/ARCHITECTURE.md) — _Full 10-stage retrieval pipeline._
- **Assignment 4:** [Experiments](docs/week2/EXPERIMENTS.md) ✅ — _Measured trials on chunk size, overlap, prompt templates, and embedding models._

> **📊 Key experimental results** (23 live LLM calls, measured end-to-end):
>
> - **Chunk size is decisive.** On the 5-part "Key Elements" question the model stated **1 of 5**
>   elements at chunk 300 and **all 5** at chunk 1000 (answer coverage **0.20 → 1.00**) — proving the
>   earlier failure was *retrieval fragmentation*, not bad ingestion.
> - **Grounding holds.** The out-of-document control question was correctly refused in **3/3** runs.
> - **Templates cut both ways.** The raw question *retrieves* best (+13% similarity) but *answers*
>   worst; templates do the reverse. The app now **embeds the raw question and templates only the
>   LLM prompt** — capturing both wins.
> - **Better ranking beats better recall.** `bge-small` scored *lower* keyword recall than `MiniLM`
>   yet produced **better answers** (0.90 vs 0.80) — retrieval proxies can mislead.
>
> Full methodology, verbatim answers, and limitations → **[docs/week2/EXPERIMENTS.md](docs/week2/EXPERIMENTS.md)**
- **Assignment 5:** [Builder Journal](docs/week2/BUILDER_JOURNAL.md)

### 📦 Repository Contents

| Deliverable | Week 1 | Week 2 |
| :---------- | :----- | :----- |
| Research Report | [📄](docs/week1/RESEARCH_REPORT.md) | [📄](docs/week2/RESEARCH_REPORT.md) |
| Architecture | [📄](docs/week1/ARCHITECTURE.md) | [📄](docs/week2/ARCHITECTURE.md) |
| Experiments | [📄](docs/week1/PROMPT_EXPERIMENTS.md) | [📄](docs/week2/EXPERIMENTS.md) |
| Builder Journal | [📄](docs/week1/BUILDER_JOURNAL.md) | [📄](docs/week2/BUILDER_JOURNAL.md) |
| Screenshots | [🖼️](docs/week1/screenshots/) | [🖼️](docs/week2/screenshots/) |

**Shared:** [Source Code](app.py) · [requirements.txt](requirements.txt) · [Installation Guide](INSTALLATION.md)

---

_Engineered with focus by Rana Muhammad Haseeb Khan during the Visibility Bots Fellowship — 2026._
