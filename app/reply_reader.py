from __future__ import annotations

import email
import logging
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from app.config import Settings
from app.imap_client import ImapClient
from app.models import ReplyItem, RepliesPollRequest

logger = logging.getLogger(__name__)


class ReplyReader:
    def __init__(self, settings: Settings, imap_client: ImapClient) -> None:
        self.settings = settings
        self.imap_client = imap_client

    def poll_replies(self, filters: RepliesPollRequest) -> tuple[list[ReplyItem], list[ReplyItem]]:
        items: list[ReplyItem] = []
        unseen_items: list[ReplyItem] = []

        with self.imap_client.connect() as client:
            status, _ = client.select(self.settings.IMAP_INBOX_FOLDER)
            if status != 'OK':
                raise RuntimeError('Could not select inbox folder')

            status, data = client.search(None, 'ALL')
            if status != 'OK':
                raise RuntimeError('Could not search messages')

            status, unseen_data = client.search(None, 'UNSEEN')
            if status != 'OK':
                raise RuntimeError('Could not search unread messages')

            ids = (data[0].split() if data and data[0] else [])[: self.settings.POLL_LIMIT]
            unseen_ids = set((unseen_data[0].split() if unseen_data and unseen_data[0] else [])[: self.settings.POLL_LIMIT])

            for mail_id in ids:
                status, msg_data = client.fetch(mail_id, '(RFC822)')
                if status != 'OK' or not msg_data:
                    continue

                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                subject = str(make_header(decode_header(msg.get('Subject', ''))))
                from_email = msg.get('From', '')
                message_id = msg.get('Message-ID', '')
                in_reply_to = msg.get('In-Reply-To')
                references = msg.get('References')
                received_at = self._parse_date(msg.get('Date'))
                text = self._extract_text(msg)

                item = ReplyItem(
                    message_id=message_id,
                    from_email=from_email,
                    subject=subject,
                    snippet=text[:200],
                    in_reply_to=in_reply_to,
                    references=references,
                    received_at=received_at,
                )

                if self._matches_filters(item, filters):
                    items.append(item)
                    if mail_id in unseen_ids:
                        unseen_items.append(item)

        logger.info(
            'Polled %s replies including %s unread (no auto-reply/no auto-send).',
            len(items),
            len(unseen_items),
        )
        return items, unseen_items

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
    def _matches_filters(item: ReplyItem, filters: RepliesPollRequest) -> bool:
        if filters.message_id and filters.message_id != item.message_id:
            return False
        if filters.from_email and filters.from_email.lower() not in item.from_email.lower():
            return False
        return True

    @staticmethod
    def _parse_date(date_header: str | None) -> str | None:
        if not date_header:
            return None
        try:
            return parsedate_to_datetime(date_header).isoformat()
        except Exception:
            return None
