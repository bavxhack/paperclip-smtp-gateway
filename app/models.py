from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class ErrorResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: Literal['ok'] = 'ok'


class DraftCreateRequest(BaseModel):
    to: EmailStr
    subject: str = Field(min_length=1, max_length=998)
    body_text: str = Field(min_length=1)
    body_html: str | None = None
    from_email: EmailStr
    reply_to_message_id: str | None = None
    references: str | None = None


class DraftCreateResponse(BaseModel):
    status: Literal['created'] = 'created'
    folder: str


class RepliesPollRequest(BaseModel):
    message_id: str | None = None
    from_email: EmailStr | None = None


class ReplyItem(BaseModel):
    message_id: str
    from_email: str
    subject: str
    snippet: str
    in_reply_to: str | None = None
    references: str | None = None
    received_at: str | None = None


class RepliesPollResponse(BaseModel):
    status: Literal['ok'] = 'ok'
    processed: int
    items: list[ReplyItem]
    unseen_items: list[ReplyItem] = Field(default_factory=list)


class PaperclipWebhookPayload(BaseModel):
    event: str
    data: dict = Field(default_factory=dict)
