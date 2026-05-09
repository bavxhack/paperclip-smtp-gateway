from __future__ import annotations

import email
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from app.config import Settings
from app.imap_client import ImapClient
from app.models import EmailMessageItem, EmailMessagesQuery


class MailboxReader:
    def __init__(self, settings: Settings, imap_client: ImapClient) -> None:
        self.settings = settings
        self.imap_client = imap_client

    def fetch_messages(self, query: EmailMessagesQuery) -> tuple[list[EmailMessageItem], int]:
        with self.imap_client.connect() as client:
            status, _ = client.select(query.folder)
            if status != 'OK':
                raise RuntimeError(f'Could not select folder: {query.folder}')

            status, data = client.search(None, 'ALL')
            if status != 'OK':
                raise RuntimeError('Could not search messages')

            raw_ids = data[0].split() if data and data[0] else []
            total = len(raw_ids)
            ids = list(reversed(raw_ids))[: query.limit]

            items: list[EmailMessageItem] = []
            for mail_id in ids:
                status, msg_data = client.fetch(mail_id, '(RFC822)')
                if status != 'OK' or not msg_data:
                    continue

                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                from_email = msg.get('From', '')
                to_email = msg.get('To', '')
                subject = str(make_header(decode_header(msg.get('Subject', ''))))
                message_id = msg.get('Message-ID', '')
                received_at = self._parse_date(msg.get('Date'))
                body_text = self._extract_text(msg)

                item = EmailMessageItem(
                    uid=mail_id.decode('utf-8', errors='ignore'),
                    folder=query.folder,
                    message_id=message_id,
                    from_email=from_email,
                    to_email=to_email,
                    subject=subject,
                    snippet=body_text[:250],
                    body_text=body_text,
                    received_at=received_at,
                )

                if query.email_address and query.email_address.lower() not in (from_email + ' ' + to_email).lower():
                    continue
                items.append(item)

        return items, total

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
    def _parse_date(date_header: str | None) -> str | None:
        if not date_header:
            return None
        try:
            return parsedate_to_datetime(date_header).isoformat()
        except Exception:
            return None
