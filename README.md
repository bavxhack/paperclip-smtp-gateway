# paperclip-mail-agent

Docker-basierter FastAPI-Service als sicheres Mail-Gateway zwischen Paperclip AI und ALL-INKL IMAP/SMTP bzw. Thunderbird-Drafts.

## Zweck des Projekts
- Betrieb **neben** Paperclip AI als dedizierter Mail-Agent.
- Schreibt Drafts in den IMAP-Drafts-Ordner (z. B. für Thunderbird).
- Liest eingehende Antworten über IMAP und stellt sie unbearbeitet für Paperclip AI bereit.
- Unterstützt Threading (`Message-ID`, `In-Reply-To`, `References`, `Re:` Subject).

## Sicherheitsprinzip
**Niemals automatisch senden.**
- Kein SMTP-Sende-Endpoint.
- Keine Versandlogik implementiert.
- Antwortmails werden ausschließlich als Draft gespeichert.
- Logging ist defensiv gehalten (keine Passwörter, keine kompletten sensitiven Inhalte).

## API Endpoints
- `GET /health`
- `GET /imap/folders`
- `POST /drafts/create`
- `POST /replies/poll`
- `POST /paperclip/webhook`

## Setup mit Docker Compose
```bash
cp .env.example .env
# .env mit echten Zugangsdaten befüllen
docker compose -f docker-compose.example.yml up -d
```

## Environment Variables
Siehe `.env.example`.

Wichtige Variablen:
- `PAPERCLIP_BASE_URL`, `PAPERCLIP_API_KEY`
- `IMAP_*` für Zugriff auf Inbox/Drafts
- `DRY_RUN=true` für sichere Tests ohne Draft-Write

ALL-INKL Defaults:
- `IMAP_HOST=imap.kasserver.com`
- `IMAP_PORT=993`
- `SMTP_HOST=smtp.kasserver.com`
- `SMTP_PORT=465`

## ALL-INKL / Thunderbird Draft-Ordner finden
1. `GET /imap/folders` aufrufen.
2. Prüfen, wie der Drafts-Ordner tatsächlich heißt (`Drafts`, `Entwürfe`, o. ä.).
3. Wert in `IMAP_DRAFTS_FOLDER` setzen.

## Beispiel: POST /drafts/create
```bash
curl -X POST http://localhost:8088/drafts/create \
  -H "Content-Type: application/json" \
  -d '{
    "to": "lead@example.com",
    "subject": "Kurze Frage",
    "body_text": "Hallo ...",
    "body_html": "<p>Hallo ...</p>",
    "from_email": "me@example.com",
    "reply_to_message_id": null,
    "references": null
  }'
```

Antwort:
```json
{
  "status": "created",
  "folder": "Drafts"
}
```

## Beispiel: POST /replies/poll
```bash
curl -X POST http://localhost:8088/replies/poll
```

Request-Body (optional Filter):
```json
{
  "message_id": "<abc@example.com>",
  "from_email": "lead@example.com"
}
```

Verhalten:
- Liest ungelesene Antworten (`UNSEEN`) aus `IMAP_INBOX_FOLDER`.
- Bewertet/klassifiziert **nicht** und erstellt **keine** Antwort automatisch.
- Gibt Antwortdaten inkl. `message_id` zurück, damit Paperclip AI gezielt Verlaufsmails laden kann.
- Alternativ Filter über `from_email` für alle passenden E-Mails.
- Markiert nichts als gelöscht.

## Paperclip Agent Abstraktion
- Wenn `PAPERCLIP_BASE_URL` gesetzt ist: externer Paperclip-Agent wird genutzt.
- Wenn nicht: lokaler Dummy-Responder wird genutzt.

## GHCR Nutzung
Image-Name:
`ghcr.io/<github_owner>/paperclip-mail-agent`

Pull-Beispiel:
```bash
docker pull ghcr.io/<github_owner>/paperclip-mail-agent:latest
```

Docker Compose mit fertigem GHCR-Image:
```yaml
services:
  paperclip-mail-agent:
    image: ghcr.io/<github_owner>/paperclip-mail-agent:latest
    env_file: [.env]
    ports: ["8088:8088"]
```

## GitHub Actions Release/Publish
Workflow: `.github/workflows/docker-publish.yml`
- läuft auf Push nach `main`
- läuft auf Tags `v*.*.*`
- baut/pusht nach GHCR
- Tags: `latest` (main), `sha`, `semver`

## DSGVO / Cold Email / Human-in-the-loop
- Dieser Service ist ein technisches Werkzeug für Draft-Automation.
- Prüfen Sie datenschutzrechtliche, wettbewerbsrechtliche und Branchenvorgaben vor produktivem Einsatz.
- Versandfreigabe sollte immer durch Menschen erfolgen (Human-in-the-loop).
- **Keine Rechtsberatung.**
