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
<style>
:root{{--bg:#0b1020;--bg2:#131b33;--card:#1b2547;--text:#edf2ff;--muted:#adc0f8;--accent:#6ea8fe;--ok:#59d39b}}
*{{box-sizing:border-box}}body{{margin:0;font-family:Inter,Segoe UI,Arial,sans-serif;background:radial-gradient(circle at top right,#1b2b57 0,#0b1020 50%,#070b18 100%);color:var(--text)}}
.wrap{{max-width:1300px;margin:0 auto;padding:24px}}h1{{margin:0 0 4px;font-size:28px}}p{{color:var(--muted)}}
.stats,.cols{{display:grid;gap:12px}}.stats{{grid-template-columns:repeat(3,minmax(140px,1fr));margin:16px 0}}.cols{{grid-template-columns:repeat(3,minmax(260px,1fr))}}
.card{{background:linear-gradient(160deg,var(--card),var(--bg2));border:1px solid #2e3f75;border-radius:14px;padding:14px;box-shadow:0 8px 24px rgba(0,0,0,.25)}}
.kpi{{font-size:13px;color:var(--muted)}}.num{{display:block;font-size:30px;font-weight:700;color:var(--ok);margin-top:4px}}
.toolbar{{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px}}input{{background:#0d1530;color:var(--text);border:1px solid #30457f;border-radius:10px;padding:10px 12px;min-width:260px}}
button{{border:1px solid #3558b8;background:#12307a;color:#fff;border-radius:10px;padding:10px 12px;font-weight:600;cursor:pointer}}button:hover{{filter:brightness(1.12)}}
.list{{max-height:65vh;overflow:auto;display:grid;gap:8px}}.item{{background:#0d1530;border:1px solid #2b3f74;border-radius:10px;padding:10px}}
.meta{{font-size:12px;color:var(--muted);margin-top:4px}}.snippet{{margin-top:8px;white-space:pre-wrap;color:#dce5ff}}
</style>
</head><body>
<div class='wrap'>
<h1>SMTP Gateway Dashboard</h1>
<p>Inbox, Entwürfe und Gesendet im Live-Überblick.</p>
<div class='stats'>
  <div class='card'><span class='kpi'>Inbox</span><span class='num' id='inbox'>-</span></div>
  <div class='card'><span class='kpi'>Entwürfe</span><span class='num' id='drafts'>-</span></div>
  <div class='card'><span class='kpi'>Gesendet</span><span class='num' id='sent'>-</span></div>
</div>
<div class='toolbar'>
  <input id='email' placeholder='Filter: user@example.com'>
  <button onclick="loadFolder('{inbox_folder}','inboxList')">Inbox laden</button>
  <button onclick="loadFolder('{drafts_folder}','draftsList')">Entwürfe laden</button>
  <button onclick="loadFolder('{sent_folder}','sentList')">Gesendet laden</button>
</div>
<div class='cols'>
  <div class='card'><h3>Inbox ({inbox_folder})</h3><div class='list' id='inboxList'></div></div>
  <div class='card'><h3>Entwürfe ({drafts_folder})</h3><div class='list' id='draftsList'></div></div>
  <div class='card'><h3>Gesendet ({sent_folder})</h3><div class='list' id='sentList'></div></div>
</div></div>
<script>
const esc=(s)=>String(s||'').replace(/[&<>"]/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[m]));
async function loadSummary(){{const r=await fetch('/dashboard/summary');const j=await r.json();inbox.textContent=j.inbox_count;drafts.textContent=j.drafts_count;sent.textContent=j.sent_count;}}
async function loadFolder(folder,target){{const email=document.getElementById('email').value||null;const r=await fetch('/emails/messages',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{folder:folder,email_address:email,limit:25}})}});const j=await r.json();document.getElementById(target).innerHTML=(j.items||[]).map(i=>`<div class="item"><b>${{esc(i.subject||'(ohne Betreff)')}}</b><div class="meta">Von: ${{esc(i.from_email)}} · An: ${{esc(i.to_email)}} · Datum: ${{esc(i.received_at||'-')}}</div><div class="snippet">${{esc(i.snippet||'')}}</div></div>`).join('');}}
loadSummary();
</script></body></html>
"""


@app.post('/paperclip/webhook')
def paperclip_webhook(payload: PaperclipWebhookPayload) -> dict:
    logger.info('Webhook event received: %s', payload.event)
    return {'status': 'ok'}
