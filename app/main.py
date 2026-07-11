from __future__ import annotations

import json
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
            --bg: #282d2d;
            --text: #f2f2f0;
            --text-soft: #c9cdcf;
            --text-muted: #9fa6ad;
            --line: #7b8080;
            --panel-line: #666d70;
            --accent: #ad9cf6;
            --accent-deep: #15075f;
            --warning-bg: #554800;
            --warning-text: #fff7c2;
            --danger: #ffdf64;
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            min-height: 100vh;
            background: var(--bg);
            color: var(--text);
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            letter-spacing: -0.02em;
        }

        .container {
            width: min(100%, 1760px);
            margin: 0 auto;
            padding: 86px 96px 96px;
        }

        .topline {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 32px;
        }

        .eyebrow {
            color: var(--accent);
            font-size: 24px;
            font-weight: 500;
            letter-spacing: .02em;
            text-transform: uppercase;
            margin-bottom: 72px;
        }

        h1 {
            margin: 0;
            color: var(--text);
            font-size: clamp(56px, 5vw, 88px);
            font-weight: 450;
            line-height: 1.05;
        }

        .status-pill {
            margin-top: 125px;
            color: var(--text-muted);
            font-size: clamp(22px, 2vw, 34px);
            font-weight: 430;
            white-space: nowrap;
        }

        .subtitle {
            margin: 82px 0 52px;
            color: var(--text-muted);
            font-size: clamp(24px, 2vw, 34px);
            font-weight: 430;
        }

        .rule { border: 0; border-top: 4px solid var(--line); margin: 0; opacity: .9; }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 48px;
            padding: 72px 0 56px;
            border-bottom: 4px solid var(--line);
        }

        .stat-card { text-align: center; }
        .stat-value {
            display: block;
            color: #dfe2e2;
            font-size: clamp(76px, 7vw, 118px);
            font-weight: 360;
            line-height: .9;
            margin-bottom: 44px;
        }
        .stat-label {
            display: block;
            color: #dedfdd;
            font-size: clamp(30px, 2.6vw, 44px);
            font-weight: 650;
            margin-bottom: 20px;
        }
        .stat-description {
            display: block;
            color: #c5c9c9;
            font-size: clamp(22px, 1.9vw, 32px);
            font-weight: 430;
            letter-spacing: 0;
        }

        .toolbar {
            display: grid;
            grid-template-columns: 1fr auto auto;
            align-items: center;
            gap: 16px;
            padding: 84px 0 86px;
        }

        .search-box { position: relative; max-width: 760px; }
        .search-box::before {
            content: '🔎';
            position: absolute;
            left: 0;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            font-size: 31px;
            line-height: 1;
        }

        input[type="email"] {
            width: 100%;
            border: 0;
            border-bottom: 2px solid transparent;
            background: transparent;
            color: var(--text);
            font: inherit;
            font-size: clamp(24px, 2vw, 34px);
            padding: 14px 0 14px 58px;
            outline: none;
        }
        input[type="email"]::placeholder { color: var(--text-muted); opacity: 1; }
        input[type="email"]:focus { border-bottom-color: var(--accent); }

        button {
            min-height: 88px;
            border-radius: 4px;
            padding: 0 34px;
            font-size: clamp(22px, 1.8vw, 32px);
            font-weight: 780;
            cursor: pointer;
            transition: opacity .15s ease, transform .15s ease, border-color .15s ease;
        }
        button:hover { transform: translateY(-1px); }
        button:disabled { opacity: .65; cursor: progress; }
        .button-primary { border: 2px solid var(--accent); background: var(--accent); color: #070510; }
        .button-secondary { border: 2px solid var(--accent); background: transparent; color: var(--accent); }

        .content-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 72px;
        }

        .panel { min-width: 0; }
        .panel-header {
            min-height: 150px;
            border-bottom: 4px solid var(--line);
            margin-bottom: 38px;
        }
        .folder-badge {
            display: inline-block;
            color: var(--text-soft);
            background: var(--accent-deep);
            border: 2px solid var(--accent-deep);
            border-radius: 3px;
            padding: 7px 16px;
            font-size: clamp(17px, 1.3vw, 24px);
            font-weight: 520;
            line-height: 1;
            text-transform: uppercase;
            letter-spacing: -.01em;
            margin-bottom: 14px;
        }
        .panel:nth-child(2) .folder-badge {
            background: transparent;
            border-color: var(--accent);
            color: var(--accent);
        }
        .panel-title {
            display: block;
            color: var(--text);
            font-size: clamp(30px, 2.4vw, 40px);
            font-weight: 560;
        }
        .panel-body { display: grid; gap: 28px; }
        .message-list { display: grid; gap: 28px; }

        .message-item {
            display: block;
            width: 100%;
            text-align: left;
            border: 3px solid var(--panel-line);
            border-left: 12px solid var(--accent);
            border-radius: 3px;
            background: transparent;
            color: inherit;
            padding: 30px 30px 30px 34px;
            min-height: 250px;
            cursor: pointer;
            transition: border-color .15s ease, background .15s ease, transform .15s ease;
        }
        .message-item:hover { border-color: #8a9194; background: rgba(255,255,255,.018); transform: translateY(-1px); }
        .message-header { display: block; margin-bottom: 18px; }
        .message-subject {
            color: #d9dbda;
            font-size: clamp(22px, 1.7vw, 30px);
            font-weight: 760;
            line-height: 1.5;
            word-break: break-word;
        }
        .message-date {
            color: var(--text-muted);
            font-size: clamp(20px, 1.45vw, 28px);
            font-weight: 430;
            margin-left: 6px;
        }
        .message-meta, .message-snippet {
            color: var(--text-muted);
            font-size: clamp(21px, 1.55vw, 29px);
            line-height: 1.48;
            letter-spacing: 0;
        }
        .message-meta { display: block; margin-bottom: 2px; }
        .message-meta span { display: block; }
        .message-snippet {
            display: -webkit-box;
            -webkit-line-clamp: 5;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .loading { display: inline-block; width: 24px; height: 24px; border: 3px solid rgba(173,156,246,.35); border-radius: 50%; border-top-color: var(--accent); animation: spin 1s linear infinite; vertical-align: middle; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .loading-overlay, .empty-state, .error-message {
            color: var(--text-muted);
            font-size: clamp(22px, 1.6vw, 28px);
            line-height: 1.5;
            padding: 38px 0;
        }
        .error-message {
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 24px;
            align-items: start;
            background: var(--warning-bg);
            color: var(--warning-text);
            padding: 30px;
            border-radius: 3px;
        }
        .error-message strong { display: block; color: #fff8d5; font-size: clamp(24px, 1.8vw, 32px); margin-bottom: 8px; }

        .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.72); display: none; justify-content: center; align-items: center; z-index: 1000; padding: 32px; }
        .modal-overlay.active { display: flex; }
        .modal { width: min(980px, 100%); max-height: 88vh; overflow: auto; background: var(--bg); border: 3px solid var(--panel-line); color: var(--text); }
        .modal-header { display: flex; justify-content: space-between; gap: 24px; align-items: center; padding: 30px 36px; border-bottom: 3px solid var(--line); }
        .modal-title { font-size: clamp(28px, 2.4vw, 42px); font-weight: 560; }
        .modal-close { min-height: 0; border: 0; background: transparent; color: var(--accent); font-size: 46px; padding: 0 8px; }
        .modal-body { padding: 34px 36px; }
        .message-detail { display: grid; gap: 28px; }
        .detail-section { border-bottom: 2px solid var(--panel-line); padding-bottom: 22px; }
        .detail-section:last-child { border-bottom: 0; padding-bottom: 0; }
        .detail-label { color: var(--accent); font-size: 16px; text-transform: uppercase; letter-spacing: .04em; margin-bottom: 10px; }
        .detail-value { color: var(--text-soft); font-size: 24px; line-height: 1.45; word-break: break-word; }
        .message-body { color: var(--text-soft); border: 2px solid var(--panel-line); padding: 24px; white-space: pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 20px; line-height: 1.55; max-height: 420px; overflow: auto; }

        @media (max-width: 1200px) {
            .container { padding: 52px 44px; }
            .content-grid { gap: 36px; }
            .toolbar { grid-template-columns: 1fr; justify-items: start; }
        }
        @media (max-width: 900px) {
            .topline { display: block; }
            .eyebrow { margin-bottom: 40px; }
            .status-pill { margin-top: 30px; }
            .stats-grid, .content-grid { grid-template-columns: 1fr; }
            .stats-grid { gap: 34px; }
            .stat-card { text-align: left; }
            button { width: 100%; }
            .toolbar { justify-items: stretch; }
        }
    </style>
</head>
<body>
    <main class="container">
        <header>
            <div class="topline">
                <div>
                    <div class="eyebrow">Paperclip Mail Agent</div>
                    <h1>E-Mail Dashboard</h1>
                </div>
                <div class="status-pill" id="lastUpdated">↪ Aktualisiert: --:--</div>
            </div>
            <p class="subtitle">Ein ruhiger, klarer Überblick über Inbox, Entwürfe und gesendete Nachrichten.</p>
            <hr class="rule">
        </header>

        <section class="stats-grid" aria-label="Kennzahlen">
            <div class="stat-card"><span class="stat-value" id="inboxCount">-</span><span class="stat-label">Inbox</span><span class="stat-description">Eingegangene Nachrichten</span></div>
            <div class="stat-card"><span class="stat-value" id="draftsCount">-</span><span class="stat-label">Entwürfe</span><span class="stat-description">Gespeicherte Entwürfe</span></div>
            <div class="stat-card"><span class="stat-value" id="sentCount">-</span><span class="stat-label">Gesendet</span><span class="stat-description">Versendete Nachrichten</span></div>
        </section>

        <section class="toolbar" aria-label="Filter und Aktionen">
            <div class="search-box"><input type="email" id="emailFilter" placeholder="Nach E-Mail-Adresse filtern" autocomplete="off"></div>
            <button class="button-primary" id="refreshButton" type="button"><span class="loading" id="refreshLoading" style="display:none"></span><span id="refreshText">Aktualisieren</span></button>
            <button class="button-secondary" id="clearButton" type="button">Filter zurücksetzen</button>
        </section>

        <section class="content-grid">
            <article class="panel"><div class="panel-header"><span class="folder-badge" id="inboxBadge">{inbox_folder_html} (0)</span><span class="panel-title">Inbox</span></div><div class="panel-body"><div class="message-list" id="inboxList"></div></div></article>
            <article class="panel"><div class="panel-header"><span class="folder-badge" id="draftsBadge">{drafts_folder_html} (0)</span><span class="panel-title">Entwürfe</span></div><div class="panel-body"><div class="message-list" id="draftsList"></div></div></article>
            <article class="panel"><div class="panel-header"><span class="folder-badge" id="sentBadge">{sent_folder_html} (0)</span><span class="panel-title">Gesendet</span></div><div class="panel-body"><div class="message-list" id="sentList"></div></div></article>
        </section>
    </main>

    <div class="modal-overlay" id="messageModal" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
        <div class="modal"><div class="modal-header"><span class="modal-title" id="modalTitle">Nachrichtendetails</span><button class="modal-close" id="modalClose" type="button" aria-label="Schließen">&times;</button></div><div class="modal-body"><div class="message-detail" id="modalContent"></div></div></div>
    </div>

    <script>
        var INBOX_FOLDER = {inbox_folder_json};
        var DRAFTS_FOLDER = {drafts_folder_json};
        var SENT_FOLDER = {sent_folder_json};
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
        function errorMarkup(folder) { return '<div class="error-message"><span>⚠</span><span><strong>⚠ Fehler beim Laden der Nachrichten</strong>Die Nachrichten aus ' + esc(folder) + ' konnten nicht geladen werden. Bitte versuchen Sie es erneut.</span></div>'; }
        function badgeLabel(folder, count) { return String(folder || '').toUpperCase() + ' (' + count + ')'; }

        async function loadSummary() {
            var response = await fetch('/dashboard/summary');
            if (!response.ok) throw new Error('Zusammenfassung konnte nicht geladen werden');
            var data = await response.json();
            document.getElementById('inboxCount').textContent = data.inbox_count || 0;
            document.getElementById('draftsCount').textContent = data.drafts_count || 0;
            document.getElementById('sentCount').textContent = data.sent_count || 0;
            document.getElementById('lastUpdated').textContent = '↪ Aktualisiert: ' + new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
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
                listEl.innerHTML = errorMarkup(folder);
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
            document.getElementById('inboxBadge').textContent = badgeLabel(INBOX_FOLDER, document.querySelectorAll('#inboxList .message-item').length);
            document.getElementById('draftsBadge').textContent = badgeLabel(DRAFTS_FOLDER, document.querySelectorAll('#draftsList .message-item').length);
            document.getElementById('sentBadge').textContent = badgeLabel(SENT_FOLDER, document.querySelectorAll('#sentList .message-item').length);
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
    replacements = {
        '{inbox_folder_html}': esc(settings.IMAP_INBOX_FOLDER),
        '{drafts_folder_html}': esc(settings.IMAP_DRAFTS_FOLDER),
        '{sent_folder_html}': esc(settings.IMAP_SENT_FOLDER),
        '{inbox_folder_json}': json.dumps(settings.IMAP_INBOX_FOLDER),
        '{drafts_folder_json}': json.dumps(settings.IMAP_DRAFTS_FOLDER),
        '{sent_folder_json}': json.dumps(settings.IMAP_SENT_FOLDER),
    }
    html = DASHBOARD_HTML
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
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
