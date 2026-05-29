from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


class RecordingDraftWriter:
    def __init__(self) -> None:
        self.payload = None

    def create_draft(self, payload):  # type: ignore[no-untyped-def]
        self.payload = payload
        return 'SMTP-Draft'


def test_send_uses_draft_writer_and_returns_sent_status(monkeypatch) -> None:
    writer = RecordingDraftWriter()
    monkeypatch.setattr('app.main.draft_writer', writer)
    client = TestClient(app)

    response = client.post(
        '/send',
        json={
            'to': 'lead@example.com',
            'subject': 'Send via drafts',
            'body_text': 'Hello',
            'from_email': 'me@example.com',
        },
    )

    assert response.status_code == 200
    assert response.json() == {'status': 'sent', 'folder': 'SMTP-Draft'}
    assert writer.payload is not None
    assert writer.payload.to == 'lead@example.com'
    assert writer.payload.subject == 'Send via drafts'
