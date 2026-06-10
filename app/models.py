"""
Pydantic models for request validation and structured data interchange.

These models provide runtime type-checking and serialisation boundaries
between the webhook transport layer and the agent's internal logic.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class WebhookMessage(BaseModel):
    """A WhatsApp message extracted from the webhook payload."""

    phone: str = Field(..., description="Sender phone number in E.164 format")
    body: str = Field(default="", description="Message text body (empty for media)")
    message_id: str = Field(default="", description="WhatsApp message ID")


class MemberRecord(BaseModel):
    """A row from the members table."""

    id: int
    phone: str
    name: str
    plan: str
    expiry: str


class ClassRecord(BaseModel):
    """A row from the class_schedule table."""

    id: int
    class_type: str
    date: str
    time: str
    instructor: str
    capacity: int


class TrialBooking(BaseModel):
    """A trial class booking request payload."""

    phone: str
    name: Optional[str] = None
    date: str
    time: str


class ToolInput(BaseModel):
    """Generic envelope for tool-call inputs dispatched by the agent loop."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
