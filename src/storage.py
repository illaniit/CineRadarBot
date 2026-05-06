from __future__ import annotations

import json
import logging
from pathlib import Path


LOGGER = logging.getLogger(__name__)


class SentItemsStorage:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.sent_keys: set[str] = set()

    def load(self) -> None:
        if not self.path.exists():
            self.sent_keys = set()
            return

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("No se pudo leer %s; se empieza sin historico: %s", self.path, exc)
            self.sent_keys = set()
            return

        if isinstance(data, list):
            self.sent_keys = {str(item) for item in data}
            return
        if isinstance(data, dict):
            raw_keys = data.get("sent_keys", [])
            self.sent_keys = {str(item) for item in raw_keys if item}
            return

        self.sent_keys = set()

    def has_seen(self, key: str | None) -> bool:
        return bool(key and key in self.sent_keys)

    def mark_seen(self, keys: list[str]) -> None:
        self.sent_keys.update(key for key in keys if key)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"sent_keys": sorted(self.sent_keys)}
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
