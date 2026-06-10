# CLAUDE.md — Gym WhatsApp RAG Agent

## Project overview

FastAPI microservice that powers an AI gym assistant on WhatsApp. Uses Claude
tool-calling (6 tools), RAG with sentence-transformers + NumPy, SQLite, and the
Meta WhatsApp Cloud API.

## How to run

```bash
source venv/bin/activate
uvicorn app.main:app --port 8000 --host 0.0.0.0
```

Expose with Cloudflare Tunnel (needed for WhatsApp webhook):

```bash
cloudflared tunnel --url http://localhost:8000
```

## How to verify / test

```bash
source venv/bin/activate

# All imports clean
python3 -c "from app import config, models, db, rag, tools, whatsapp, memory, agent, main"

# DB init and seed
python3 -c "from app.db import init_db; init_db(); print('OK')"

# RAG search
python3 -c "from app.rag import search; print(search('yoga classes')[:200])"

# Rate limiter
python3 -c "
from app.models import RateLimiter
rl = RateLimiter(max_requests=3, window_seconds=1.0)
assert rl.is_allowed('a') and rl.is_allowed('a') and rl.is_allowed('a')
assert not rl.is_allowed('a')  # rate limited
assert rl.is_allowed('b')       # different phone, not limited
print('OK')
"

# Webhook endpoints (start server first, then):
curl -s http://localhost:8000/health
# → "ok"

curl -s "http://localhost:8000/webhook?hub.mode=subscribe&hub.challenge=TEST&hub.verify_token=your-custom-verify-token-here"
# → "TEST" (echoes challenge on correct token)

curl -s "http://localhost:8000/webhook?hub.mode=subscribe&hub.challenge=999&hub.verify_token=wrong"
# → "Verification failed" (403 on wrong token)

curl -s -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"entry":[{"changes":[{"value":{"metadata":{}}}]}]}'
# → {"status":"ignored"} (status callbacks are filtered)
```

## Key gotchas (verified during build)

### 1. Server takes 10–15 seconds to start
The `all-MiniLM-L6-v2` sentence-transformer model (and its PyTorch dependency)
take ~10 seconds to load on first import. The Uvicorn "Application startup
complete" message only appears after this. **Always wait 10–15 seconds after
starting the server before running tests.**

### 2. Port conflicts from stale processes
`pkill -f uvicorn` before starting a fresh server. Multiple `uvicorn app.main:app`
processes on the same port produce "address already in use" errors.

### 3. Python 3.9 LibreSSL warning (macOS)
```
NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+
```
Harmless on macOS. Upgrade to Python 3.12+ to eliminate, or ignore.

### 4. `.env` path is now explicit
`app/config.py` resolves `.env` relative to the config file's location, not CWD.
The server works regardless of which directory it's started from.

### 5. Webhook returns 200 before processing
Messages are handled via FastAPI `BackgroundTasks`. Meta's webhook gets a 200
response within milliseconds, preventing duplicate message processing from
Meta's 20-second retry behavior. The agent has a 25-second internal timeout.

### 6. Rate limiter prevents abuse
5 messages per 10-second window per phone. Rate-limited messages return 200
silently so Meta doesn't retry them.

### 7. DB has duplicate and capacity guards
- `insert_trial_booking`: rejects same phone + date + time
- `insert_class_registration`: rejects if class is full or already registered
- Both raise `ValueError` with user-friendly messages

## Architecture

```
WhatsApp → Meta Graph API → Cloudflare Tunnel → FastAPI
                                                    ├── GET  /webhook  (verify)
                                                    ├── POST /webhook  (messages)
                                                    └── GET  /health   (Docker)

POST /webhook → BackgroundTasks → run_agent() [25s timeout]
                                      ├── Claude API (tool-use loop, 15 rounds)
                                      ├── RAG search (MiniLM + NumPy dot product)
                                      ├── SQLite queries (4 tables)
                                      └── WhatsApp send (text / image / video)
```

## File map

| File | Role |
|------|------|
| `app/main.py` | FastAPI app, webhook, health, rate limiter, background tasks |
| `app/agent.py` | Claude tool-use loop, system prompt, media handler |
| `app/tools.py` | 6 tool impls + Anthropic JSON schemas + dispatcher |
| `app/rag.py` | Sentence-transformer encoding, NumPy cosine similarity search |
| `app/db.py` | SQLite schema (4 tables), seed data, query helpers, validation |
| `app/whatsapp.py` | WhatsApp Cloud API: send text, image, video (async) |
| `app/memory.py` | Per-phone conversation history (dict-based, replace with Redis in prod) |
| `app/config.py` | Env vars from `.env` with explicit path |
| `app/models.py` | `RateLimiter` (sliding-window per-phone) |
| `data/knowledge.txt` | Gym knowledge corpus, chunked at paragraph boundaries |
| `Dockerfile` | python:3.12-slim, non-root user, healthcheck on /health |

## Dependencies

```
fastapi, uvicorn, anthropic, httpx, python-dotenv,
numpy, sentence-transformers, pydantic
```

The sentence-transformers package pulls in PyTorch (~75 MB) and transformers
(~12 MB). First install takes 2–3 minutes on a fast connection.
