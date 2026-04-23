import logging

import httpx

from .models import Event

logger = logging.getLogger(__name__)


class HttpTransport:
    def __init__(self, api_key: str, endpoint: str, timeout: int = 10):
        self._api_key = api_key
        self._batch_url = endpoint.rstrip("/") + "/ingest/batch"
        self._timeout = timeout

    def send_batch(self, events: list[Event]) -> None:
        """
        Отправить батч событий на сервер.
        Поднимает исключение при ошибке (для retry-логики в worker'е).
        """
        payload = {"events": [e.to_dict() for e in events]}

        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(
                self._batch_url,
                json=payload,
                headers={"X-API-Key": self._api_key},
            )
            response.raise_for_status()

            data = response.json()
            if data.get("status", {}).get("code") not in ("", None):
                raise RuntimeError(
                    f"Сервер вернул ошибку: {data['status'].get('message')}"
                )
