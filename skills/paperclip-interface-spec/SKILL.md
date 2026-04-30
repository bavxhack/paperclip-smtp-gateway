---
name: paperclip-interface-spec
description: Erstelle, prüfe und dokumentiere exakte Schnittstellenbeschreibungen für das Repository paperclip-smtp-gateway (FastAPI Endpoints, Request/Response-Modelle, Integrationspunkte zu Paperclip). Verwende dieses Skill bei Aufgaben wie API-Dokumentation, Vertragstests, Client-Implementierungen oder Import eines Repo-basierten Skills in Paperclip.
---

# Ziel
Erzeuge eine präzise, wiederverwendbare Schnittstellenbeschreibung für `paperclip-smtp-gateway` und halte sie konsistent mit dem Code.

## Vorgehen
1. Lies zuerst `references/interfaces.md`.
2. Extrahiere die relevanten Schnittstellen (HTTP, Datenmodelle, Agent-Integration).
3. Gib Spezifikationen immer in stabiler Form aus:
   - Endpoint + Methode
   - Request-Felder inkl. Typen und Constraints
   - Response-Felder inkl. Typen
   - Fehlerfälle/Validierung
4. Bei Unklarheiten: Implementierung in `app/main.py`, `app/models.py`, `app/paperclip_client.py` prüfen.
5. Keine stillen Annahmen treffen; unbekannte Felder explizit als „nicht spezifiziert“ markieren.

## Ausgabeformat (empfohlen)
- Abschnitt `API`
- Abschnitt `Modelle`
- Abschnitt `Integrationsvertrag Paperclip`
- Abschnitt `Offene Punkte`

## Import aus Repo
Wenn ein Nutzer das Skill direkt aus einem Git-Repo importieren will:
1. Verwende den Skill-Ordner `skills/paperclip-interface-spec` als Import-Pfad.
2. Stelle sicher, dass mindestens `SKILL.md` vorhanden ist.
3. Optional: `agents/openai.yaml` für UI-Metadaten verwenden.
