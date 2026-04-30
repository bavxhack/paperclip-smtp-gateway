from __future__ import annotations

import email
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.config import Settings
from app.imap_client import ImapClient
from app.models import DraftCreateRequest


class DraftWriter:
    def __init__(self, settings: Settings, imap_client: ImapClient) -> None:
        self.settings = settings
        self.imap_client = imap_client

    def create_draft(self, payload: DraftCreateRequest) -> str:
        message = self._build_message(payload)
        if self.settings.DRY_RUN:
            return self.settings.IMAP_DRAFTS_FOLDER

        with self.imap_client.connect() as client:
            res = client.append(
                self.settings.IMAP_DRAFTS_FOLDER,
                '\\Draft',
                None,
                message.as_bytes(),
            )
            if res[0] != 'OK':
                raise RuntimeError('Could not append draft to IMAP folder')

        return self.settings.IMAP_DRAFTS_FOLDER

    def _build_message(self, payload: DraftCreateRequest) -> EmailMessage:
        message = EmailMessage()
        from_name = self.settings.FROM_NAME.strip()
        message['From'] = formataddr((from_name, payload.from_email)) if from_name else payload.from_email
        message['To'] = payload.to
        message['Subject'] = payload.subject
        message['Message-ID'] = make_msgid()

        if payload.reply_to_message_id:
            message['In-Reply-To'] = payload.reply_to_message_id
            references = payload.references or payload.reply_to_message_id
            message['References'] = references
            if not payload.subject.lower().startswith('re:'):
                message.replace_header('Subject', f"Re: {payload.subject}")

        message.set_content(payload.body_text)
        if payload.body_html:
            message.add_alternative(payload.body_html, subtype='html')
        return message
