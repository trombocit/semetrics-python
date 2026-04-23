import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .models import Event
from .queue import EventQueue
from .transport import HttpTransport
from .worker import BackgroundWorker

logger = logging.getLogger(__name__)

SDK_VERSION = "0.1.0"


class Semetrics:
    """
    Клиент Semetrics для Python.

    Пример использования:
        semetrics = Semetrics(api_key="sm_live_...", endpoint="https://semetrics.ru/events")
        semetrics.track("user_signed_up", user_id="u123", properties={"plan": "pro"})
        semetrics.shutdown()  # при завершении программы
    """

    def __init__(
        self,
        api_key: str,
        endpoint: str = "https://semetrics.ru/events",
        flush_interval: int = 5,
        batch_size: int = 50,
        max_queue_size: int = 10_000,
        max_retries: int = 3,
        request_timeout: int = 10,
        persistence_path: Optional[str] = None,
    ):
        self._queue = EventQueue(max_size=max_queue_size, persistence_path=persistence_path)
        self._transport = HttpTransport(api_key=api_key, endpoint=endpoint, timeout=request_timeout)
        self._worker = BackgroundWorker(
            queue=self._queue,
            transport=self._transport,
            flush_interval=flush_interval,
            batch_size=batch_size,
            max_retries=max_retries,
        )
        self._worker.start()

    def track(
        self,
        event_name: str,
        user_id: Optional[str] = None,
        anonymous_id: Optional[str] = None,
        session_id: Optional[str] = None,
        properties: Optional[dict[str, Any]] = None,
        client_ts: Optional[datetime] = None,
    ) -> None:
        """
        Добавить событие в очередь.
        Не блокирует вызывающий код — отправка происходит в фоне.
        """
        event = Event(
            event_name=event_name,
            user_id=user_id,
            anonymous_id=anonymous_id,
            session_id=session_id,
            platform="python",
            sdk_version=SDK_VERSION,
            properties=properties,
            client_ts=client_ts or datetime.now(timezone.utc),
        )
        self._queue.enqueue(event)

    def flush(self) -> None:
        """Синхронно отправить все накопленные события прямо сейчас."""
        self._worker.flush_sync()

    def shutdown(self) -> None:
        """Остановить фоновый worker и отправить всё накопленное перед выходом."""
        self._worker.stop()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.shutdown()
