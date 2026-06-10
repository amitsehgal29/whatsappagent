"""
Agentic tool-use orchestration loop.

This is the core of the gym assistant.  On each user message the loop:

  1. Appends the user message to a per-phone conversation history.
  2. Sends the full history + tool schemas to the Claude API.
  3. If Claude returns ``tool_use`` stop-reason → executes the tool(s),
     appends ``tool_result`` blocks, and loops (up to 15 rounds).
  4. If Claude returns ``end_turn`` → extracts the text reply and returns it.

The conversation history preserves intermediate tool calls so Claude can
chain tools across turns (e.g. ``get_next_class`` → ``register_for_class``).
"""

from __future__ import annotations

from anthropic import Anthropic

from app.config import ANTHROPIC_API_KEY, MAX_TOOL_ROUNDS, MODEL
from app.memory import ConversationMemory
from app.tools import TOOLS, execute_tool
from app.whatsapp import send_image, send_text

# ---------------------------------------------------------------------------
# Claude client — created once, reused across all requests
# ---------------------------------------------------------------------------
_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Per-phone conversation state.
_memory = ConversationMemory()

# ---------------------------------------------------------------------------
# System prompt — injected on every API call to ground the assistant
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT: str = (
    "You are a friendly, professional gym assistant for a premium fitness centre. "
    "Your job is to help prospects and members with questions about membership "
    "plans, class schedules, trainer information, gym policies, amenities, and "
    "to help them book trial classes or register for group classes.\n\n"
    "Rules:\n"
    "- Answer ONLY from the information returned by your tools. "
    "Never invent prices, trainer names, or policies.\n"
    "- If a tool returns no results, tell the user honestly and suggest alternatives.\n"
    "- When booking or registering, confirm the details back to the user.\n"
    "- Collect all required information before calling booking tools.\n"
    "- Be concise but warm — one or two paragraphs max.\n"
    "- If a user asks something you cannot answer, offer to connect them with "
    "the front desk."
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_agent(phone: str, user_message: str) -> str:
    """Process a user message and return the assistant's text response.

    This is the main entry point called from the webhook handler.  It manages
    the full tool-calling loop for *phone* and persists the conversation
    history in memory so subsequent messages maintain context.
    """
    # -- send trainer images inline if Claude requests it --------------------
    if _is_media_sentinel(user_message):
        return await _handle_media_request(phone)

    _memory.add_user_message(phone, user_message)
    history = _memory.get(phone)

    for _round in range(MAX_TOOL_ROUNDS):
        response = _client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            tools=TOOLS,
            messages=history,
        )

        # -- final text response ---------------------------------------------
        if response.stop_reason == "end_turn":
            text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            _memory.add_assistant_message(phone, text)
            return text

        # -- tool-use round --------------------------------------------------
        if response.stop_reason == "tool_use":
            for block in response.content:
                if block.type != "tool_use":
                    continue

                # Resolve media tools via async WhatsApp helpers; everything
                # else goes through the synchronous dispatcher.
                if block.name == "send_trainer_profiles":
                    result = await _handle_media_request(phone)
                else:
                    result = await execute_tool(
                        block.name,
                        block.input or {},
                        phone,
                    )

                # Append tool result to conversation per Anthropic spec.
                _memory.add_tool_result(phone, block.id, str(result))

            # Update history reference for the next loop iteration.
            history = _memory.get(phone)
            continue

        # fallback — should not happen with current API behaviour
        break

    return (
        "I'm sorry, I wasn't able to process that request. "
        "Please try again or contact the front desk for assistance."
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _handle_media_request(phone: str) -> str:
    """Send trainer profile images to *phone* via WhatsApp.

    Looks for images in the ``media/`` directory matching the pattern
    ``trainer*.jpg`` and sends each one with an appropriate caption.
    Returns a descriptive result string for the conversation log.
    """
    from pathlib import Path

    media_dir = Path(__file__).resolve().parent.parent / "media"
    trainer_images = sorted(media_dir.glob("trainer*.jpg"))

    if not trainer_images:
        await send_text(
            phone,
            "Our trainers are Sarah Chen (strength & rehab) and Marcus Williams "
            "(yoga, HIIT & mobility). Photos are being uploaded — check back soon!",
        )
        return "trainer_profiles_sent:text_only"

    for img_path in trainer_images:
        try:
            await send_image(phone, img_path, caption="")
        except Exception:
            # Don't block the conversation on media failures.
            continue

    await send_text(
        phone,
        "Here are our trainers! Sarah specialises in strength & rehab; "
        "Marcus leads yoga, HIIT, and mobility. Both offer one-on-one sessions.",
    )
    return f"trainer_profiles_sent:{len(trainer_images)}_images"


def _is_media_sentinel(text: str) -> bool:
    """Return True if *text* is a synthetic media-delivery sentinel rather
    than a real user message.  Used internally to inject media sends into
    the conversation flow without exposing them to Claude."""
    return text.startswith("MEDIA_SEND:")
