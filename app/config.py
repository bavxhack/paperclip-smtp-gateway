from functools import lru_cache

from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', case_sensitive=True)

    APP_PORT: int = Field(default=8088, ge=1, le=65535)
    LOG_LEVEL: str = Field(default='INFO')

    IMAP_HOST: str = Field(default='imap.kasserver.com')
    IMAP_PORT: int = Field(default=993, ge=1, le=65535)
    IMAP_USER: str = ''
    IMAP_PASSWORD: str = ''
    IMAP_INBOX_FOLDER: str = 'INBOX'
    IMAP_DRAFTS_FOLDER: str = 'Drafts'
    IMAP_USE_SSL: bool = True

    SMTP_HOST: str = Field(default='smtp.kasserver.com')
    SMTP_PORT: int = Field(default=465, ge=1, le=65535)

    FROM_EMAIL: str = ''
    FROM_NAME: str = ''

    PAPERCLIP_BASE_URL: HttpUrl | None = None
    PAPERCLIP_API_KEY: str = ''

    POLL_LIMIT: int = Field(default=10, ge=1, le=100)
    DRY_RUN: bool = False


class AppMetadata(BaseModel):
    name: str = 'paperclip-mail-agent'
    version: str = '0.1.0'


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
