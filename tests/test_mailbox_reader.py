from __future__ import annotations

from contextlib import contextmanager

from app.config import Settings
from app.mailbox_reader import MailboxReader
from app.models import EmailMessagesQuery


class FallbackClient:
    def __init__(self) -> None:
        self.selected: list[str] = []

    def select(self, folder: str):  # type: ignore[no-untyped-def]
        self.selected.append(folder)
        if folder == 'Entwurf APNR RFA':
            return 'OK', []
        return 'NO', []

    def search(self, *_args):  # type: ignore[no-untyped-def]
        return 'OK', [b'']


class FallbackImapClient:
    def __init__(self) -> None:
        self.client = FallbackClient()

    @contextmanager
    def connect(self):  # type: ignore[no-untyped-def]
        yield self.client

    def list_folders(self) -> list[str]:
        return ['INBOX', 'Entwurf APNR RFA', 'Sent']


def test_fetch_messages_uses_matching_draft_folder_when_configured_folder_fails() -> None:
    imap_client = FallbackImapClient()
    reader = MailboxReader(Settings(), imap_client)  # type: ignore[arg-type]

    items, total = reader.fetch_messages(EmailMessagesQuery(folder='Drafts'))

    assert items == []
    assert total == 0
    assert imap_client.client.selected == ['Drafts', 'Entwurf APNR RFA']
