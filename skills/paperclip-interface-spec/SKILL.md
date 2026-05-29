---
name: paperclip-interface-spec
description: Create, validate, and document exact interface specifications for the paperclip-smtp-gateway repository (FastAPI endpoints, request/response models, and Paperclip integration points). Use this skill for API documentation, contract tests, client implementations, or importing a repo-based skill into Paperclip.
---

# Goal
Produce a precise, reusable interface specification for `paperclip-smtp-gateway` and keep it consistent with the code.

## Workflow
1. Read `references/interfaces.md` first.
2. Extract relevant interfaces (HTTP, data models, agent integration).
3. Always output specs in a stable format:
   - Endpoint + method
   - Request fields including types and constraints
   - Response fields including types
   - Error cases/validation
4. If anything is unclear, inspect implementation in `app/main.py`, `app/models.py`, `app/config.py`, `app/reply_reader.py`, `app/paperclip_client.py`.
5. Do not make silent assumptions; mark unknown fields explicitly as “not specified”.
6. For `/drafts/create` and `/send`, always document draft body newline compatibility:
   - `body_text` and optional `body_html` accept both real newline characters and literal escaped newline markers (`\\n`, `\\r\\n`, `\\r`).
   - The gateway normalizes literal escaped markers to real line breaks before writing IMAP drafts, so clients may send either representation.
   - `/send` is a send-like agent endpoint, but it intentionally uses the same draft writer and stores messages in `IMAP_DRAFTS_FOLDER` instead of sending via SMTP.
7. For `/replies/poll`, always document the polling window and response arrays:
   - `limit` is optional (`1..1000`) and defaults to server `POLL_LIMIT` when omitted.
   - Server `POLL_LIMIT` defaults to `100` and is configurable up to `1000`.
   - Results are evaluated newest-first from `IMAP_INBOX_FOLDER`.
   - `items` = newest matched replies, capped by the effective limit after filters are applied.
   - `unseen_items` = unread subset of returned `items` for incremental processing/parsing.

## Recommended output format
- Section `API`
- Section `Models`
- Section `Paperclip integration contract`
- Section `Open questions`

## Import from repository
If a user wants to import this skill directly from a Git repository:
1. Use the `skills/paperclip-interface-spec` folder as the import path.
2. Ensure at least `SKILL.md` is present.
3. Optionally use `agents/openai.yaml` for UI metadata.
