"""
WhatsApp Cloud API integration layer.

Provides async helpers for sending text, image, and video messages via the
Meta Graph API.  Media delivery follows the two-step upload-then-reference
flow required by the WhatsApp platform:

  1. POST the raw file bytes to /{PHONE_NUMBER_ID}/media
  2. Send a message referencing the returned *media_id*

All functions are async and use ``httpx.AsyncClient`` for non-blocking I/O.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from app.config import (
    GRAPH_API_VERSION,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_TOKEN,
)

# ---------------------------------------------------------------------------
# Base URL — assembled once at module level
# ---------------------------------------------------------------------------
_BASE: str = (
    f"https://graph.facebook.com/{GRAPH_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}"
)
_MESSAGES_URL: str = f"{_BASE}/messages"
_MEDIA_URL: str = f"{_BASE}/media"

# Shared auth header sent with every request.
_AUTH: dict[str, str] = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}

# ---------------------------------------------------------------------------
# Root for local media files
# ---------------------------------------------------------------------------
MEDIA_ROOT: Path = Path(__file__).resolve().parent.parent / "media"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def send_text(phone: str, text: str) -> dict:
    """Send a plain-text WhatsApp message to *phone*."""
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "text",
        "text": {"body": text},
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _MESSAGES_URL,
            headers=_AUTH,
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def send_image(phone: str, image_path: str | Path, caption: str = "") -> dict:
    """Upload a local image and send it as a WhatsApp image message.

    Parameters
    ----------
    phone : str
        Recipient phone in E.164 format.
    image_path : str or Path
        Path to the image file on disk (jpg / png).
    caption : str
        Optional caption text displayed below the image.
    """
    media_id: str = await _upload_media(image_path, "image/jpeg")

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "image",
        "image": {"id": media_id, "caption": caption} if caption else {"id": media_id},
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _MESSAGES_URL,
            headers={**_AUTH, "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def send_video(phone: str, video_path: str | Path, caption: str = "") -> dict:
    """Upload a local video and send it as a WhatsApp video message."""
    media_id: str = await _upload_media(video_path, "video/mp4")

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "video",
        "video": {"id": media_id, "caption": caption} if caption else {"id": media_id},
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _MESSAGES_URL,
            headers={**_AUTH, "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _upload_media(file_path: str | Path, mime_type: str) -> str:
    """Upload a local file to the WhatsApp Media API and return its *media_id*."""
    path = Path(file_path)
    if not path.is_absolute():
        path = MEDIA_ROOT / path

    async with httpx.AsyncClient() as client:
        # WhatsApp requires multipart/form-data for media uploads.
        # NOTE: open() is synchronous I/O — fine for occasional trainer images
        # (files are small, uploaded rarely).  For high-throughput media uploads
        # use aiofiles or run_in_executor to avoid blocking the event loop.
        with open(path, "rb") as fh:
            resp = await client.post(
                _MEDIA_URL,
                headers=_AUTH,
                files={"file": (path.name, fh, mime_type)},
                data={"messaging_product": "whatsapp"},
            )
        resp.raise_for_status()
        body = resp.json()
        return body["id"]
