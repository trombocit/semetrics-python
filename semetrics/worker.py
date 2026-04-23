import logging
import threading
import time

from .queue import EventQueue
from .transport import HttpTransport

logger = logging.getLogger(__name__)


class BackgroundWorker(threading.Thread):
    """
    Daemon thread, который периодически отправляет события из очереди.
    Запускается при создании клиента, останавливается при shutdown().
    """

    def __init__(
        self,
        queue: EventQueue,
        transport: HttpTransport,
        flush_interval: int = 5,
        batch_size: int = 50,
        max_retries: int = 3,
    ):
        super().__init__(daemon=True, name="semetrics-worker")
        self._queue = queue
        self._transport = transport
        self._flush_interval = flush_interval
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._flush_interval)
            self._flush()

    def flush_sync(self) -> None:
        """Отправить всё что есть прямо сейчас (вызывается из основного потока)."""
        while len(self._queue) > 0:
            self._flush()

    def stop(self) -> None:
        """Остановить worker и отправить оставшиеся события."""
        self._stop_event.set()
        self.flush_sync()

    def _flush(self) -> None:
        batch = self._queue.dequeue_batch(self._batch_size)
        if not batch:
            return

        for attempt in range(self._max_retries):
            try:
                self._transport.send_batch(batch)
                self._queue.delete_from_db(batch)
                logger.debug(f"Отправлено {len(batch)} событий.")
                return
            except Exception as exc:
                wait = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(
                    f"Ошибка отправки (попытка {attempt + 1}/{self._max_retries}): {exc}. "
                    f"Повтор через {wait}с."
                )
                if attempt < self._max_retries - 1:
                    time.sleep(wait)

        # После всех попыток — логируем потерю батча
        logger.error(f"Батч из {len(batch)} событий потерян после {self._max_retries} попыток.")
