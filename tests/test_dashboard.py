from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_dashboard_renders_drafts_middle_column_and_modal() -> None:
    client = TestClient(app)

    response = client.get('/dashboard')

    assert response.status_code == 200
    html = response.text
    inbox_position = html.index('id="inboxList"')
    drafts_position = html.index('id="draftsList"')
    sent_position = html.index('id="sentList"')
    assert inbox_position < drafts_position < sent_position
    assert 'data-folder-kind="drafts"' in html
    assert 'grid-template-columns: repeat(3, minmax(0, 1fr))' in html
    assert '.panel { min-width: 0; overflow: hidden; }' in html
    assert 'overflow-wrap: anywhere' in html
    assert 'var folderPanels = [' in html
    assert "listId: 'draftsList'" in html
    assert "label: 'Entwürfe'" in html
    assert "panel.label + ' (' + count + ')'" in html
    assert 'id="messageModal"' in html
    assert 'function showMessageDetail(itemId)' in html
    assert "showMessageDetail(row.dataset.messageId)" in html
