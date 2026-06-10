"""
FastAPI webhook server.

Provides two endpoints consumed by the Meta WhatsApp Cloud API:

  GET  /webhook   — verification handshake (hub.challenge)
  POST /webhook   — incoming message events

On startup the server initialises the SQLite database and seeds demo data.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse

from app.agent import run_agent
from app.config import WHATSAPP_VERIFY_TOKEN
from app.db import init_db
from app.whatsapp import send_text

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Gym WhatsApp RAG Agent",
    description="Conversational AI assistant for gym prospects and members, integrated with WhatsApp via the Meta Cloud API.",
    version="1.0.0",
)

_log = logging.getLogger("uvicorn")

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@app.on_event("startup")
def _startup() -> None:
    """Initialise the database and seed demo data before accepting requests."""
    init_db()
    _log.info("Database initialised and seeded.")


# ---------------------------------------------------------------------------
# Webhook — verification (GET)
# ---------------------------------------------------------------------------


@app.get("/webhook")
async def webhook_verify(request: Request) -> PlainTextResponse:
    """Handle the WhatsApp webhook verification handshake.

    Meta sends a GET with ``hub.mode``, ``hub.challenge``, and
    ``hub.verify_token``.  We echo back the challenge if the token matches.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    challenge = params.get("hub.challenge")
    token = params.get("hub.verify_token")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        _log.info("Webhook verified successfully.")
        return PlainTextResponse(challenge)

    _log.warning("Webhook verification failed — token mismatch.")
    return PlainTextResponse("Verification failed", status_code=403)


# ---------------------------------------------------------------------------
# Webhook — incoming messages (POST)
# ---------------------------------------------------------------------------


@app.post("/webhook")
async def webhook_handler(request: Request) -> JSONResponse:
    """Receive a WhatsApp message event and return the agent's reply.

    Expected payload structure (Meta Graph API v25.0)::

      {
        "entry": [{
          "changes": [{
            "value": {
              "messages": [{
                "from": "1234567890",
                "text": {"body": "Hi there!"}
              }]
            }
          }]
        }]
      }
    """
    payload = await request.json()

    # Drill into the nested payload.
    try:
        value = payload["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError):
        return JSONResponse({"status": "ignored"}, status_code=200)

    # Filter out status callbacks (sent / delivered / read) — these have no
    # "messages" key and should not trigger the agent.
    if "messages" not in value:
        return JSONResponse({"status": "ignored"}, status_code=200)

    msg = value["messages"][0]
    phone: str = msg["from"]
    body: str = msg.get("text", {}).get("body", "")

    if not body:
        # Non-text message (image, sticker, etc.) — send a polite fallback.
        await send_text(
            phone,
            "I can only read text messages at the moment. "
            "How can I help you with the gym?",
        )
        return JSONResponse({"status": "ok"}, status_code=200)

    _log.info("Incoming message from %s: %s", phone, body)

    # Run the agentic tool-use loop.
    reply = await run_agent(phone, body)

    # Dispatch the reply back to WhatsApp.
    await send_text(phone, reply)

    return JSONResponse({"status": "ok"}, status_code=200)
