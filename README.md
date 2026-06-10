<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Claude-Sonnet%204.6-black?style=flat-square&logo=anthropic" alt="Claude">
  <img src="https://img.shields.io/badge/WhatsApp-Cloud%20API%20v25.0-25D366?style=flat-square&logo=whatsapp" alt="WhatsApp">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
</p>

<h1 align="center">🏋️ Gym WhatsApp RAG Agent</h1>

<p align="center">
  <strong>Production-grade conversational AI for gyms — fully agentic, RAG-grounded, WhatsApp-native.</strong>
</p>

<p align="center">
  A FastAPI microservice powered by <strong>Claude tool-calling</strong> and <strong>semantic vector search</strong> that handles the full gym customer lifecycle — from prospect enquiries to class bookings — entirely within WhatsApp.
</p>

---

## ✨ Why This Exists

Most gym "chatbots" are rule-based trees that break the moment a user deviates from the script. This agent is different:

- **Agentic** — Claude autonomously decides which tools to call, in what order, based on user intent. No hard-coded flows.
- **Grounded** — A retrieval-augmented generation pipeline injects your gymʼs actual knowledge (pricing, policies, trainers) into every response. Zero hallucination.
- **Transactional** — Book trial classes, register for sessions, and look up membership details as side effects of a conversation.
- **Multimodal** — Sends trainer photos and video directly into the WhatsApp thread via the native media upload pipeline.

---

## 🧠 Architecture

```
WhatsApp Message
      │
      ▼
┌─────────────────────────────────────────────┐
│                 FastAPI Webhook              │
│           GET /webhook  (verify)             │
│           POST /webhook (messages)           │
└──────────────────┬──────────────────────────┘
                   │
      ┌────────────▼────────────┐
      │     AGENTIC LOOP        │
      │   (Claude Sonnet 4.6)   │
      │                        │
      │  • Conversation memory  │
      │  • Tool selection       │
      │  • Multi-turn chaining  │◄──── 15-round safety cap
      └────┬──────┬──────┬─────┘
           │      │      │
    ┌──────▼┐ ┌───▼──┐ ┌─▼──────────┐
    │  RAG  │ │ SQL  │ │ WhatsApp    │
    │       │ │      │ │ Media API   │
    │ MiniLM│ │Lite  │ │             │
    │ NumPy │ │      │ │ Upload → ID │
    └───────┘ └──────┘ └─────────────┘
```

### The Five Layers

| # | Layer | Technology | Responsibility |
|---|-------|-----------|----------------|
| 1 | **Transport** | FastAPI + Uvicorn + Cloudflare Tunnel | HTTPS webhook, payload parsing, verification handshake |
| 2 | **Orchestration** | Claude API (tool-use) | Tool-calling loop, conversation state, response synthesis |
| 3 | **Retrieval** | Sentence Transformers + NumPy | Semantic chunk search over gym knowledge corpus |
| 4 | **Data** | SQLite (WAL mode) | Members, class schedule, trial bookings, registrations |
| 5 | **Response** | WhatsApp Cloud API v25.0 | Text + image + video delivery, media upload pipeline |

---

## 🔧 Tools The Agent Can Use

| Tool | Trigger | Side Effect |
|------|---------|-------------|
| `search_knowledge_base` | Any general gym question | RAG retrieval from `knowledge.txt` |
| `get_membership_details` | "What's my plan?" | SQL `SELECT` on members table |
| `get_next_class` | "When is yoga?" | SQL query with date filter |
| `register_for_class` | "Sign me up for that" | SQL `INSERT` into registrations |
| `book_trial_class` | "I want to try a class" | SQL `INSERT` into trial_bookings |
| `send_trainer_profiles` | "Who are the trainers?" | WhatsApp image media upload |

Claude can **chain tools** across turns — a user says "when is yoga?" followed by "book me in" and Claude resolves the anaphoric reference using the prior `get_next_class` result still in conversation history.

---

## 🚀 Quick Start

> 📖 **Complete step-by-step guide with screenshots?** See **[GET_STARTED.md](GET_STARTED.md)** — walks you through every step from zero to a working bot.

### Prerequisites
- Python 3.12+
- [Anthropic API key](https://console.anthropic.com/)
- [Meta Developer account](https://developers.facebook.com/) with a WhatsApp Business App
- [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) (`cloudflared`)

### 1. Clone & Configure

```bash
git clone https://github.com/amitsehgal29/whatsappagent
cd whatsappagent
# Edit .env with your API keys (see GET_STARTED.md for where to get them)
```

### 2. Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run

```bash
uvicorn app.main:app --port 8000
```

### 4. Expose

```bash
cloudflared tunnel --url http://localhost:8000
# Copy the generated HTTPS URL → paste into Meta Dashboard as webhook callback
```

### 5. Subscribe to Events

```bash
curl -X POST \
  https://graph.facebook.com/v25.0/YOUR_WABA_ID/subscribed_apps \
  -H "Authorization: Bearer YOUR_WHATSAPP_TOKEN"
```

Now message your WhatsApp Business number — the agent replies.

---

## 🐳 Docker

```bash
docker build -t gym-whatsapp-agent .
docker run -p 8000:8000 --env-file .env gym-whatsapp-agent
```

---

## 📁 Project Structure

```
whatsappagent/
├── app/
│   ├── __init__.py      # Package marker
│   ├── main.py          # FastAPI app & webhook endpoints
│   ├── config.py        # Env-var configuration
│   ├── agent.py         # Claude tool-use loop & media handler
│   ├── tools.py         # 6 tool implementations + JSON schemas
│   ├── rag.py           # Semantic search (MiniLM + NumPy)
│   ├── whatsapp.py      # WhatsApp Cloud API helpers (text/image/video)
│   ├── db.py            # SQLite schema, seed data, query helpers
│   ├── memory.py        # Per-phone conversation history store
│   └── models.py        # Pydantic validation models
├── data/
│   └── knowledge.txt    # Gym knowledge corpus (paragraph-chunked)
├── media/
│   └── .gitkeep         # Trainer images & videos (git-ignored)
├── requirements.txt     # Python dependency manifest
├── Dockerfile           # Production container image
├── .env                 # Secrets (NEVER committed)
├── .gitignore
└── README.md
```

---

## ⚙️ Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `WHATSAPP_TOKEN` | Meta access token |
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp phone number ID |
| `WHATSAPP_WABA_ID` | WhatsApp Business Account ID |
| `WHATSAPP_VERIFY_TOKEN` | Arbitrary string for webhook verification |
| `GRAPH_API_VERSION` | Default: `v25.0` |
| `MODEL` | Default: `claude-sonnet-4-6` |
| `DEMO_MEMBER_PHONE` | Your WhatsApp number (E.164, no `+`) for demo seed |

---

## 🧪 Verification

```bash
# All imports clean
python3 -c "from app import config, models, db, rag, tools, whatsapp, memory, agent, main"

# Database
python3 -c "from app.db import init_db; init_db(); print('✓ DB ready')"

# RAG retrieval
python3 -c "from app.rag import search; print(search('yoga classes')[:200])"

# Webhook endpoint
curl "http://localhost:8000/webhook?hub.mode=subscribe&hub.challenge=42&hub.verify_token=test"
```

---

## 🛤️ Roadmap

- [ ] Redis-backed conversation memory (survive restarts)
- [ ] PostgreSQL migration for multi-tenant gym deployments
- [ ] Qdrant / Pinecone vector store for sub-10ms retrieval on large corpora
- [ ] LangGraph state machine for complex multi-agent workflows
- [ ] Web dashboard for conversation analytics and CRM
- [ ] Multi-language support (the RAG corpus already works in any language)

---

## 📄 License

MIT © 2026 [Amit Sehgal](https://github.com/amitsehgal29)

---

<p align="center">
  <sub>Built with ❤️ using Claude, FastAPI, and the WhatsApp Cloud API</sub>
</p>
