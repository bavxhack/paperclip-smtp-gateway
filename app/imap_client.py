from __future__ import annotations

import imaplib
import logging
import socket
from contextlib import contextmanager

from app.config import Settings

logger = logging.getLogger(__name__)


class ImapClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @contextmanager
    def connect(self):
        client: imaplib.IMAP4 | imaplib.IMAP4_SSL
        timeout = 15
        socket.setdefaulttimeout(timeout)
        if self.settings.IMAP_USE_SSL:
            client = imaplib.IMAP4_SSL(self.settings.IMAP_HOST, self.settings.IMAP_PORT)
        else:
            client = imaplib.IMAP4(self.settings.IMAP_HOST, self.settings.IMAP_PORT)

        try:
            client.login(self.settings.IMAP_USER, self.settings.IMAP_PASSWORD)
            yield client
        finally:
            try:
                client.logout()
            except Exception:
                logger.debug('IMAP logout failed (ignored).')

    def list_folders(self) -> list[str]:
        with self.connect() as client:
            status, folders = client.list()
            if status != 'OK':
                raise RuntimeError('Could not list IMAP folders')

            names = []
            for raw in folders or []:
                line = raw.decode(errors='ignore')
                if '"' in line:
                    names.append(line.split('"')[-2])
                else:
                    names.append(line)
            return names
