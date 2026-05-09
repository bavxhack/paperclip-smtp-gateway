# Interface Specification: paperclip-smtp-gateway

## 1) HTTP API Endpoints

### GET /health
- Response 200:
  - `status`: Literal `"ok"`

### GET /imap/folders
- Purpose: list available IMAP folders.
- Response 200:
  - `folders`: `str[]`

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
  - `unseen_items`: `ReplyItem[]`

### POST /emails/messages
- Purpose: retrieve emails from a specific IMAP folder with optional filtering by email address.
- Request (`EmailMessagesQuery`):
  - `folder`: `str` (required, min_length=1, max_length=255)
  - `email_address`: `EmailStr | null` (optional)
  - `limit`: `int` (optional, default `50`, min `1`, max `200`)
- Response 200 (`EmailMessagesResponse`):
  - `status`: Literal `"ok"`
  - `total_in_folder`: `int`
  - `returned`: `int`
  - `items`: `EmailMessageItem[]`

### GET /dashboard/summary
- Purpose: return mailbox KPIs for dashboard.
- Response 200 (`GatewayDashboardResponse`):
  - `status`: Literal `"ok"`
  - `inbox_count`: `int`
  - `drafts_count`: `int`
  - `sent_count`: `int`
  - `recent_activity`: `EmailMessageItem[]`

### GET /dashboard
- Purpose: returns a lightweight HTML dashboard + mini mail-client UI.
- Response 200:
  - `text/html`

### POST /paperclip/webhook
- Request (`PaperclipWebhookPayload`):
  - `event`: `str`
  - `data`: `dict` (default `{}`)
- Response:
  - `{"status":"ok"}`

## 2) Models

`ReplyItem`:
- `message_id`: `str`
- `from_email`: `str`
- `subject`: `str`
- `snippet`: `str`
- `in_reply_to`: `str | null`
- `references`: `str | null`
- `received_at`: `str | null`

`EmailMessageItem`:
- `uid`: `str`
- `folder`: `str`
- `message_id`: `str`
- `from_email`: `str`
- `to_email`: `str`
- `subject`: `str`
- `snippet`: `str`
- `body_text`: `str`
- `received_at`: `str | null`

## 3) Standard error object
- `ErrorResponse`:
  - `detail`: `str`

## 4) Paperclip integration contract (outbound)

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
