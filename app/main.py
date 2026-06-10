"""
FastAPI webhook server.

Endpoints:

  GET  /health   — Docker / load-balancer healthcheck
  GET  /webhook  — WhatsApp verification handshake (hub.challenge)
  POST /webhook  — incoming WhatsApp message events

On startup the server initialises the SQLite database and seeds demo data.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse

from app.agent import run_agent
from app.config import WHATSAPP_VERIFY_TOKEN
from app.db import init_db
from app.models import RateLimiter
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

# Sliding-window rate limiter: max 5 messages per 10-second window per phone.
_rate_limiter = RateLimiter(max_requests=5, window_seconds=10.0)

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@app.on_event("startup")
def _startup() -> None:
    """Initialise the database and seed demo data before accepting requests."""
    init_db()
    _log.info("Database initialised and seeded.")


# ---------------------------------------------------------------------------
# Healthcheck
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> PlainTextResponse:
    """Simple healthcheck — always returns 200."""
    return PlainTextResponse("ok")


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
async def webhook_handler(request: Request, background: BackgroundTasks) -> JSONResponse:
    """Receive a WhatsApp message event and return the agent's reply.

    Returns HTTP 200 immediately to satisfy Meta's 20-second webhook
    timeout, then processes the message asynchronously in the background.
    This prevents duplicate processing when Meta retries a timed-out request.

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
    except (KeyError, IndexError, TypeError):
        _log.warning("Unrecognised webhook payload structure: %s",
                      str(payload)[:500])
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

    # Rate-limit check — return 200 silently so Meta doesn't retry.
    if not _rate_limiter.is_allowed(phone):
        _log.warning("Rate limit exceeded for %s", phone)
        return JSONResponse({"status": "ok"}, status_code=200)

    # Process in the background so Meta gets a fast 200 response.  If the
    # agent takes >20s Meta would otherwise retry the same message, risking
    # duplicate bookings.
    background.add_task(_process_message, phone, body)

    return JSONResponse({"status": "ok"}, status_code=200)


# ---------------------------------------------------------------------------
# Background message processing
# ---------------------------------------------------------------------------

async def _process_message(phone: str, body: str) -> None:
    """Run the agent loop with a timeout and send the reply back.

    Called as a FastAPI background task so the webhook handler can return
    immediately.
    """
    try:
        reply = await asyncio.wait_for(
            run_agent(phone, body),
            timeout=25.0,
        )
    except asyncio.TimeoutError:
        _log.error("Agent timed out for %s", phone)
        reply = (
            "I'm sorry, I'm taking longer than expected. "
            "Please try again or contact the front desk."
        )
    except Exception:
        _log.exception("Agent failed for %s", phone)
        reply = (
            "Something went wrong on our end. "
            "Please try again in a moment."
        )

    try:
        await send_text(phone, reply)
    except Exception:
        _log.exception("Failed to send WhatsApp reply to %s", phone)
