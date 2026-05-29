from __future__ import annotations

from app.config import Settings
from app.draft_writer import DraftWriter, normalize_draft_newlines
from app.models import DraftCreateRequest


class UnusedImapClient:
    pass


def build_payload(body_text: str, body_html: str | None = None) -> DraftCreateRequest:
    return DraftCreateRequest(
        to='lead@example.com',
        subject='Line breaks',
        body_text=body_text,
        body_html=body_html,
        from_email='me@example.com',
    )


def test_normalize_draft_newlines_accepts_literal_and_real_newlines() -> None:
    assert normalize_draft_newlines('Hello\\nWorld') == 'Hello\nWorld'
    assert normalize_draft_newlines('Hello\nWorld') == 'Hello\nWorld'
    assert normalize_draft_newlines('Hello\\r\\nWorld') == 'Hello\nWorld'


def test_build_message_converts_literal_newlines_in_text_body() -> None:
    writer = DraftWriter(Settings(DRY_RUN=True), UnusedImapClient())  # type: ignore[arg-type]

    message = writer._build_message(build_payload('Hello\\nWorld'))

    assert message.get_content() == 'Hello\nWorld\n'


def test_build_message_converts_literal_newlines_in_html_body() -> None:
    writer = DraftWriter(Settings(DRY_RUN=True), UnusedImapClient())  # type: ignore[arg-type]

    message = writer._build_message(build_payload('Hello\\nWorld', '<p>Hello\\nWorld</p>'))

    assert message.get_body(preferencelist=('plain',)).get_content() == 'Hello\nWorld\n'
    assert message.get_body(preferencelist=('html',)).get_content() == '<p>Hello\nWorld</p>\n'
