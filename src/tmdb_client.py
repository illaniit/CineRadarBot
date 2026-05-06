from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import requests

from .models import MovieItem


LOGGER = logging.getLogger(__name__)
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"


class TMDbClient:
    def __init__(
        self,
        api_token: str | None = None,
        api_key: str | None = None,
        timeout: int = 20,
    ) -> None:
        self.api_token = api_token
        self.api_key = api_key
        self.timeout = timeout

    def get_cinema_releases(
        self,
        country: str,
        language: str,
        days_ahead: int,
        min_vote_count: int = 0,
    ) -> list[MovieItem]:
        today = date.today()
        end_date = today + timedelta(days=days_ahead)
        results: dict[tuple[int, str], MovieItem] = {}

        for endpoint in ("now_playing", "upcoming"):
            for page in range(1, 6):
                payload = self._get(
                    f"/movie/{endpoint}",
                    {
                        "region": country,
                        "language": language,
                        "page": page,
                    },
                )
                movies = payload.get("results", [])
                if not isinstance(movies, list):
                    break

                for raw_movie in movies:
                    item = self._normalise_movie(raw_movie, today, end_date)
                    if item is None:
                        continue
                    if (item.vote_count or 0) < min_vote_count:
                        continue
                    results[(item.tmdb_id or 0, item.release_date or "")] = item

                total_pages = min(int(payload.get("total_pages", 1) or 1), 5)
                if page >= total_pages:
                    break

        return sorted(
            results.values(),
            key=lambda movie: (movie.release_date or "9999-99-99", movie.title),
        )

    def _get(self, path: str, params: dict[str, object]) -> dict[str, Any]:
        query = dict(params)
        headers: dict[str, str] = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        elif self.api_key:
            query["api_key"] = self.api_key

        response = requests.get(
            f"{TMDB_BASE_URL}{path}", params=query, headers=headers, timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _normalise_movie(
        raw_movie: dict[str, Any], start_date: date, end_date: date
    ) -> MovieItem | None:
        release_date = raw_movie.get("release_date")
        tmdb_id = raw_movie.get("id")
        if not release_date or not tmdb_id:
            return None

        try:
            release = date.fromisoformat(release_date)
        except ValueError:
            LOGGER.debug("Fecha TMDb invalida para %s: %s", tmdb_id, release_date)
            return None

        if not (start_date <= release <= end_date):
            return None

        poster_path = raw_movie.get("poster_path")
        poster_url = f"{TMDB_POSTER_BASE_URL}{poster_path}" if poster_path else None

        return MovieItem(
            title=raw_movie.get("title") or raw_movie.get("original_title") or "Sin titulo",
            origin="Cine",
            release_date=release_date,
            overview=raw_movie.get("overview") or None,
            poster_url=poster_url,
            vote_average=raw_movie.get("vote_average"),
            vote_count=raw_movie.get("vote_count"),
            tmdb_id=int(tmdb_id),
            platform_names=["Cine"],
            unique_key=f"cinema:{tmdb_id}:{release_date}",
        )
