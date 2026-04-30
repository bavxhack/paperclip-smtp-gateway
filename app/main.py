from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException

from app.config import AppMetadata, get_settings
from app.draft_writer import DraftWriter
from app.imap_client import ImapClient
from app.logging_config import configure_logging
from app.models import (
    DraftCreateRequest,
    DraftCreateResponse,
    HealthResponse,
    PaperclipWebhookPayload,
    RepliesPollRequest,
    RepliesPollResponse,
)
from app.paperclip_client import build_agent
from app.reply_reader import ReplyReader

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

metadata = AppMetadata()
app = FastAPI(title=metadata.name, version=metadata.version)

imap_client = ImapClient(settings)
draft_writer = DraftWriter(settings, imap_client)
reply_reader = ReplyReader(settings, imap_client)
agent = build_agent(settings)


@app.get('/health', response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get('/imap/folders')
def imap_folders() -> dict:
    try:
        return {'folders': imap_client.list_folders()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f'IMAP error: {exc}') from exc


@app.post('/drafts/create', response_model=DraftCreateResponse)
def create_draft(payload: DraftCreateRequest) -> DraftCreateResponse:
    try:
        folder = draft_writer.create_draft(payload)
        return DraftCreateResponse(folder=folder)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f'Draft creation failed: {exc}') from exc


@app.post('/replies/poll', response_model=RepliesPollResponse)
def poll_replies(payload: RepliesPollRequest) -> RepliesPollResponse:
    try:
        items = reply_reader.poll_replies(payload)
        return RepliesPollResponse(processed=len(items), items=items)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f'Reply polling failed: {exc}') from exc


@app.post('/paperclip/webhook')
def paperclip_webhook(payload: PaperclipWebhookPayload) -> dict:
    logger.info('Webhook event received: %s', payload.event)
    return {'status': 'ok'}
