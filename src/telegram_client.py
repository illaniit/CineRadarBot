from __future__ import annotations

import logging

import requests


LOGGER = logging.getLogger(__name__)


class TelegramClient:
    def __init__(self, bot_token: str, chat_id: str, timeout: int = 20) -> None:
        self.chat_id = chat_id
        self.timeout = timeout
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, text: str) -> bool:
        return self._post(
            "sendMessage",
            {
                "chat_id": self.chat_id,
                "text": text,
                "disable_web_page_preview": False,
            },
        )

    def send_photo(self, photo_url: str, caption: str) -> bool:
        return self._post(
            "sendPhoto",
            {
                "chat_id": self.chat_id,
                "photo": photo_url,
                "caption": caption,
            },
        )

    def _post(self, method: str, payload: dict[str, object]) -> bool:
        url = f"{self.base_url}/{method}"
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            LOGGER.error(
                "Error HTTP enviando %s a Telegram: %s",
                method,
                exc.__class__.__name__,
            )
            return False
        except ValueError:
            LOGGER.error("Telegram devolvio una respuesta no JSON en %s", method)
            return False

        if not data.get("ok"):
            description = data.get("description", "sin descripcion")
            LOGGER.error("Telegram rechazo %s: %s", method, description)
            return False

        return True
