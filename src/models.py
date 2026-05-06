from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MovieItem:
    title: str
    origin: str
    release_date: str | None = None
    overview: str | None = None
    poster_url: str | None = None
    vote_average: float | None = None
    vote_count: int | None = None
    popularity: float | None = None
    tmdb_id: int | None = None
    media_type: str = "movie"
    platform_names: list[str] = field(default_factory=list)
    provider: str | None = None
    unique_key: str | None = None

    @property
    def tmdb_url(self) -> str | None:
        if self.tmdb_id is None:
            return None
        path = "tv" if self.media_type in {"tv", "series"} else "movie"
        return f"https://www.themoviedb.org/{path}/{self.tmdb_id}"
