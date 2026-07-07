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
            --bg-primary: #0b1020;
            --bg-secondary: #131b33;
            --bg-card: #1b2547;
            --bg-hover: #253465;
            --text-primary: #edf2ff;
            --text-secondary: #adc0f8;
            --text-muted: #7a8bb8;
            --accent: #6ea8fe;
            --accent-hover: #8ab4ff;
            --success: #59d39b;
            --warning: #f5a623;
            --danger: #ff6b6b;
            --border: #2e3f75;
            --shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
            --shadow-lg: 0 12px 32px rgba(0, 0, 0, 0.35);
            --radius: 14px;
            --radius-sm: 10px;
            --transition: all 0.2s ease;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, Oxygen, Ubuntu, sans-serif;
            background: radial-gradient(circle at top right, #1b2b57 0%, #0b1020 50%, #070b18 100%);
            color: var(--text-primary);
            min-height: 100vh;
            line-height: 1.6;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
        }

        header {
            margin-bottom: 32px;
        }

        h1 {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 8px;
            background: linear-gradient(135deg, var(--accent), var(--success));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .subtitle {
            color: var(--text-secondary);
            font-size: 16px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 32px;
        }

        .stat-card {
            background: linear-gradient(160deg, var(--bg-card), var(--bg-secondary));
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 24px;
            box-shadow: var(--shadow);
            transition: var(--transition);
            position: relative;
            overflow: hidden;
        }

        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--accent), var(--success));
        }

        .stat-card:hover {
            transform: translateY(-4px);
            box-shadow: var(--shadow-lg);
        }

        .stat-label {
            font-size: 14px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
            font-weight: 600;
        }

        .stat-value {
            font-size: 42px;
            font-weight: 800;
            color: var(--success);
            display: block;
        }

        .toolbar {
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
            align-items: center;
            margin-bottom: 24px;
            padding: 20px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: var(--radius);
        }

        .search-box {
            flex: 1;
            min-width: 280px;
            max-width: 400px;
        }

        input[type="text"],
        input[type="email"] {
            width: 100%;
            background: var(--bg-primary);
            color: var(--text-primary);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            padding: 12px 16px;
            font-size: 15px;
            transition: var(--transition);
        }

        input[type="text"]:focus,
        input[type="email"]:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 3px rgba(110, 168, 254, 0.2);
        }

        button {
            background: linear-gradient(135deg, var(--bg-card), var(--bg-hover));
            color: var(--text-primary);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            padding: 12px 20px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: var(--transition);
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        button:hover {
            background: linear-gradient(135deg, var(--bg-hover), var(--bg-card));
            border-color: var(--accent);
            transform: translateY(-2px);
        }

        button:active {
            transform: translateY(0);
        }

        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }

        .content-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 24px;
        }

        .panel {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            overflow: hidden;
            box-shadow: var(--shadow);
        }

        .panel-header {
            padding: 16px 20px;
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .panel-title {
            font-size: 18px;
            font-weight: 700;
            color: var(--text-primary);
        }

        .panel-count {
            background: var(--bg-primary);
            color: var(--text-secondary);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
        }

        .panel-body {
            padding: 0;
            max-height: 60vh;
            overflow: auto;
        }

        .message-list {
            display: grid;
            gap: 1px;
        }

        .message-item {
            background: var(--bg-primary);
            border-bottom: 1px solid var(--border);
            padding: 16px 20px;
            cursor: pointer;
            transition: var(--transition);
            position: relative;
        }

        .message-item:last-child {
            border-bottom: none;
        }

        .message-item:hover {
            background: var(--bg-hover);
        }

        .message-item.unread {
            background: linear-gradient(90deg, rgba(110, 168, 254, 0.15), transparent);
            border-left: 4px solid var(--accent);
        }

        .message-item.unread:hover {
            background: linear-gradient(90deg, rgba(110, 168, 254, 0.25), var(--bg-hover));
        }

        .message-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 8px;
        }

        .message-subject {
            font-size: 16px;
            font-weight: 600;
            color: var(--text-primary);
            word-break: break-word;
            flex: 1;
            margin-right: 12px;
        }

        .message-date {
            color: var(--text-muted);
            font-size: 13px;
            white-space: nowrap;
            text-align: right;
        }

        .message-meta {
            display: flex;
            gap: 16px;
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 8px;
            flex-wrap: wrap;
        }

        .message-meta span {
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }

        .message-snippet {
            color: var(--text-muted);
            font-size: 14px;
            line-height: 1.5;
            white-space: pre-wrap;
            word-break: break-word;
            max-height: 60px;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 1000;
            padding: 20px;
        }

        .modal-overlay.active {
            display: flex;
        }

        .modal {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            width: 100%;
            max-width: 800px;
            max-height: 85vh;
            overflow: auto;
            box-shadow: var(--shadow-lg);
            animation: modalSlideIn 0.3s ease;
        }

        @keyframes modalSlideIn {
            from {
                opacity: 0;
                transform: translateY(-20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .modal-header {
            padding: 20px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--bg-card);
        }

        .modal-title {
            font-size: 20px;
            font-weight: 700;
            color: var(--text-primary);
        }

        .modal-close {
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 28px;
            cursor: pointer;
            padding: 4px 8px;
            line-height: 1;
        }

        .modal-close:hover {
            color: var(--danger);
        }

        .modal-body {
            padding: 24px;
        }

        .message-detail {
            display: grid;
            gap: 20px;
        }

        .detail-section {
            border-bottom: 1px solid var(--border);
            padding-bottom: 20px;
        }

        .detail-section:last-child {
            border-bottom: none;
            padding-bottom: 0;
        }

        .detail-label {
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4px;
            font-weight: 600;
        }

        .detail-value {
            color: var(--text-primary);
            font-size: 15px;
            word-break: break-word;
        }

        .message-body {
            background: var(--bg-primary);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            padding: 16px;
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.6;
            max-height: 400px;
            overflow: auto;
        }

        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid var(--border);
            border-radius: 50%;
            border-top-color: var(--accent);
            animation: spin 1s ease-in-out infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .loading-overlay {
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 40px;
            color: var(--text-secondary);
        }

        .error-message {
            color: var(--danger);
            padding: 16px;
            text-align: center;
            font-size: 14px;
        }

        .empty-state {
            text-align: center;
            padding: 40px 20px;
            color: var(--text-muted);
        }

        .empty-state-icon {
            font-size: 48px;
            margin-bottom: 12px;
        }

        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }

        .badge-inbox {
            background: rgba(90, 150, 255, 0.2);
            color: #8ab4ff;
        }

        .badge-drafts {
            background: rgba(255, 193, 7, 0.2);
            color: #ffc107;
        }

        .badge-sent {
            background: rgba(89, 211, 155, 0.2);
            color: #59d39b;
        }

        @media (max-width: 1024px) {
            .content-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        @media (max-width: 768px) {
            .container {
                padding: 16px;
            }

            h1 {
                font-size: 24px;
            }

            .stats-grid {
                grid-template-columns: repeat(3, 1fr);
            }

            .stat-value {
                font-size: 32px;
            }

            .content-grid {
                grid-template-columns: 1fr;
            }

            .toolbar {
                flex-direction: column;
                align-items: stretch;
            }

            .search-box {
                max-width: none;
            }

            button {
                width: 100%;
            }}
        }

        @media (max-width: 480px) {
            .stats-grid {
                grid-template-columns: 1fr;
            }

            .stat-value {
                font-size: 28px;
            }

            .message-item {
                padding: 12px 16px;
            }

            .modal {
                margin: 0;
                border-radius: 0;
            }}
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>SMTP Gateway Dashboard</h1>
            <p class="subtitle">Inbox, Entwürfe und Gesendet im Live-Überblick</p>
        </header>

        <div class="stats-grid">
            <div class="stat-card">
                <span class="stat-label">Inbox</span>
                <span class="stat-value" id="inboxCount">-</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Entwürfe</span>
                <span class="stat-value" id="draftsCount">-</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Gesendet</span>
                <span class="stat-value" id="sentCount">-</span>
            </div>
        </div>

        <div class="toolbar">
            <div class="search-box">
                <input type="email" id="emailFilter" placeholder="Filter nach E-Mail-Adresse (z.B. user@example.com)" onkeypress="if(event.key==='Enter') loadAllFolders()">
            </div>
            <button onclick="loadAllFolders()">
                <span class="loading" id="refreshLoading" style="display:none"></span>
                <span id="refreshText">Alle aktualisieren</span>
            </button>
            <button onclick="clearFilter()">Filter zurücksetzen</button>
        </div>

        <div class="content-grid">
            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">Inbox</span>
                    <span class="badge badge-inbox">{inbox_folder}</span>
                </div>
                <div class="panel-body">
                    <div class="message-list" id="inboxList">
                        <div class="loading-overlay">
                            <span class="loading"></span>
                            <span style="margin-left:12px">Lade Nachrichten...</span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">Entwürfe</span>
                    <span class="badge badge-drafts">{drafts_folder}</span>
                </div>
                <div class="panel-body">
                    <div class="message-list" id="draftsList">
                        <div class="loading-overlay">
                            <span class="loading"></span>
                            <span style="margin-left:12px">Lade Nachrichten...</span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">Gesendet</span>
                    <span class="badge badge-sent">{sent_folder}</span>
                </div>
                <div class="panel-body">
                    <div class="message-list" id="sentList">
                        <div class="loading-overlay">
                            <span class="loading"></span>
                            <span style="margin-left:12px">Lade Nachrichten...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="messageModal">
        <div class="modal">
            <div class="modal-header">
                <span class="modal-title" id="modalTitle">Nachrichtendetails</span>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="message-detail" id="modalContent"></div>
            </div>
        </div>
    </div>

    <script>
        var INBOX_FOLDER = '{inbox_folder}';
        var DRAFTS_FOLDER = '{drafts_folder}';
        var SENT_FOLDER = '{sent_folder}';

        function esc(s) {
            if (!s) return '';
            return String(s)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function formatDate(dateString) {
            if (!dateString) return '-';
            try {
                var date = new Date(dateString);
                return date.toLocaleString('de-DE', {
                    day: '2-digit',
                    month: '2-digit',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            } catch (e) {
                return dateString;
            }
        }

        function formatRelativeTime(dateString) {
            if (!dateString) return '';
            try {
                var date = new Date(dateString);
                var now = new Date();
                var diff = now - date;
                var seconds = Math.floor(diff / 1000);
                var minutes = Math.floor(seconds / 60);
                var hours = Math.floor(minutes / 60);
                var days = Math.floor(hours / 24);
                
                if (days > 0) return 'vor ' + days + ' Tag' + (days > 1 ? 'en' : '');
                if (hours > 0) return 'vor ' + hours + ' Std.';
                if (minutes > 0) return 'vor ' + minutes + ' Min.';
                return 'gerade eben';
            } catch (e) {
                return '';
            }
        }

        function truncate(text, length) {
            if (!text || text.length <= length) return text;
            return text.substring(0, length) + '...';
        }

        function showLoading(elementId, show) {
            var loadingEl = document.getElementById(elementId + 'Loading');
            var textEl = document.getElementById(elementId + 'Text');
            if (loadingEl) loadingEl.style.display = show ? 'inline-block' : 'none';
            if (textEl) textEl.style.display = show ? 'none' : 'inline';
        }

        async function loadSummary() {
            try {
                var response = await fetch('/dashboard/summary');
                if (!response.ok) throw new Error('Failed to load summary');
                var data = await response.json();
                
                document.getElementById('inboxCount').textContent = data.inbox_count || 0;
                document.getElementById('draftsCount').textContent = data.drafts_count || 0;
                document.getElementById('sentCount').textContent = data.sent_count || 0;
                
                updatePanelCounts();
            } catch (error) {
                console.error('Error loading summary:', error);
                showError('inboxList', 'Fehler beim Laden der Zusammenfassung');
            }
        }

        async function loadFolder(folder, targetElementId, showLoadingState) {
            var email = document.getElementById('emailFilter').value || null;
            var listEl = document.getElementById(targetElementId);
            
            if (showLoadingState) {
                listEl.innerHTML = '<div class="loading-overlay"><span class="loading"></span><span style="margin-left:12px">Lade Nachrichten...</span></div>';
            }
            
            try {
                var response = await fetch('/emails/messages', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        folder: folder,
                        email_address: email,
                        limit: 50
                    })
                });
                
                if (!response.ok) throw new Error('Failed to load messages');
                
                var data = await response.json();
                
                if (!data.items || data.items.length === 0) {
                    listEl.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📭</div><div>Keine Nachrichten gefunden</div></div>';
                    return;
                }
                
                listEl.innerHTML = data.items.map(function(item) {
                    return createMessageItemHtml(item, folder);
                }).join('');
                
                updatePanelCounts();
                
            } catch (error) {
                console.error('Error loading folder:', folder, error);
                showError(targetElementId, 'Fehler beim Laden der Nachrichten');
            }
        }

        function createMessageItemHtml(item, folder) {
            var isUnread = !item.received_at;
            var folderClass = 'badge-' + folder.toLowerCase();
            
            return '<div class="message-item ' + (isUnread ? 'unread' : '') + '" onclick=\'showMessageDetail(' + JSON.stringify(item).replace(/"/g, '&quot;') + ')\'>' +
                '<div class="message-header">' +
                '<span class="message-subject">' + esc(item.subject || '(kein Betreff)') + '</span>' +
                '<span class="message-date">' + formatDate(item.received_at) + '</span>' +
                '</div>' +
                '<div class="message-meta">' +
                '<span>📧 ' + esc(item.from_email) + '</span>' +
                '<span>📤 ' + esc(item.to_email) + '</span>' +
                '<span class="badge ' + folderClass + '">' + esc(folder) + '</span>' +
                '</div>' +
                '<div class="message-snippet">' + esc(truncate(item.snippet || item.body_text || '', 150)) + '</div>' +
                '</div>';
        }

        function showMessageDetail(item) {
            var modal = document.getElementById('messageModal');
            var modalTitle = document.getElementById('modalTitle');
            var modalContent = document.getElementById('modalContent');
            
            modalTitle.textContent = esc(item.subject || '(kein Betreff)');
            
            var html = '<div class="detail-section">' +
                '<div class="detail-label">Absender</div>' +
                '<div class="detail-value">' + esc(item.from_email) + '</div>' +
                '</div>' +
                '<div class="detail-section">' +
                '<div class="detail-label">Empfänger</div>' +
                '<div class="detail-value">' + esc(item.to_email) + '</div>' +
                '</div>' +
                '<div class="detail-section">' +
                '<div class="detail-label">Datum</div>' +
                '<div class="detail-value">' + formatDate(item.received_at) + ' (' + formatRelativeTime(item.received_at) + ')</div>' +
                '</div>' +
                '<div class="detail-section">' +
                '<div class="detail-label">Message-ID</div>' +
                '<div class="detail-value" style="font-family: monospace; font-size: 12px;">' + esc(item.message_id) + '</div>' +
                '</div>' +
                '<div class="detail-section">' +
                '<div class="detail-label">Ordner</div>' +
                '<div class="detail-value"><span class="badge badge-' + item.folder.toLowerCase() + '">' + esc(item.folder) + '</span></div>' +
                '</div>' +
                '<div class="detail-section">' +
                '<div class="detail-label">Betreff</div>' +
                '<div class="detail-value">' + esc(item.subject || '(kein Betreff)') + '</div>' +
                '</div>' +
                '<div class="detail-section">' +
                '<div class="detail-label">Nachrichten-Text</div>' +
                '<div class="message-body">' + esc(item.body_text || '(kein Text)') + '</div>' +
                '</div>';
            
            if (item.snippet) {
                html += '<div class="detail-section">' +
                    '<div class="detail-label">Vorschau</div>' +
                    '<div class="detail-value">' + esc(item.snippet) + '</div>' +
                    '</div>';
            }
            
            modalContent.innerHTML = html;
            modal.classList.add('active');
        }

        function closeModal() {
            document.getElementById('messageModal').classList.remove('active');
        }

        async function loadAllFolders() {
            showLoading('refresh', true);
            
            try {
                await Promise.all([
                    loadFolder(INBOX_FOLDER, 'inboxList', false),
                    loadFolder(DRAFTS_FOLDER, 'draftsList', false),
                    loadFolder(SENT_FOLDER, 'sentList', false)
                ]);
                await loadSummary();
            } catch (error) {
                console.error('Error loading all folders:', error);
            } finally {
                showLoading('refresh', false);
            }
        }

        function clearFilter() {
            document.getElementById('emailFilter').value = '';
            loadAllFolders();
        }

        function showError(elementId, message) {
            var el = document.getElementById(elementId);
            if (el) {
                el.innerHTML = '<div class="error-message">' + esc(message) + '</div>';
            }
        }

        function updatePanelCounts() {
            var inboxCount = document.querySelectorAll('#inboxList .message-item').length;
            var draftsCount = document.querySelectorAll('#draftsList .message-item').length;
            var sentCount = document.querySelectorAll('#sentList .message-item').length;
            
            var inboxBadge = document.querySelector('.badge-inbox');
            var draftsBadge = document.querySelector('.badge-drafts');
            var sentBadge = document.querySelector('.badge-sent');
            
            if (inboxBadge) inboxBadge.textContent = INBOX_FOLDER + ' (' + inboxCount + ')';
            if (draftsBadge) draftsBadge.textContent = DRAFTS_FOLDER + ' (' + draftsCount + ')';
            if (sentBadge) sentBadge.textContent = SENT_FOLDER + ' (' + sentCount + ')';
        }

        document.getElementById('messageModal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeModal();
            }
        });

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeModal();
            }
        });

        loadAllFolders();
        setInterval(loadSummary, 60000);
    </script>
</body>
</html>
"""


@app.get('/dashboard', response_class=HTMLResponse)
def dashboard() -> str:
    inbox_folder = settings.IMAP_INBOX_FOLDER
    drafts_folder = settings.IMAP_DRAFTS_FOLDER
    sent_folder = settings.IMAP_SENT_FOLDER
    
    return DASHBOARD_HTML.format(
        inbox_folder=esc(inbox_folder),
        drafts_folder=esc(drafts_folder),
        sent_folder=esc(sent_folder)
    )


def esc(s):
    """Escape HTML special characters."""
    if not s:
        return ''
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;')


@app.post('/paperclip/webhook')
def paperclip_webhook(payload: PaperclipWebhookPayload) -> dict:
    logger.info('Webhook event received: %s', payload.event)
    return {'status': 'ok'}
