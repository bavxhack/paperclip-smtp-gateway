# Schnittstellen-Spezifikation: paperclip-smtp-gateway

## 1) HTTP API Endpoints

### GET /health
- Response 200:
  - `status`: Literal `"ok"`

### GET /imap/folders
- Zweck: verfügbare IMAP-Ordner auflisten.
- Response 200:
  - nicht in `app/models.py` typisiert; von Implementierung in `app/main.py` abhängig.

### POST /drafts/create
- Request (`DraftCreateRequest`):
  - `to`: `EmailStr` (required)
  - `subject`: `str` (required, min_length=1, max_length=998)
  - `body_text`: `str` (required, min_length=1)
  - `body_html`: `str | null` (optional)
  - `from_email`: `EmailStr` (required)
  - `reply_to_message_id`: `str | null` (optional)
  - `references`: `str | null` (optional)
- Response 200 (`DraftCreateResponse`):
  - `status`: Literal `"created"`
  - `folder`: `str`

### POST /replies/poll
- Request (`RepliesPollRequest`):
  - `message_id`: `str | null` (optional)
  - `from_email`: `EmailStr | null` (optional)
- Response 200 (`RepliesPollResponse`):
  - `status`: Literal `"ok"`
  - `processed`: `int`
  - `items`: `ReplyItem[]`

`ReplyItem`:
- `message_id`: `str`
- `from_email`: `str`
- `subject`: `str`
- `snippet`: `str`
- `in_reply_to`: `str | null`
- `references`: `str | null`
- `received_at`: `str | null`

### POST /paperclip/webhook
- Request (`PaperclipWebhookPayload`):
  - `event`: `str`
  - `data`: `dict` (default `{}`)
- Response:
  - von Implementierung in `app/main.py` abhängig.

## 2) Standard-Fehlerobjekt
- `ErrorResponse`:
  - `detail`: `str`

## 3) Integrationsvertrag Paperclip (Outbound)

Wenn `PAPERCLIP_BASE_URL` gesetzt ist, nutzt der Dienst `PaperclipAgent`:

- HTTP Request:
  - Methode: `POST`
  - URL: `{PAPERCLIP_BASE_URL}/generate`
  - Header: `Authorization: Bearer <PAPERCLIP_API_KEY>` (nur falls Key vorhanden)
  - JSON Body:
    - `text`: `str` (incoming_text)

- Erwartete Response JSON:
  - `body_text`: `str` (fallback: `""` wenn nicht vorhanden)
  - `body_html`: `str | null`

- Timeout:
  - Gesamt: 15.0s
  - Connect: 5.0s

Wenn `PAPERCLIP_BASE_URL` **nicht** gesetzt ist, nutzt der Dienst `DummyResponder` mit lokal generiertem `body_text`.
