from __future__ import annotations

from collections import defaultdict
from datetime import date

from .models import MovieItem


TELEGRAM_TEXT_LIMIT = 4096
CAPTION_LIMIT = 1024


def format_movie_item(movie: MovieItem, max_length: int = TELEGRAM_TEXT_LIMIT) -> str:
    icon = "📺" if movie.media_type in {"tv", "series"} else "🎬"
    lines = [
        f"{icon} {movie.title}",
        f"📍 Estreno en: {_format_origin(movie)}",
    ]

    if movie.media_type in {"tv", "series"}:
        lines.append("📺 Tipo: Serie")

    display_date = _format_date(movie.release_date)
    if display_date:
        lines.append(f"📅 Fecha: {display_date}")

    if movie.vote_average is not None:
        lines.append(f"⭐ Nota: {movie.vote_average:.1f}/10")

    overview = _truncate(movie.overview or "Sinopsis no disponible.", 420)
    lines.append(f"📝 {overview}")

    if movie.tmdb_url:
        lines.append(f"🔗 TMDb: {movie.tmdb_url}")

    text = "\n".join(lines)
    if len(text) > max_length:
        text = _truncate(text, max_length - 1)
    return text


def build_digest(
    cinema_items: list[MovieItem],
    streaming_items: list[MovieItem],
    max_items_per_message: int,
) -> list[str]:
    messages: list[str] = []
    if cinema_items:
        messages.extend(
            _chunk_section("🎟 Estrenos en cines", cinema_items, max_items_per_message)
        )

    if streaming_items:
        by_platform: dict[str, list[MovieItem]] = defaultdict(list)
        for item in streaming_items:
            platforms = item.platform_names or [item.origin]
            for platform in platforms:
                by_platform[platform].append(item)

        ordered_items: list[MovieItem] = []
        for platform in sorted(by_platform):
            ordered_items.append(MovieItem(title=f"__SECTION__{platform}", origin=platform))
            ordered_items.extend(by_platform[platform])

        messages.extend(
            _chunk_section("🍿 Estrenos en plataformas", ordered_items, max_items_per_message)
        )

    return messages


def build_empty_digest(errors: list[str] | None = None) -> str:
    today = date.today().strftime("%d/%m/%Y")
    text = f"🎬 CineRadarBot\nNo hay estrenos nuevos para avisar hoy ({today})."
    if errors:
        text += "\n\nAvisos:\n" + "\n".join(f"- {error}" for error in errors)
    return text


def _chunk_section(
    title: str, items: list[MovieItem], max_items_per_message: int
) -> list[str]:
    chunks: list[str] = []
    current_parts = [title]
    item_count = 0

    for item in items:
        if item.title.startswith("__SECTION__"):
            rendered = f"\n{item.title.removeprefix('__SECTION__')}"
        else:
            rendered = "\n" + format_movie_item(item)
            item_count += 1

        candidate = "\n\n".join(current_parts + [rendered])
        if len(candidate) > TELEGRAM_TEXT_LIMIT or item_count > max_items_per_message:
            chunks.append("\n\n".join(current_parts))
            current_parts = [title, rendered]
            item_count = 1 if not item.title.startswith("__SECTION__") else 0
        else:
            current_parts.append(rendered)

    if current_parts:
        chunks.append("\n\n".join(current_parts))
    return chunks


def _format_origin(movie: MovieItem) -> str:
    if movie.platform_names:
        return ", ".join(dict.fromkeys(movie.platform_names))
    return movie.origin


def _format_date(raw_date: str | None) -> str | None:
    if not raw_date:
        return None
    if len(raw_date) == 4 and raw_date.isdigit():
        return raw_date
    try:
        parsed = date.fromisoformat(raw_date[:10])
    except ValueError:
        return raw_date
    return parsed.strftime("%d/%m/%Y")


def _truncate(text: str, max_length: int) -> str:
    clean = " ".join(text.split())
    if len(clean) <= max_length:
        return clean
    return clean[: max_length - 1].rstrip() + "…"
