from __future__ import annotations

import email
import logging
from email.header import decode_header, make_header

from app.config import Settings
from app.draft_writer import DraftWriter
from app.imap_client import ImapClient
from app.models import DraftCreateRequest, ReplyItem

logger = logging.getLogger(__name__)


class ReplyReader:
    def __init__(self, settings: Settings, imap_client: ImapClient, draft_writer: DraftWriter) -> None:
        self.settings = settings
        self.imap_client = imap_client
        self.draft_writer = draft_writer

    def poll_replies(self) -> tuple[list[ReplyItem], int]:
        items: list[ReplyItem] = []
        created_drafts = 0

        with self.imap_client.connect() as client:
            status, _ = client.select(self.settings.IMAP_INBOX_FOLDER)
            if status != 'OK':
                raise RuntimeError('Could not select inbox folder')

            status, data = client.search(None, 'UNSEEN')
            if status != 'OK':
                raise RuntimeError('Could not search unread messages')

            ids = (data[0].split() if data and data[0] else [])[: self.settings.POLL_LIMIT]

            for mail_id in ids:
                status, msg_data = client.fetch(mail_id, '(RFC822)')
                if status != 'OK' or not msg_data:
                    continue
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                subject = str(make_header(decode_header(msg.get('Subject', ''))))
                from_email = msg.get('From', '')
                message_id = msg.get('Message-ID', '')
                text = self._extract_text(msg)
                classification = self._classify(text)

                item = ReplyItem(
                    message_id=message_id,
                    from_email=from_email,
                    subject=subject,
                    snippet=text[:200],
                    classification=classification,
                )

                if classification in {'interested', 'question'}:
                    draft_payload = DraftCreateRequest(
                        to=self.settings.FROM_EMAIL,
                        subject=subject,
                        body_text='Danke für Ihre Nachricht. Wir melden uns zeitnah mit weiteren Details.',
                        from_email=self.settings.FROM_EMAIL,
                        reply_to_message_id=message_id or None,
                        references=msg.get('References'),
                    )
                    self.draft_writer.create_draft(draft_payload)
                    item.draft_created = True
                    created_drafts += 1

                items.append(item)

        logger.info('Processed %s replies, created %s drafts.', len(items), created_drafts)
        return items, created_drafts

    @staticmethod
    def _extract_text(msg: email.message.Message) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    payload = part.get_payload(decode=True)
                    return (payload or b'').decode(part.get_content_charset() or 'utf-8', errors='ignore').strip()
        payload = msg.get_payload(decode=True)
        return (payload or b'').decode(msg.get_content_charset() or 'utf-8', errors='ignore').strip()

    @staticmethod
    def _classify(text: str) -> str:
        t = text.lower()
        if any(k in t for k in ['unsubscribe', 'abmelden']):
            return 'unsubscribe'
        if any(k in t for k in ['kein interesse', 'not interested', 'no thanks']):
            return 'not_interested'
        if '?' in t or 'frage' in t:
            return 'question'
        if any(k in t for k in ['interesse', 'sounds good', 'let\'s talk']):
            return 'interested'
        return 'unclear'
