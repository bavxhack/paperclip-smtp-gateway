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
  - `body_text`: `str` (required, min_length=1). Accepts both real newline characters and literal escaped newline markers (`\\n`, `\\r\\n`, `\\r`); the gateway normalizes escaped markers to real line breaks before writing the draft.
  - `body_html`: `str | null` (optional). If provided, literal escaped newline markers are normalized the same way before writing the HTML draft alternative.
  - `from_email`: `EmailStr` (required)
  - `reply_to_message_id`: `str | null` (optional)
  - `references`: `str | null` (optional)
- Response 200 (`DraftCreateResponse`):
  - `status`: Literal `"created"`
  - `folder`: `str`

### POST /replies/poll
- Purpose: poll replies from `IMAP_INBOX_FOLDER` for Paperclip processing.
- Request (`RepliesPollRequest`):
  - `message_id`: `str | null` (optional; exact match against `ReplyItem.message_id`)
  - `from_email`: `EmailStr | null` (optional; case-insensitive containment match against `ReplyItem.from_email`)
  - `limit`: `int | null` (optional, default uses server `POLL_LIMIT`, min `1`, max `1000`)
- Effective default limit:
  - `POLL_LIMIT`: default `100`, min `1`, max `1000`.
- Polling behavior:
  - Selects `IMAP_INBOX_FOLDER`.
  - Searches `ALL` messages and evaluates them newest-first.
  - Searches `UNSEEN` messages separately to identify unread returned items.
  - Applies `message_id` / `from_email` filters before enforcing the effective limit.
  - Does not delete messages.
- Response 200 (`RepliesPollResponse`):
  - `status`: Literal `"ok"`
  - `processed`: `int` (number of returned `items`)
  - `items`: `ReplyItem[]` (newest matched replies, capped by effective limit)
  - `unseen_items`: `ReplyItem[]` (unread subset of returned `items`)

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

`RepliesPollRequest`:
- `message_id`: `str | null` (optional)
- `from_email`: `EmailStr | null` (optional)
- `limit`: `int | null` (optional, default server `POLL_LIMIT`, min `1`, max `1000`)

`RepliesPollResponse`:
- `status`: Literal `"ok"`
- `processed`: `int`
- `items`: `ReplyItem[]`
- `unseen_items`: `ReplyItem[]`

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

## 3) Runtime settings relevant to interfaces

- `POLL_LIMIT`: default `100`, min `1`, max `1000`; default maximum for `/replies/poll` when the request omits `limit`.
- `IMAP_INBOX_FOLDER`: folder used by `/replies/poll`.
- `IMAP_DRAFTS_FOLDER`: folder used by `/drafts/create`.
- `IMAP_SENT_FOLDER`: folder used by dashboard/message retrieval examples.

## 3.1) Draft newline normalization

For `/drafts/create`, Paperclip clients may send line breaks in either supported form:

- real newline characters, for example JSON-decoded `"Hello\nWorld"`;
- literal escaped newline markers, for example the two characters `\\n` in `"Hello\\\\nWorld"`.

Before creating the MIME draft, the gateway converts literal `\\r\\n`, `\\n`, and `\\r` markers in `body_text` and `body_html` to real `\n` line breaks. This keeps older clients that send literal markers compatible while preserving clients that already send real line breaks.

## 4) Standard error object
- `ErrorResponse`:
  - `detail`: `str`

## 5) Paperclip integration contract (outbound)

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
