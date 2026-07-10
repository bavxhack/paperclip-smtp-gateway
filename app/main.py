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
    SendEmailRequest,
    SendEmailResponse,
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


@app.post('/send', response_model=SendEmailResponse)
def send_email(payload: SendEmailRequest) -> SendEmailResponse:
    try:
        folder = draft_writer.create_draft(payload)
        return SendEmailResponse(folder=folder)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f'Email send failed: {exc}') from exc


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


DASHBOARD_HTML = """
<!doctype html>
<html lang="de">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SMTP Gateway Dashboard</title>
    <style>
        :root {
            --bg: #f6f7f9;
            --surface: #ffffff;
            --surface-muted: #f1f3f5;
            --text: #17202a;
            --text-soft: #5c6670;
            --text-muted: #8a949e;
            --accent: #2f5f8f;
            --accent-soft: #e8eef5;
            --border: #dde3ea;
            --danger: #b42318;
            --shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
            --radius: 18px;
            --radius-sm: 12px;
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            min-height: 100vh;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: linear-gradient(180deg, #eef2f6 0%, var(--bg) 38%);
            color: var(--text);
        }

        .container { max-width: 1440px; margin: 0 auto; padding: 32px; }

        .topbar {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 24px;
            margin-bottom: 28px;
        }

        .eyebrow { color: var(--accent); font-size: 13px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
        h1 { margin: 6px 0 8px; font-size: clamp(30px, 4vw, 46px); line-height: 1.05; letter-spacing: -0.04em; }
        .subtitle { margin: 0; color: var(--text-soft); max-width: 640px; }

        .status-pill {
            border: 1px solid var(--border);
            border-radius: 999px;
            background: rgba(255,255,255,.72);
            color: var(--text-soft);
            padding: 10px 14px;
            white-space: nowrap;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
        }

        .stats-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-bottom: 20px; }
        .stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 22px; box-shadow: var(--shadow); }
        .stat-label { display: block; color: var(--text-soft); font-size: 14px; font-weight: 650; margin-bottom: 10px; }
        .stat-value { display: block; color: var(--text); font-size: 42px; line-height: 1; font-weight: 760; letter-spacing: -0.04em; }

        .toolbar {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            align-items: center;
            margin-bottom: 22px;
            padding: 14px;
            background: rgba(255,255,255,.78);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
            backdrop-filter: blur(10px);
        }

        .search-box { flex: 1; min-width: 260px; }
        input[type="email"] { width: 100%; background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 12px 14px; font-size: 15px; }
        input[type="email"]:focus { outline: 2px solid var(--accent-soft); border-color: var(--accent); }

        button { border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 12px 16px; background: var(--surface); color: var(--text); font-weight: 700; cursor: pointer; transition: transform .15s ease, border-color .15s ease, background .15s ease; }
        button:hover { transform: translateY(-1px); border-color: #b8c3cf; background: #fafbfc; }
        .button-primary { background: var(--accent); border-color: var(--accent); color: #fff; }
        .button-primary:hover { background: #284f78; }

        .content-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; }
        .panel { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow); overflow: hidden; min-height: 420px; }
        .panel-header { padding: 18px 18px 14px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; gap: 12px; align-items: center; }
        .panel-title { font-size: 18px; font-weight: 760; }
        .folder-badge { background: var(--surface-muted); color: var(--text-soft); border: 1px solid var(--border); padding: 6px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
        .panel-body { max-height: 62vh; overflow: auto; }

        .message-item { display: block; width: 100%; text-align: left; border: 0; border-bottom: 1px solid var(--border); border-radius: 0; background: transparent; color: inherit; padding: 16px 18px; cursor: pointer; transition: background .15s ease; }
        .message-item:hover { background: #f8fafc; }
        .message-item.unread { box-shadow: inset 3px 0 0 var(--accent); background: #fbfcfe; }
        .message-header { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
        .message-subject { font-weight: 720; word-break: break-word; }
        .message-date { color: var(--text-muted); font-size: 12px; white-space: nowrap; }
        .message-meta { display: grid; gap: 4px; color: var(--text-soft); font-size: 13px; margin-bottom: 10px; }
        .message-snippet { color: var(--text-muted); font-size: 14px; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }

        .modal-overlay { position: fixed; inset: 0; background: rgba(17, 24, 39, 0.58); display: none; justify-content: center; align-items: center; z-index: 1000; padding: 20px; }
        .modal-overlay.active { display: flex; }
        .modal { background: var(--surface); border-radius: 22px; width: min(880px, 100%); max-height: 88vh; overflow: auto; box-shadow: 0 25px 80px rgba(0,0,0,.25); }
        .modal-header { padding: 18px 22px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
        .modal-title { font-size: 20px; font-weight: 760; }
        .modal-close { border: 0; background: transparent; font-size: 28px; padding: 2px 8px; color: var(--text-soft); }
        .modal-body { padding: 22px; }
        .message-detail { display: grid; gap: 18px; }
        .detail-section { border-bottom: 1px solid var(--border); padding-bottom: 16px; }
        .detail-section:last-child { border-bottom: 0; padding-bottom: 0; }
        .detail-label { color: var(--text-muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; font-weight: 750; margin-bottom: 5px; }
        .detail-value { word-break: break-word; }
        .message-body { background: var(--surface-muted); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 16px; white-space: pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 14px; line-height: 1.6; max-height: 420px; overflow: auto; }

        .loading { display: inline-block; width: 18px; height: 18px; border: 2px solid #c8d1dc; border-radius: 50%; border-top-color: var(--accent); animation: spin 1s linear infinite; vertical-align: middle; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .loading-overlay, .empty-state, .error-message { padding: 34px 18px; text-align: center; color: var(--text-muted); }
        .error-message { color: var(--danger); }

        @media (max-width: 1040px) { .content-grid { grid-template-columns: 1fr; } }
        @media (max-width: 760px) { .container { padding: 18px; } .topbar { display: block; } .status-pill { display: inline-block; margin-top: 16px; } .stats-grid { grid-template-columns: 1fr; } .toolbar { align-items: stretch; flex-direction: column; } button { width: 100%; } }
    </style>
</head>
<body>
    <main class="container">
        <header class="topbar">
            <div>
                <div class="eyebrow">Paperclip Mail Agent</div>
                <h1>SMTP Gateway Dashboard</h1>
                <p class="subtitle">Ein ruhiger, klarer Überblick über Inbox, Entwürfe und gesendete Nachrichten.</p>
            </div>
            <div class="status-pill" id="lastUpdated">Noch nicht aktualisiert</div>
        </header>

        <section class="stats-grid" aria-label="Kennzahlen">
            <div class="stat-card"><span class="stat-label">Inbox</span><span class="stat-value" id="inboxCount">-</span></div>
            <div class="stat-card"><span class="stat-label">Entwürfe</span><span class="stat-value" id="draftsCount">-</span></div>
            <div class="stat-card"><span class="stat-label">Gesendet</span><span class="stat-value" id="sentCount">-</span></div>
        </section>

        <section class="toolbar" aria-label="Filter und Aktionen">
            <div class="search-box"><input type="email" id="emailFilter" placeholder="Nach E-Mail-Adresse filtern" autocomplete="off"></div>
            <button class="button-primary" id="refreshButton" type="button"><span class="loading" id="refreshLoading" style="display:none"></span><span id="refreshText">Aktualisieren</span></button>
            <button id="clearButton" type="button">Filter zurücksetzen</button>
        </section>

        <section class="content-grid">
            <article class="panel"><div class="panel-header"><span class="panel-title">Inbox</span><span class="folder-badge" id="inboxBadge">{inbox_folder}</span></div><div class="panel-body"><div class="message-list" id="inboxList"></div></div></article>
            <article class="panel"><div class="panel-header"><span class="panel-title">Entwürfe</span><span class="folder-badge" id="draftsBadge">{drafts_folder}</span></div><div class="panel-body"><div class="message-list" id="draftsList"></div></div></article>
            <article class="panel"><div class="panel-header"><span class="panel-title">Gesendet</span><span class="folder-badge" id="sentBadge">{sent_folder}</span></div><div class="panel-body"><div class="message-list" id="sentList"></div></div></article>
        </section>
    </main>

    <div class="modal-overlay" id="messageModal" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
        <div class="modal"><div class="modal-header"><span class="modal-title" id="modalTitle">Nachrichtendetails</span><button class="modal-close" id="modalClose" type="button" aria-label="Schließen">&times;</button></div><div class="modal-body"><div class="message-detail" id="modalContent"></div></div></div>
    </div>

    <script>
        var INBOX_FOLDER = '{inbox_folder}';
        var DRAFTS_FOLDER = '{drafts_folder}';
        var SENT_FOLDER = '{sent_folder}';
        var messageStore = new Map();

        function esc(value) {
            if (value === null || value === undefined) return '';
            return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        }

        function formatDate(value) {
            if (!value) return '-';
            var date = new Date(value);
            if (Number.isNaN(date.getTime())) return value;
            return date.toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
        }

        function truncate(text, length) {
            text = text || '';
            return text.length > length ? text.slice(0, length) + '…' : text;
        }

        function setRefreshState(isLoading) {
            document.getElementById('refreshLoading').style.display = isLoading ? 'inline-block' : 'none';
            document.getElementById('refreshText').textContent = isLoading ? 'Lädt…' : 'Aktualisieren';
            document.getElementById('refreshButton').disabled = isLoading;
        }

        function loadingMarkup() { return '<div class="loading-overlay"><span class="loading"></span><span style="margin-left:10px">Lade Nachrichten…</span></div>'; }
        function emptyMarkup() { return '<div class="empty-state">Keine Nachrichten gefunden</div>'; }

        async function loadSummary() {
            var response = await fetch('/dashboard/summary');
            if (!response.ok) throw new Error('Zusammenfassung konnte nicht geladen werden');
            var data = await response.json();
            document.getElementById('inboxCount').textContent = data.inbox_count || 0;
            document.getElementById('draftsCount').textContent = data.drafts_count || 0;
            document.getElementById('sentCount').textContent = data.sent_count || 0;
            document.getElementById('lastUpdated').textContent = 'Aktualisiert: ' + new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
        }

        async function loadFolder(folder, targetElementId) {
            var listEl = document.getElementById(targetElementId);
            var email = document.getElementById('emailFilter').value.trim() || null;
            listEl.innerHTML = loadingMarkup();

            try {
                var response = await fetch('/emails/messages', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ folder: folder, email_address: email, limit: 50 })
                });
                if (!response.ok) throw new Error('Nachrichten konnten nicht geladen werden');
                var data = await response.json();
                listEl.innerHTML = data.items && data.items.length ? data.items.map(function(item, index) { return createMessageItemHtml(item, folder, targetElementId + '-' + index); }).join('') : emptyMarkup();
                updatePanelCounts();
            } catch (error) {
                console.error('Error loading folder:', folder, error);
                listEl.innerHTML = '<div class="error-message">Fehler beim Laden der Nachrichten</div>';
            }
        }

        function createMessageItemHtml(item, folder, itemId) {
            item.folder = folder;
            messageStore.set(itemId, item);
            var isUnread = item.seen === false || item.is_unread === true;
            return '<button type="button" class="message-item ' + (isUnread ? 'unread' : '') + '" data-message-id="' + esc(itemId) + '">' +
                '<div class="message-header"><span class="message-subject">' + esc(item.subject || '(kein Betreff)') + '</span><span class="message-date">' + esc(formatDate(item.received_at)) + '</span></div>' +
                '<div class="message-meta"><span>Von: ' + esc(item.from_email || '-') + '</span><span>An: ' + esc(item.to_email || '-') + '</span></div>' +
                '<div class="message-snippet">' + esc(truncate(item.snippet || item.body_text || '', 150)) + '</div>' +
                '</button>';
        }

        function showMessageDetail(itemId) {
            var item = messageStore.get(itemId);
            if (!item) return;
            document.getElementById('modalTitle').textContent = item.subject || '(kein Betreff)';
            document.getElementById('modalContent').innerHTML =
                detailHtml('Absender', item.from_email || '-') +
                detailHtml('Empfänger', item.to_email || '-') +
                detailHtml('Datum', formatDate(item.received_at)) +
                detailHtml('Ordner', item.folder || '-') +
                detailHtml('Message-ID', item.message_id || '-', true) +
                detailHtml('Betreff', item.subject || '(kein Betreff)') +
                '<div class="detail-section"><div class="detail-label">Nachrichten-Text</div><div class="message-body">' + esc(item.body_text || item.snippet || '(kein Text)') + '</div></div>';
            document.getElementById('messageModal').classList.add('active');
        }

        function detailHtml(label, value, mono) {
            return '<div class="detail-section"><div class="detail-label">' + esc(label) + '</div><div class="detail-value"' + (mono ? ' style="font-family: ui-monospace, monospace; font-size: 12px;"' : '') + '>' + esc(value) + '</div></div>';
        }

        function closeModal() { document.getElementById('messageModal').classList.remove('active'); }

        async function loadAllFolders() {
            setRefreshState(true);
            try {
                await Promise.all([loadFolder(INBOX_FOLDER, 'inboxList'), loadFolder(DRAFTS_FOLDER, 'draftsList'), loadFolder(SENT_FOLDER, 'sentList')]);
                await loadSummary();
            } catch (error) {
                console.error('Error loading dashboard:', error);
            } finally {
                setRefreshState(false);
            }
        }

        function updatePanelCounts() {
            document.getElementById('inboxBadge').textContent = INBOX_FOLDER + ' (' + document.querySelectorAll('#inboxList .message-item').length + ')';
            document.getElementById('draftsBadge').textContent = DRAFTS_FOLDER + ' (' + document.querySelectorAll('#draftsList .message-item').length + ')';
            document.getElementById('sentBadge').textContent = SENT_FOLDER + ' (' + document.querySelectorAll('#sentList .message-item').length + ')';
        }

        document.getElementById('refreshButton').addEventListener('click', loadAllFolders);
        document.getElementById('clearButton').addEventListener('click', function() { document.getElementById('emailFilter').value = ''; loadAllFolders(); });
        document.getElementById('emailFilter').addEventListener('keydown', function(event) { if (event.key === 'Enter') loadAllFolders(); });
        document.getElementById('modalClose').addEventListener('click', closeModal);
        document.getElementById('messageModal').addEventListener('click', function(event) { if (event.target === this) closeModal(); });
        document.addEventListener('keydown', function(event) { if (event.key === 'Escape') closeModal(); });
        document.addEventListener('click', function(event) { var row = event.target.closest('.message-item'); if (row && row.dataset.messageId) showMessageDetail(row.dataset.messageId); });

        loadAllFolders();
        setInterval(loadSummary, 60000);
    </script>
</body>
</html>
"""


@app.get('/dashboard', response_class=HTMLResponse)
def dashboard() -> str:
    inbox_folder = esc(settings.IMAP_INBOX_FOLDER)
    drafts_folder = esc(settings.IMAP_DRAFTS_FOLDER)
    sent_folder = esc(settings.IMAP_SENT_FOLDER)
    
    html = DASHBOARD_HTML.replace('{inbox_folder}', inbox_folder).replace('{drafts_folder}', drafts_folder).replace('{sent_folder}', sent_folder)
    return html


def esc(s):
    """Escape HTML special characters."""
    if not s:
        return ''
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;')


@app.post('/paperclip/webhook')
def paperclip_webhook(payload: PaperclipWebhookPayload) -> dict:
    logger.info('Webhook event received: %s', payload.event)
    return {'status': 'ok'}
