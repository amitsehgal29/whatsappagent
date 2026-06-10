"""
Tool implementations and Anthropic JSON-Schema definitions.

Six tools are exposed to the Claude model so it can autonomously decide
which backend function to call, with what arguments, and in what order.

  ┌──────────────────────────┬──────────────────────────────────────┐
  │ Tool                     │ Backend                              │
  ├──────────────────────────┼──────────────────────────────────────┤
  │ search_knowledge_base    │ app.rag.search()                     │
  │ send_trainer_profiles    │ app.whatsapp.send_image()            │
  │ book_trial_class         │ app.db.insert_trial_booking()        │
  │ get_membership_details   │ app.db.get_member()                  │
  │ get_next_class           │ app.db.get_next_class()              │
  │ register_for_class       │ app.db.insert_class_registration()   │
  └──────────────────────────┴──────────────────────────────────────┘
"""

from __future__ import annotations

from typing import Any

from app import rag
from app.db import (
    get_member,
    get_next_class,
    insert_class_registration,
    insert_trial_booking,
)


# ======================================================================
# Tool implementations
# ======================================================================

def search_knowledge_base(query: str) -> str:
    """Search the gym knowledge corpus and return the top relevant chunks."""
    return rag.search(query)


def send_trainer_profiles(phone: str) -> str:
    """Queue trainer profile images for delivery via WhatsApp.

    The actual async send happens inside the agent loop's tool dispatcher,
    so this function returns an instruction string that the dispatcher
    recognises and handles with ``whatsapp.send_image()``.
    """
    return "MEDIA_SEND:trainer_profiles"


def book_trial_class(
    phone: str, date: str, time: str, name: str = ""
) -> str:
    """Book a prospect into a trial class."""
    row_id = insert_trial_booking(phone, date, time, name)
    return (
        f"Trial class booked successfully (booking #{row_id}). "
        f"Date: {date}, Time: {time}. Please arrive 10 minutes early "
        f"and bring a valid photo ID."
    )


def get_membership_details(phone: str) -> str:
    """Look up the membership record for the calling phone number."""
    member = get_member(phone)
    if not member:
        return (
            "No membership found for this number. You can sign up for a "
            "free trial class to try us out, or ask me about our plans."
        )
    return (
        f"Member: {member['name']}\n"
        f"Plan: {member['plan']}\n"
        f"Expiry: {member['expiry']}\n"
        f"Status: Active"
    )


def get_next_class_info(class_type: str) -> str:
    """Return the upcoming schedule for a given class type."""
    classes = get_next_class(class_type)
    if not classes:
        return (
            f"No upcoming {class_type} classes found in the schedule. "
            f"Try another class type or check back later."
        )
    lines = [f"Upcoming {class_type} classes:"]
    for c in classes:
        lines.append(
            f"  • ID #{c['id']} — {c['date']} at {c['time']} "
            f"with {c['instructor']} ({c['capacity']} spots)"
        )
    return "\n".join(lines)


def register_for_class(phone: str, class_id: int) -> str:
    """Register a member for a specific class by its ID."""
    row_id = insert_class_registration(phone, class_id)
    return (
        f"You're registered! (booking #{row_id}). "
        f"Class ID: {class_id}. See you there!"
    )


# ======================================================================
# Tool dispatcher — called by the agent loop
# ======================================================================

async def execute_tool(name: str, inputs: dict[str, Any], phone: str) -> str:
    """Dispatch a tool call by name and return the result as a string.

    *name* and *inputs* come directly from the Claude API's tool_use block.
    *phone* is the sender's WhatsApp number used for member-scoped tools.

    Media tools (send_trainer_profiles) return a sentinel string that the
    agent loop handles by calling ``whatsapp.send_image()`` asynchronously.
    """
    if name == "search_knowledge_base":
        return search_knowledge_base(**inputs)

    if name == "send_trainer_profiles":
        return send_trainer_profiles(phone)

    if name == "book_trial_class":
        return book_trial_class(phone=phone, **inputs)

    if name == "get_membership_details":
        return get_membership_details(phone)

    if name == "get_next_class":
        return get_next_class_info(**inputs)

    if name == "register_for_class":
        return register_for_class(phone=phone, **inputs)

    return f"Unknown tool: {name}"


# ======================================================================
# Anthropic Tool Schemas (JSON Schema format)
# ======================================================================

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_knowledge_base",
        "description": (
            "Search the gym knowledge base for information about membership "
            "plans, pricing, hours, locations, classes, trainers, amenities, "
            "policies, and offers. Use this whenever a prospect or member asks "
            "a general question about the gym."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The natural-language question or search query.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_membership_details",
        "description": (
            "Look up the membership record for the current WhatsApp user. "
            "Returns name, plan type, and expiry date. Use this when a member "
            "asks about their account status, plan, or renewal."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_next_class",
        "description": (
            "Find upcoming class instances for a given class type "
            "(e.g., Yoga, HIIT, Spinning, Pilates, Zumba). "
            "Returns date, time, instructor, and available spots."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "class_type": {
                    "type": "string",
                    "description": "The class type to search for (case-insensitive).",
                }
            },
            "required": ["class_type"],
        },
    },
    {
        "name": "book_trial_class",
        "description": (
            "Book a free trial class for a prospect. Collects preferred date, "
            "time, and optionally the person's name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Preferred date in YYYY-MM-DD format.",
                },
                "time": {
                    "type": "string",
                    "description": "Preferred time in HH:MM 24-hour format.",
                },
                "name": {
                    "type": "string",
                    "description": "The prospect's full name (optional).",
                },
            },
            "required": ["date", "time"],
        },
    },
    {
        "name": "register_for_class",
        "description": (
            "Register the current member for a specific class using its ID. "
            "The class ID can be obtained from a preceding get_next_class call."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "class_id": {
                    "type": "integer",
                    "description": "The numeric class ID from the schedule.",
                }
            },
            "required": ["class_id"],
        },
    },
    {
        "name": "send_trainer_profiles",
        "description": (
            "Send trainer profile images to the user via WhatsApp. "
            "Call this when a prospect or member asks to see the trainers, "
            "their qualifications, or who teaches which class."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]
