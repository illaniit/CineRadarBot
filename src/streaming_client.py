from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import requests

from .models import MovieItem


LOGGER = logging.getLogger(__name__)


STREAMING_AVAILABILITY_BASE_URL = "https://api.movieofthenight.com/v4"
STREAMING_AVAILABILITY_RAPIDAPI_BASE_URL = (
    "https://streaming-availability.p.rapidapi.com"
)
WATCHMODE_BASE_URL = "https://api.watchmode.com/v1"


PLATFORM_DISPLAY_NAMES = {
    "netflix": "Netflix",
    "prime": "Prime Video",
    "amazon": "Prime Video",
    "disney": "Disney+",
    "disneyplus": "Disney+",
    "max": "Max",
    "hbo": "Max",
    "hbomax": "Max",
    "movistar": "Movistar Plus+",
    "movistarplus": "Movistar Plus+",
    "filmin": "Filmin",
    "apple": "Apple TV+",
    "appletv": "Apple TV+",
    "apple tv+": "Apple TV+",
    "skyshowtime": "SkyShowtime",
}


class StreamingClient:
    def __init__(
        self,
        api_key: str | None,
        provider: str,
        catalogs: list[str],
        watchmode_source_ids: list[str],
        timeout: int = 25,
        max_pages: int = 3,
    ) -> None:
        self.api_key = api_key
        self.provider = provider
        self.catalogs = catalogs
        self.watchmode_source_ids = watchmode_source_ids
        self.timeout = timeout
        self.max_pages = max_pages

    def get_streaming_releases(
        self, country: str, language: str, days_ahead: int
    ) -> list[MovieItem]:
        if not self.api_key:
            LOGGER.info("STREAMING_API_KEY no configurada; se omiten plataformas")
            return []

        if self.provider in {"streamingavailability", "movieofthenight"}:
            return self._get_streaming_availability_releases(
                country=country, language=language, days_ahead=days_ahead
            )
        if self.provider == "watchmode":
            return self._get_watchmode_releases(country=country, days_ahead=days_ahead)

        LOGGER.warning("Proveedor streaming no soportado: %s", self.provider)
        return []

    def _get_streaming_availability_releases(
        self, country: str, language: str, days_ahead: int
    ) -> list[MovieItem]:
        country_code = country.lower()
        output_language = language.split("-")[0].lower()
        items: dict[str, MovieItem] = {}
        catalogs = self.catalogs or []
        from_date = date.today() - timedelta(days=days_ahead)
        to_date = date.today() + timedelta(days=1)
        from_timestamp = int(
            datetime.combine(from_date, time.min, tzinfo=timezone.utc).timestamp()
        )
        to_timestamp = int(
            datetime.combine(to_date, time.min, tzinfo=timezone.utc).timestamp()
        )

        for catalog in catalogs:
            cursor: str | None = None
            for _ in range(self.max_pages):
                params = {
                    "country": country_code,
                    "change_type": "new",
                    "item_type": "show",
                    "catalogs": catalog,
                    "show_type": "movie",
                    "output_language": output_language,
                    "from": from_timestamp,
                    "to": to_timestamp,
                    "order_direction": "desc",
                }
                if cursor:
                    params["cursor"] = cursor

                payload = self._streaming_availability_get("/changes", params)
                changes = payload.get("changes") or payload.get("items") or []
                if isinstance(changes, dict):
                    changes = changes.get("changes") or changes.get("items") or []
                if not isinstance(changes, list):
                    break
                shows = payload.get("shows") or {}
                if not isinstance(shows, dict):
                    shows = {}

                for change in changes:
                    if not isinstance(change, dict):
                        continue
                    show_id = str(change.get("showId") or change.get("show_id") or "")
                    show = shows.get(show_id) if show_id else None
                    item = self._normalise_streaming_availability_change(
                        change, show=show, fallback_catalog=catalog
                    )
                    if item:
                        items[item.unique_key or f"{item.provider}:{item.title}"] = item

                if not payload.get("hasMore"):
                    break
                cursor = payload.get("nextCursor")
                if not cursor:
                    break

        return sorted(
            items.values(),
            key=lambda movie: (movie.release_date or "9999-99-99", movie.title),
        )

    def _streaming_availability_get(
        self, path: str, params: dict[str, object]
    ) -> dict[str, Any]:
        rapidapi_host = "streaming-availability.p.rapidapi.com"
        use_rapidapi = self.api_key and self.api_key.startswith("rapidapi:")
        api_key = self.api_key.removeprefix("rapidapi:") if self.api_key else ""
        base_url = (
            STREAMING_AVAILABILITY_RAPIDAPI_BASE_URL
            if use_rapidapi
            else STREAMING_AVAILABILITY_BASE_URL
        )
        headers = (
            {"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": rapidapi_host}
            if use_rapidapi
            else {"X-API-Key": api_key}
        )

        response = requests.get(
            f"{base_url}{path}", params=params, headers=headers, timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def _normalise_streaming_availability_change(
        self,
        change: dict[str, Any],
        show: dict[str, Any] | None,
        fallback_catalog: str,
    ) -> MovieItem | None:
        show = show or change.get("show") or change.get("item") or change
        if not isinstance(show, dict):
            return None

        show_type = (
            change.get("showType")
            or change.get("show_type")
            or show.get("showType")
            or show.get("show_type")
        )
        if show_type and show_type != "movie":
            return None

        tmdb_id = _parse_tmdb_id(show.get("tmdbId") or show.get("tmdb_id"))
        title = show.get("title") or show.get("originalTitle") or show.get("original_title")
        if not title:
            return None

        timestamp = change.get("timestamp")
        if isinstance(timestamp, (int, float)):
            change_date = datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()
        else:
            changed_at = (
                change.get("updatedAt")
                or change.get("createdAt")
                or change.get("changeDate")
                or change.get("date")
                or date.today().isoformat()
            )
            change_date = str(changed_at)[:10]

        platforms = self._extract_streaming_availability_platforms(
            show, change, fallback_catalog
        )
        platform_label = ", ".join(platforms) if platforms else _display_platform(fallback_catalog)

        poster_url = _extract_streaming_availability_poster(show)
        rating = show.get("rating")
        vote_average = float(rating) / 10 if isinstance(rating, (int, float)) else None

        unique_id = tmdb_id or show.get("id") or title.lower()
        provider_key = _slug(platform_label)

        return MovieItem(
            title=title,
            origin=platform_label,
            release_date=change_date,
            overview=show.get("overview") or None,
            poster_url=poster_url,
            vote_average=vote_average,
            vote_count=None,
            tmdb_id=tmdb_id,
            platform_names=platforms or [platform_label],
            provider=self.provider,
            unique_key=f"streaming:{provider_key}:{unique_id}:{change_date}",
        )

    @staticmethod
    def _extract_streaming_availability_platforms(
        show: dict[str, Any], change: dict[str, Any], fallback_catalog: str
    ) -> list[str]:
        options = show.get("streamingOptions") or show.get("streaming_options") or {}
        platforms: set[str] = set()

        service = change.get("service")
        if isinstance(service, dict):
            service_name = service.get("name") or service.get("id")
            if service_name:
                platforms.add(_display_platform(str(service_name)))

        if isinstance(options, dict):
            for country_options in options.values():
                if not isinstance(country_options, list):
                    continue
                for option in country_options:
                    if not isinstance(option, dict):
                        continue
                    service = option.get("service") or {}
                    service_id = (
                        service.get("id")
                        if isinstance(service, dict)
                        else option.get("serviceId") or option.get("service_id")
                    )
                    if service_id:
                        platforms.add(_display_platform(str(service_id)))

        if not platforms:
            platforms.add(_display_platform(fallback_catalog))

        return sorted(platforms)

    def _get_watchmode_releases(self, country: str, days_ahead: int) -> list[MovieItem]:
        today = date.today()
        end_date = today + timedelta(days=days_ahead)
        params: dict[str, object] = {
            "types": "movie",
            "regions": country.upper(),
            "source_types": "sub",
            "sort_by": "release_date_desc",
            "release_date_start": today.strftime("%Y%m%d"),
            "release_date_end": end_date.strftime("%Y%m%d"),
            "limit": 50,
            "page": 1,
        }
        if self.watchmode_source_ids:
            params["source_ids"] = ",".join(self.watchmode_source_ids)

        payload = self._watchmode_get("/list-titles/", params)
        raw_titles = payload.get("titles") or payload.get("results") or []
        if not isinstance(raw_titles, list):
            return []

        items: list[MovieItem] = []
        for raw_title in raw_titles:
            if not isinstance(raw_title, dict):
                continue
            item = self._normalise_watchmode_title(raw_title, country)
            if item:
                items.append(item)

        return sorted(
            items,
            key=lambda movie: (movie.release_date or "9999-99-99", movie.title),
        )

    def _watchmode_get(self, path: str, params: dict[str, object]) -> dict[str, Any]:
        query = dict(params)
        query["apiKey"] = self.api_key
        response = requests.get(
            f"{WATCHMODE_BASE_URL}{path}",
            params=query,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def _normalise_watchmode_title(
        self, raw_title: dict[str, Any], country: str
    ) -> MovieItem | None:
        title = raw_title.get("title") or raw_title.get("name")
        watchmode_id = raw_title.get("id")
        if not title or not watchmode_id:
            return None

        sources = self._get_watchmode_sources(int(watchmode_id), country)
        platforms = sorted(
            {
                _display_platform(source.get("name") or source.get("source_name") or "")
                for source in sources
                if isinstance(source, dict)
                and (source.get("type") in {None, "sub"} or source.get("format") == "HD")
            }
        )
        if not platforms:
            platforms = ["Streaming"]

        release_date = str(raw_title.get("year") or date.today().year)
        if raw_title.get("release_date"):
            release_date = str(raw_title["release_date"])[:10]

        tmdb_id = _parse_tmdb_id(raw_title.get("tmdb_id") or raw_title.get("tmdbId"))
        provider_key = _slug(",".join(platforms))

        return MovieItem(
            title=title,
            origin=", ".join(platforms),
            release_date=release_date,
            overview=raw_title.get("plot_overview") or None,
            poster_url=raw_title.get("poster") or raw_title.get("poster_url") or None,
            vote_average=None,
            vote_count=None,
            tmdb_id=tmdb_id,
            platform_names=platforms,
            provider=self.provider,
            unique_key=f"streaming:{provider_key}:{tmdb_id or watchmode_id}:{release_date}",
        )

    def _get_watchmode_sources(self, watchmode_id: int, country: str) -> list[dict[str, Any]]:
        try:
            payload = self._watchmode_get(
                f"/title/{watchmode_id}/sources/",
                {"regions": country.upper()},
            )
        except requests.RequestException as exc:
            LOGGER.warning(
                "No se pudieron consultar sources Watchmode para %s: %s",
                watchmode_id,
                _http_error_summary(exc),
            )
            return []

        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            sources = payload.get("sources") or payload.get("results") or []
            if isinstance(sources, list):
                return [item for item in sources if isinstance(item, dict)]
        return []


def _parse_tmdb_id(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raw = str(value)
    if raw.startswith("movie/"):
        raw = raw.split("/", 1)[1]
    try:
        return int(raw)
    except ValueError:
        return None


def _extract_streaming_availability_poster(show: dict[str, Any]) -> str | None:
    image_set = show.get("imageSet") or show.get("image_set") or {}
    if not isinstance(image_set, dict):
        return None

    vertical = image_set.get("verticalPoster") or image_set.get("poster")
    if isinstance(vertical, dict):
        for key in ("w600", "w500", "w342", "original"):
            if vertical.get(key):
                return str(vertical[key])
    if isinstance(vertical, str):
        return vertical
    return None


def _display_platform(raw_name: str) -> str:
    normalised = _slug(raw_name)
    return PLATFORM_DISPLAY_NAMES.get(normalised, raw_name.strip() or "Streaming")


def _slug(value: str) -> str:
    return (
        value.lower()
        .replace("+", "plus")
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
        .replace(".", "")
    )


def _http_error_summary(exc: requests.RequestException) -> str:
    response = getattr(exc, "response", None)
    if response is not None:
        return f"HTTP {response.status_code}"
    return exc.__class__.__name__
