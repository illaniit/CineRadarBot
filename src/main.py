from __future__ import annotations

import logging
import sys

import requests

from .config import AppConfig, load_config
from .formatter import CAPTION_LIMIT, build_empty_digest, format_movie_item
from .models import MovieItem
from .storage import SentItemsStorage
from .streaming_client import StreamingClient
from .telegram_client import TelegramClient
from .tmdb_client import TMDbClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
LOGGER = logging.getLogger(__name__)


def main() -> int:
    try:
        config = load_config()
    except ValueError as exc:
        LOGGER.error("Configuracion invalida: %s", exc)
        return 2

    storage = SentItemsStorage(config.storage_path)
    storage.load()

    cinema_items, streaming_items, errors = collect_items(config)
    cinema_items = _filter_new(cinema_items, storage)
    streaming_items = _filter_new(streaming_items, storage)

    telegram = TelegramClient(config.telegram_bot_token, config.telegram_chat_id)
    sent_keys: list[str] = []

    if cinema_items or streaming_items:
        sent_keys.extend(_send_grouped_items(telegram, cinema_items, streaming_items))
    else:
        message = build_empty_digest(errors)
        telegram.send_message(message)

    if errors and (cinema_items or streaming_items):
        telegram.send_message("⚠️ CineRadarBot tuvo avisos:\n" + "\n".join(f"- {e}" for e in errors))

    if sent_keys:
        storage.mark_seen(sent_keys)
        storage.save()
        LOGGER.info("Guardados %s nuevos avisos enviados", len(sent_keys))
    else:
        storage.save()
        LOGGER.info("No habia nuevos avisos para guardar")

    return 0


def collect_items(config: AppConfig) -> tuple[list[MovieItem], list[MovieItem], list[str]]:
    errors: list[str] = []
    cinema_items: list[MovieItem] = []
    streaming_items: list[MovieItem] = []

    tmdb = TMDbClient(config.tmdb_api_token, config.tmdb_api_key)
    try:
        cinema_items = tmdb.get_cinema_releases(
            country=config.country,
            language=config.language,
            days_ahead=config.days_ahead,
            min_vote_count=config.min_tmdb_vote_count,
        )
        LOGGER.info("TMDb devolvio %s estrenos de cine", len(cinema_items))
    except requests.RequestException as exc:
        LOGGER.error("Fallo consultando TMDb: %s", _http_error_summary(exc))
        errors.append("No se pudieron consultar estrenos de cine en TMDb.")

    streaming = StreamingClient(
        api_key=config.streaming_api_key,
        provider=config.streaming_api_provider,
        catalogs=config.streaming_catalogs,
        watchmode_source_ids=config.watchmode_source_ids,
        max_pages=config.max_streaming_pages,
    )
    try:
        streaming_items = streaming.get_streaming_releases(
            country=config.country,
            language=config.language,
            days_ahead=config.days_ahead,
        )
        LOGGER.info("Streaming devolvio %s novedades", len(streaming_items))
    except requests.RequestException as exc:
        LOGGER.error("Fallo consultando API de streaming: %s", _http_error_summary(exc))
        errors.append("No se pudieron consultar plataformas de streaming.")

    return cinema_items, streaming_items, errors


def _filter_new(items: list[MovieItem], storage: SentItemsStorage) -> list[MovieItem]:
    return [item for item in items if not storage.has_seen(item.unique_key)]


def _send_grouped_items(
    telegram: TelegramClient,
    cinema_items: list[MovieItem],
    streaming_items: list[MovieItem],
) -> list[str]:
    sent_keys: list[str] = []
    if cinema_items:
        telegram.send_message("🎟 Estrenos en cines")
        sent_keys.extend(_send_individual_items(telegram, cinema_items))

    if streaming_items:
        telegram.send_message("🍿 Estrenos en plataformas")
        by_platform: dict[str, list[MovieItem]] = {}
        for item in streaming_items:
            platform = (item.platform_names or [item.origin])[0]
            by_platform.setdefault(platform, []).append(item)

        for platform in sorted(by_platform):
            telegram.send_message(platform)
            sent_keys.extend(_send_individual_items(telegram, by_platform[platform]))

    return sent_keys


def _send_individual_items(telegram: TelegramClient, items: list[MovieItem]) -> list[str]:
    sent_keys: list[str] = []
    for item in items:
        text = format_movie_item(item, max_length=CAPTION_LIMIT if item.poster_url else 4096)
        if item.poster_url:
            ok = telegram.send_photo(item.poster_url, text)
            if not ok:
                ok = telegram.send_message(format_movie_item(item))
        else:
            ok = telegram.send_message(text)

        if ok and item.unique_key:
            sent_keys.append(item.unique_key)

    return sent_keys


def _http_error_summary(exc: requests.RequestException) -> str:
    response = getattr(exc, "response", None)
    if response is not None:
        return f"HTTP {response.status_code}"
    return exc.__class__.__name__


if __name__ == "__main__":
    sys.exit(main())
