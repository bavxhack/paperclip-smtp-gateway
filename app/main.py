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
    <title>E-Mail Dashboard</title>
    <style>
        :root {
            --bg: #292f2f;
            --text: #f2f2f0;
            --muted: #a9adb6;
            --line: #858b8c;
            --accent: #b3a0ff;
            --accent-deep: #12004d;
            --warn-bg: #5a4a00;
            --warn-text: #fff7b3;
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            min-height: 100vh;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: var(--bg);
            color: var(--text);
        }

        .container {
            width: min(100%, 1760px);
            margin: 0 auto;
            padding: clamp(56px, 7vw, 112px) clamp(42px, 6vw, 120px) 90px;
        }

        .eyebrow {
            margin-bottom: 34px;
            color: var(--accent);
            font-size: clamp(14px, 1.2vw, 24px);
            font-weight: 500;
            letter-spacing: .03em;
            text-transform: uppercase;
        }

        .hero { position: relative; padding-bottom: 46px; border-bottom: 3px solid var(--line); }
        h1 { margin: 0; font-size: clamp(50px, 5.1vw, 92px); line-height: 1.08; font-weight: 400; letter-spacing: -.045em; }
        .subtitle { margin: 70px 0 0; color: var(--muted); font-size: clamp(20px, 1.8vw, 34px); line-height: 1.35; }
        .status-pill { position: absolute; right: 0; top: 120px; color: var(--muted); font-size: clamp(18px, 1.7vw, 32px); white-space: nowrap; }

        .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 48px; padding: 58px 0 52px; border-bottom: 3px solid var(--line); text-align: center; }
        .stat-card { min-width: 0; }
        .stat-value { display: block; color: var(--text); font-size: clamp(68px, 6vw, 112px); font-weight: 300; line-height: .95; letter-spacing: -.04em; }
        .stat-label { display: block; margin-top: 42px; color: var(--text); font-size: clamp(25px, 2vw, 42px); font-weight: 600; }
        .stat-description { display: block; margin-top: 24px; color: var(--text); font-size: clamp(18px, 1.5vw, 32px); font-weight: 400; opacity: .82; }

        .toolbar { display: grid; grid-template-columns: 1fr auto auto; align-items: center; gap: 18px; padding: 86px 0 68px; }
        .search-box { min-width: 0; }
        input[type="email"] { width: 100%; background: transparent; border: 0; color: var(--text); font-size: clamp(22px, 1.9vw, 36px); padding: 12px 0; }
        input[type="email"]::placeholder { color: var(--muted); opacity: 1; }
        input[type="email"]:focus { outline: 0; color: var(--text); }
        button { border-radius: 3px; padding: 22px 34px; background: transparent; border: 2px solid var(--accent); color: var(--accent); font-size: clamp(18px, 1.5vw, 32px); font-weight: 700; cursor: pointer; }
        button:disabled { opacity: .55; cursor: wait; }
        .button-primary { background: var(--accent); color: #05040a; }

        .content-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: clamp(48px, 5vw, 72px); }
        .panel[data-folder-kind="drafts"] .message-item { border-left-color: #ffd36e; }
        .panel[data-folder-kind="drafts"] .folder-badge { background: #4a3600; border-color: #ffd36e; }
        .panel { min-width: 0; }
        .panel-header { border-bottom: 3px solid var(--line); padding-bottom: 42px; margin-bottom: 38px; }
        .folder-badge { display: inline-block; margin-bottom: 14px; padding: 7px 16px; background: var(--accent-deep); border: 1px solid var(--accent); color: var(--text); font-size: clamp(14px, 1.2vw, 22px); line-height: 1; text-transform: uppercase; }
        .panel-title { display: block; color: var(--text); font-size: clamp(28px, 2.2vw, 42px); font-weight: 500; line-height: 1.1; }
        .message-list { display: grid; gap: 30px; }
        .message-item { display: block; width: 100%; text-align: left; border: 3px solid #697071; border-left: 11px solid var(--accent); border-radius: 2px; background: transparent; color: inherit; padding: 32px 32px 28px; cursor: pointer; }
        .message-item:hover { border-color: var(--accent); }
        .message-header { margin-bottom: 14px; font-size: clamp(20px, 1.55vw, 30px); line-height: 1.35; }
        .message-subject { font-weight: 750; color: #dedfdd; }
        .message-date { color: var(--muted); font-weight: 400; }
        .message-meta, .message-snippet { color: var(--muted); font-size: clamp(18px, 1.45vw, 28px); line-height: 1.55; }
        .message-snippet { display: -webkit-box; -webkit-line-clamp: 5; -webkit-box-orient: vertical; overflow: hidden; }
        .message-meta .to-line { display: none; }
        .empty-state, .error-message, .loading-overlay { color: var(--muted); font-size: clamp(18px, 1.35vw, 26px); line-height: 1.45; padding: 12px 0; }
        .error-message { background: var(--warn-bg); color: var(--warn-text); padding: 32px; }
        .loading { display: inline-block; width: 18px; height: 18px; border: 2px solid var(--muted); border-radius: 50%; border-top-color: var(--accent); animation: spin 1s linear infinite; vertical-align: middle; }
        @keyframes spin { to { transform: rotate(360deg); } }

        .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.72); display: none; justify-content: center; align-items: center; z-index: 1000; padding: 24px; }
        .modal-overlay.active { display: flex; }
        .modal { background: var(--bg); border: 2px solid var(--line); width: min(920px, 100%); max-height: 88vh; overflow: auto; color: var(--text); }
        .modal-header { padding: 22px 26px; border-bottom: 2px solid var(--line); display: flex; justify-content: space-between; gap: 20px; align-items: center; }
        .modal-title { font-size: 28px; font-weight: 500; }
        .modal-close { border: 0; padding: 0 8px; color: var(--accent); font-size: 42px; }
        .modal-body { padding: 26px; }
        .message-detail { display: grid; gap: 20px; }
        .detail-label { color: var(--accent); text-transform: uppercase; letter-spacing: .04em; font-size: 13px; margin-bottom: 6px; }
        .detail-value { color: var(--text); word-break: break-word; }
        .message-body { border-top: 2px solid var(--line); padding-top: 18px; white-space: pre-wrap; color: var(--muted); line-height: 1.55; }

        @media (max-width: 1100px) {
            .status-pill { position: static; margin-top: 28px; display: block; }
            .content-grid { grid-template-columns: 1fr; }
        }
        @media (max-width: 760px) {
            .container { padding: 34px 22px 50px; }
            .hero { padding-bottom: 30px; }
            .subtitle { margin-top: 28px; }
            .stats-grid, .toolbar { grid-template-columns: 1fr; text-align: left; gap: 24px; }
            .stats-grid { padding: 34px 0; }
            .stat-label { margin-top: 18px; }
            button { width: 100%; }
        }
    </style>
</head>
<body>
    <main class="container">
        <header class="hero">
            <div class="eyebrow">Paperclip Mail Agent</div>
            <h1>E-Mail Dashboard</h1>
            <p class="subtitle">Ein ruhiger, klarer Überblick über Inbox, Entwürfe und gesendete Nachrichten.</p>
            <div class="status-pill" id="lastUpdated">Noch nicht aktualisiert</div>
        </header>

        <section class="stats-grid" aria-label="Kennzahlen">
            <div class="stat-card"><span class="stat-value" id="inboxCount">-</span><span class="stat-label">Inbox</span><span class="stat-description">Eingegangene Nachrichten</span></div>
            <div class="stat-card"><span class="stat-value" id="draftsCount">-</span><span class="stat-label">Entwürfe</span><span class="stat-description">Gespeicherte Entwürfe</span></div>
            <div class="stat-card"><span class="stat-value" id="sentCount">-</span><span class="stat-label">Gesendet</span><span class="stat-description">Versendete Nachrichten</span></div>
        </section>

        <section class="toolbar" aria-label="Filter und Aktionen">
            <div class="search-box"><input type="email" id="emailFilter" placeholder="🔎 Nach E-Mail-Adresse filtern" autocomplete="off"></div>
            <button class="button-primary" id="refreshButton" type="button"><span class="loading" id="refreshLoading" style="display:none"></span><span id="refreshText">Aktualisieren</span></button>
            <button id="clearButton" type="button">Filter zurücksetzen</button>
        </section>

        <section class="content-grid" aria-label="Nachrichten nach Ordnern">
            <article class="panel" data-folder-kind="inbox"><div class="panel-header"><span class="folder-badge" id="inboxBadge">{inbox_folder}</span><span class="panel-title">Inbox</span></div><div class="message-list" id="inboxList"></div></article>
            <article class="panel" data-folder-kind="drafts"><div class="panel-header"><span class="folder-badge" id="draftsBadge">{drafts_folder}</span><span class="panel-title">Entwürfe</span></div><div class="message-list" id="draftsList"></div></article>
            <article class="panel" data-folder-kind="sent"><div class="panel-header"><span class="folder-badge" id="sentBadge">{sent_folder}</span><span class="panel-title">Gesendet</span></div><div class="message-list" id="sentList"></div></article>
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
        var folderPanels = [
            { folder: INBOX_FOLDER, listId: 'inboxList', badgeId: 'inboxBadge', label: 'Inbox' },
            { folder: DRAFTS_FOLDER, listId: 'draftsList', badgeId: 'draftsBadge', label: 'Entwürfe' },
            { folder: SENT_FOLDER, listId: 'sentList', badgeId: 'sentBadge', label: 'Gesendet' }
        ];

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
            document.getElementById('lastUpdated').textContent = '↪ Aktualisiert: ' + new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
        }

        async function loadFolder(panel) {
            var folder = panel.folder;
            var targetElementId = panel.listId;
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
                updatePanelCount(panel, data.returned || 0);
            } catch (error) {
                console.error('Error loading folder:', folder, error);
                listEl.innerHTML = '<div class="error-message">⚠️ Fehler beim Laden der Nachrichten<br>Die Nachrichten konnten nicht geladen werden. Bitte versuchen Sie es erneut.</div>';
            }
        }

        function createMessageItemHtml(item, folder, itemId) {
            item.folder = folder;
            messageStore.set(itemId, item);
            return '<button type="button" class="message-item" data-message-id="' + esc(itemId) + '">' +
                '<div class="message-header"><span class="message-subject">' + esc(item.subject || '(kein Betreff)') + '</span> <span class="message-date">' + esc(formatDate(item.received_at)) + '</span></div>' +
                '<div class="message-meta"><span>Von: ' + esc(item.from_email || '-') + '</span><span class="to-line">An: ' + esc(item.to_email || '-') + '</span></div>' +
                '<div class="message-snippet">' + esc(truncate(item.snippet || item.body_text || '', 220)) + '</div>' +
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
                messageStore.clear();
                await Promise.all(folderPanels.map(loadFolder));
                await loadSummary();
            } catch (error) {
                console.error('Error loading dashboard:', error);
            } finally {
                setRefreshState(false);
            }
        }

        function updatePanelCount(panel, count) {
            document.getElementById(panel.badgeId).textContent = panel.folder + ' (' + count + ')';
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
