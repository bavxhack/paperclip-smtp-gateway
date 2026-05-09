from __future__ import annotations

import logging

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from app.config import AppMetadata, get_settings
from app.draft_writer import DraftWriter
from app.imap_client import ImapClient
from app.logging_config import configure_logging
from app.mailbox_reader import MailboxReader
from app.models import (
    DraftCreateRequest,
    DraftCreateResponse,
    EmailMessagesQuery,
    EmailMessagesResponse,
    GatewayDashboardResponse,
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
mailbox_reader = MailboxReader(settings, imap_client)
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
def poll_replies(payload: RepliesPollRequest = Body(default_factory=RepliesPollRequest)) -> RepliesPollResponse:
    try:
        items, unseen_items = reply_reader.poll_replies(payload)
        return RepliesPollResponse(processed=len(items), items=items, unseen_items=unseen_items)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f'Reply polling failed: {exc}') from exc


@app.post('/emails/messages', response_model=EmailMessagesResponse)
def email_messages(payload: EmailMessagesQuery) -> EmailMessagesResponse:
    try:
        items, total = mailbox_reader.fetch_messages(payload)
        return EmailMessagesResponse(total_in_folder=total, returned=len(items), items=items)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f'Message retrieval failed: {exc}') from exc


@app.get('/dashboard/summary', response_model=GatewayDashboardResponse)
def dashboard_summary() -> GatewayDashboardResponse:
    try:
        inbox_items, inbox_total = mailbox_reader.fetch_messages(EmailMessagesQuery(folder=settings.IMAP_INBOX_FOLDER, limit=10))
        drafts_items, drafts_total = mailbox_reader.fetch_messages(EmailMessagesQuery(folder=settings.IMAP_DRAFTS_FOLDER, limit=10))
        sent_items, sent_total = mailbox_reader.fetch_messages(EmailMessagesQuery(folder=settings.IMAP_SENT_FOLDER, limit=10))
        recent = sorted(inbox_items + drafts_items + sent_items, key=lambda x: x.received_at or '', reverse=True)[:10]
        return GatewayDashboardResponse(
            inbox_count=inbox_total,
            drafts_count=drafts_total,
            sent_count=sent_total,
            recent_activity=recent,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f'Dashboard summary failed: {exc}') from exc


@app.get('/dashboard', response_class=HTMLResponse)
def dashboard() -> str:
    inbox_folder = settings.IMAP_INBOX_FOLDER
    drafts_folder = settings.IMAP_DRAFTS_FOLDER
    sent_folder = settings.IMAP_SENT_FOLDER
    return f"""
<!doctype html><html><head><meta charset='utf-8'><title>SMTP Gateway Dashboard</title>
<style>body{{font-family:Arial;margin:20px}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.card{{border:1px solid #ddd;padding:12px;border-radius:8px}}.cols{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}pre{{white-space:pre-wrap;background:#f7f7f7;padding:8px;border-radius:6px}}</style>
</head><body>
<h1>SMTP Gateway Dashboard</h1>
<div class='grid'><div class='card'>Inbox: <b id='inbox'>-</b></div><div class='card'>Drafts: <b id='drafts'>-</b></div><div class='card'>Sent: <b id='sent'>-</b></div></div>
<h2>Filter</h2><input id='email' placeholder='user@example.com'>
<button onclick="loadFolder('{inbox_folder}','inboxList')">Inbox laden</button>
<button onclick="loadFolder('{drafts_folder}','draftsList')">Entwürfe laden</button>
<button onclick="loadFolder('{sent_folder}','sentList')">Gesendet laden</button>
<div class='cols'><div><h3>Inbox</h3><div id='inboxList'></div></div><div><h3>Entwürfe</h3><div id='draftsList'></div></div><div><h3>Gesendet</h3><div id='sentList'></div></div></div>
<script>
async function loadSummary(){{const r=await fetch('/dashboard/summary');const j=await r.json();document.getElementById('inbox').textContent=j.inbox_count;document.getElementById('drafts').textContent=j.drafts_count;document.getElementById('sent').textContent=j.sent_count;}}
async function loadFolder(folder,target){{const email=document.getElementById('email').value||null;const r=await fetch('/emails/messages',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{folder:folder,email_address:email,limit:25}})}});const j=await r.json();document.getElementById(target).innerHTML=(j.items||[]).map(i=>`<pre><b>${{i.subject||'(ohne Betreff)'}}</b>
Von: ${{i.from_email}}
An: ${{i.to_email}}
Datum: ${{i.received_at||'-'}}

${{i.snippet||''}}</pre>`).join('');}}
loadSummary();
</script></body></html>
"""


@app.post('/paperclip/webhook')
def paperclip_webhook(payload: PaperclipWebhookPayload) -> dict:
    logger.info('Webhook event received: %s', payload.event)
    return {'status': 'ok'}
