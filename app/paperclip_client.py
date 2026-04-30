from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import Settings


@dataclass
class AgentResponse:
    body_text: str
    body_html: str | None = None


class DummyResponder:
    def generate_reply(self, incoming_text: str) -> AgentResponse:
        return AgentResponse(
            body_text=f'Danke für die Nachricht. Zusammenfassung: {incoming_text[:160]}',
            body_html=None,
        )


class PaperclipAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate_reply(self, incoming_text: str) -> AgentResponse:
        headers = {'Authorization': f'Bearer {self.settings.PAPERCLIP_API_KEY}'} if self.settings.PAPERCLIP_API_KEY else {}
        timeout = httpx.Timeout(15.0, connect=5.0)
        with httpx.Client(timeout=timeout, headers=headers) as client:
            resp = client.post(
                f'{self.settings.PAPERCLIP_BASE_URL}/generate',
                json={'text': incoming_text},
            )
            resp.raise_for_status()
            data = resp.json()
            return AgentResponse(body_text=data.get('body_text', ''), body_html=data.get('body_html'))


def build_agent(settings: Settings):
    if settings.PAPERCLIP_BASE_URL:
        return PaperclipAgent(settings)
    return DummyResponder()
