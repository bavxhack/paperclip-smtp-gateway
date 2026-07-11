from fastapi.testclient import TestClient

from app.main import app


def test_health_ok() -> None:
    client = TestClient(app)
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_dashboard_keeps_imap_folder_names_unescaped_in_javascript(monkeypatch) -> None:
    from app import main

    monkeypatch.setattr(main.settings, 'IMAP_DRAFTS_FOLDER', 'Entw&APw-rfe')
    client = TestClient(app)

    response = client.get('/dashboard')

    assert response.status_code == 200
    assert 'id="draftsBadge">Entw&amp;APw-rfe (0)</span>' in response.text
    assert 'var DRAFTS_FOLDER = "Entw&APw-rfe";' in response.text
    assert 'var DRAFTS_FOLDER = "Entw&amp;APw-rfe";' not in response.text
