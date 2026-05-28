from __future__ import annotations

from contextlib import contextmanager
from email.message import EmailMessage

from app.config import Settings
from app.models import RepliesPollRequest
from app.reply_reader import ReplyReader


class FakeImapClient:
    def __init__(self, messages: dict[bytes, bytes], unseen: list[bytes]) -> None:
        self.messages = messages
        self.unseen = unseen
        self.fetched: list[bytes] = []

    @contextmanager
    def connect(self):
        yield self

    def select(self, folder: str):
        return 'OK', [folder.encode()]

    def search(self, charset, criteria: str):
        if criteria == 'ALL':
            return 'OK', [b' '.join(self.messages.keys())]
        if criteria == 'UNSEEN':
            return 'OK', [b' '.join(self.unseen)]
        raise AssertionError(f'unexpected criteria: {criteria}')

    def fetch(self, mail_id: bytes, query: str):
        self.fetched.append(mail_id)
        return 'OK', [(b'RFC822', self.messages[mail_id])]


def build_message(message_id: str, from_email: str = 'lead@example.com') -> bytes:
    msg = EmailMessage()
    msg['Subject'] = f'Message {message_id}'
    msg['From'] = from_email
    msg['To'] = 'me@example.com'
    msg['Message-ID'] = f'<{message_id}@example.com>'
    msg['Date'] = 'Thu, 28 May 2026 12:00:00 +0000'
    msg.set_content(f'Body {message_id}')
    return msg.as_bytes()


def test_poll_replies_returns_newest_messages_up_to_limit() -> None:
    messages = {str(i).encode(): build_message(str(i)) for i in range(1, 6)}
    fake_imap = FakeImapClient(messages, unseen=[b'4', b'5'])
    reader = ReplyReader(Settings(POLL_LIMIT=3), fake_imap)  # type: ignore[arg-type]

    items, unseen_items = reader.poll_replies(RepliesPollRequest())

    assert [item.message_id for item in items] == ['<5@example.com>', '<4@example.com>', '<3@example.com>']
    assert [item.message_id for item in unseen_items] == ['<5@example.com>', '<4@example.com>']
    assert fake_imap.fetched == [b'5', b'4', b'3']


def test_poll_replies_limit_applies_after_filters() -> None:
    messages = {
        b'1': build_message('1', 'other@example.com'),
        b'2': build_message('2', 'lead@example.com'),
        b'3': build_message('3', 'other@example.com'),
        b'4': build_message('4', 'lead@example.com'),
        b'5': build_message('5', 'other@example.com'),
    }
    fake_imap = FakeImapClient(messages, unseen=[b'2', b'4'])
    reader = ReplyReader(Settings(POLL_LIMIT=10), fake_imap)  # type: ignore[arg-type]

    items, unseen_items = reader.poll_replies(RepliesPollRequest(from_email='lead@example.com', limit=2))

    assert [item.message_id for item in items] == ['<4@example.com>', '<2@example.com>']
    assert [item.message_id for item in unseen_items] == ['<4@example.com>', '<2@example.com>']
    assert fake_imap.fetched == [b'5', b'4', b'3', b'2']
