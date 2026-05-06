from __future__ import annotations

import os
from dataclasses import dataclass


try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is optional at import time
    load_dotenv = None


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} debe ser un entero") from exc


def _get_list(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "si", "sí", "on"}


@dataclass(frozen=True, slots=True)
class AppConfig:
    telegram_bot_token: str
    telegram_chat_id: str
    tmdb_api_token: str | None
    tmdb_api_key: str | None
    streaming_api_key: str | None
    streaming_api_provider: str
    country: str
    language: str
    days_ahead: int
    cinema_release_offset_days: int
    min_tmdb_vote_count: int
    max_items_per_message: int
    max_streaming_pages: int
    storage_path: str
    streaming_catalogs: list[str]
    watchmode_source_ids: list[str]
    include_series: bool
    send_streaming_status: bool

    @property
    def tmdb_auth_available(self) -> bool:
        return bool(self.tmdb_api_token or self.tmdb_api_key)


def load_config() -> AppConfig:
    if load_dotenv:
        load_dotenv()

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    tmdb_api_token = os.getenv("TMDB_API_TOKEN", "").strip() or None
    tmdb_api_key = os.getenv("TMDB_API_KEY", "").strip() or None

    if not telegram_bot_token:
        raise ValueError("Falta TELEGRAM_BOT_TOKEN")
    if not telegram_chat_id:
        raise ValueError("Falta TELEGRAM_CHAT_ID")
    if not (tmdb_api_token or tmdb_api_key):
        raise ValueError("Falta TMDB_API_TOKEN o TMDB_API_KEY")

    return AppConfig(
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        tmdb_api_token=tmdb_api_token,
        tmdb_api_key=tmdb_api_key,
        streaming_api_key=os.getenv("STREAMING_API_KEY", "").strip() or None,
        streaming_api_provider=os.getenv(
            "STREAMING_API_PROVIDER", "streamingavailability"
        ).strip().lower(),
        country=os.getenv("COUNTRY", "ES").strip().upper(),
        language=os.getenv("LANGUAGE", "es-ES").strip(),
        days_ahead=_get_int("DAYS_AHEAD", 7),
        cinema_release_offset_days=_get_int("CINEMA_RELEASE_OFFSET_DAYS", 1),
        min_tmdb_vote_count=_get_int("MIN_TMDB_VOTE_COUNT", 0),
        max_items_per_message=_get_int("MAX_ITEMS_PER_MESSAGE", 8),
        max_streaming_pages=_get_int("MAX_STREAMING_PAGES", 3),
        storage_path=os.getenv("STORAGE_PATH", "data/sent_items.json").strip(),
        streaming_catalogs=_get_list(
            "STREAMING_CATALOGS",
            "netflix,prime,disney,hbo,movistar,filmin,apple,skyshowtime",
        ),
        watchmode_source_ids=_get_list("WATCHMODE_SOURCE_IDS", ""),
        include_series=_get_bool("INCLUDE_SERIES", True),
        send_streaming_status=_get_bool("SEND_STREAMING_STATUS", True),
    )
