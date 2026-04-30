# Interface Specification: paperclip-smtp-gateway

## 1) HTTP API Endpoints

### GET /health
- Response 200:
  - `status`: Literal `"ok"`

### GET /imap/folders
- Purpose: list available IMAP folders.
- Response 200:
  - not typed in `app/models.py`; depends on implementation in `app/main.py`.

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
  - `items`: `ReplyItem[]` (all matched messages from inbox polling)
  - `unseen_items`: `ReplyItem[]` (subset of `items`, only unread messages)

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
  - depends on implementation in `app/main.py`.

## 2) Standard error object
- `ErrorResponse`:
  - `detail`: `str`

## 3) Paperclip integration contract (outbound)

If `PAPERCLIP_BASE_URL` is set, the service uses `PaperclipAgent`:

- HTTP request:
  - Method: `POST`
  - URL: `{PAPERCLIP_BASE_URL}/generate`
  - Header: `Authorization: Bearer <PAPERCLIP_API_KEY>` (only if API key exists)
  - JSON body:
    - `text`: `str` (incoming_text)

- Expected response JSON:
  - `body_text`: `str` (fallback: `""` if not present)
  - `body_html`: `str | null`

- Timeout:
  - Total: 15.0s
  - Connect: 5.0s

If `PAPERCLIP_BASE_URL` is **not** set, the service uses `DummyResponder` with locally generated `body_text`.
