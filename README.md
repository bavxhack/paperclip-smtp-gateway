# paperclip-mail-agent

Docker-based FastAPI service that acts as a secure mail gateway between Paperclip AI and ALL-INKL IMAP/SMTP (or Thunderbird drafts).

## Project purpose
- Runs **next to** Paperclip AI as a dedicated mail agent.
- Writes drafts into the IMAP drafts folder (for example, for Thunderbird).
- Reads incoming replies via IMAP and exposes them unmodified for Paperclip AI.
- Supports threading (`Message-ID`, `In-Reply-To`, `References`, `Re:` subject).

## Security principle
**Never send automatically.**
- No SMTP send endpoint.
- No sending logic is implemented.
- Reply emails are stored as drafts only.
- Logging is defensive (no passwords, no full sensitive content).

## API endpoints
- `GET /health`
- `GET /imap/folders`
- `POST /drafts/create`
- `POST /replies/poll`
- `POST /paperclip/webhook`

## Setup with Docker Compose
```bash
cp .env.example .env
# Fill .env with real credentials
docker compose -f docker-compose.example.yml up -d
```

## Environment variables
See `.env.example`.

Important variables:
- `PAPERCLIP_BASE_URL`, `PAPERCLIP_API_KEY`
- `IMAP_*` for inbox/drafts access
- `DRY_RUN=true` for safe tests without writing drafts

ALL-INKL defaults:
- `IMAP_HOST=imap.kasserver.com`
- `IMAP_PORT=993`
- `SMTP_HOST=smtp.kasserver.com`
- `SMTP_PORT=465`

## Find the ALL-INKL / Thunderbird drafts folder
1. Call `GET /imap/folders`.
2. Check the actual drafts folder name (`Drafts`, `Entwürfe`, etc.).
3. Set the value in `IMAP_DRAFTS_FOLDER`.

## Example: POST /drafts/create
```bash
curl -X POST http://localhost:8088/drafts/create \
  -H "Content-Type: application/json" \
  -d '{
    "to": "lead@example.com",
    "subject": "Quick question",
    "body_text": "Hello ...",
    "body_html": "<p>Hello ...</p>",
    "from_email": "me@example.com",
    "reply_to_message_id": null,
    "references": null
  }'
```

Response:
```json
{
  "status": "created",
  "folder": "Drafts"
}
```

## Example: POST /replies/poll
```bash
curl -X POST http://localhost:8088/replies/poll
```

Request body (optional filters):
```json
{
  "message_id": "<abc@example.com>",
  "from_email": "lead@example.com"
}
```

Behavior:
- Reads unread replies (`UNSEEN`) from `IMAP_INBOX_FOLDER`.
- Does **not** evaluate/classify and does **not** auto-generate a reply.
- Returns reply data including `message_id` so Paperclip AI can load thread history.
- Optional filtering by `from_email` for all matching emails.
- Does not mark anything as deleted.

## Paperclip agent abstraction
- If `PAPERCLIP_BASE_URL` is set: use the external Paperclip agent.
- If not set: use the local dummy responder.

## GHCR usage
Image name:
`ghcr.io/<github_owner>/paperclip-mail-agent`

Pull example:
```bash
docker pull ghcr.io/<github_owner>/paperclip-mail-agent:latest
```

Docker Compose with prebuilt GHCR image:
```yaml
services:
  paperclip-mail-agent:
    image: ghcr.io/<github_owner>/paperclip-mail-agent:latest
    env_file: [.env]
    ports: ["8088:8088"]
```

## GitHub Actions release/publish
Workflow: `.github/workflows/docker-publish.yml`
- runs on push to `main`
- runs on tags `v*.*.*`
- builds/pushes to GHCR
- tags: `latest` (main), `sha`, `semver`

## GDPR / cold email / human in the loop
- This service is a technical tool for draft automation.
- Verify data privacy, competition law, and industry requirements before production use.
- Sending approval should always be done by a human (human in the loop).
- **No legal advice.**
