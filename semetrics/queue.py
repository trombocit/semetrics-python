import json
import logging
import sqlite3
import threading
from collections import deque
from typing import Optional

from .models import Event

logger = logging.getLogger(__name__)


class EventQueue:
    """
    Thread-safe очередь событий.
    По умолчанию — in-memory.
    При указании persistence_path — дополнительно сохраняет в SQLite
    (события переживают перезапуск процесса).
    """

    def __init__(self, max_size: int = 10_000, persistence_path: Optional[str] = None):
        self._max_size = max_size
        self._queue: deque[Event] = deque()
        self._lock = threading.Lock()
        self._db: Optional[sqlite3.Connection] = None

        if persistence_path:
            self._init_db(persistence_path)

    def _init_db(self, path: str) -> None:
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS queued_events (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                payload   TEXT NOT NULL,
                created_at REAL DEFAULT (unixepoch('now', 'subsec'))
            )
        """)
        self._db.commit()
        self._restore_from_db()

    def _restore_from_db(self) -> None:
        """Загрузить непереданные события из SQLite при старте."""
        rows = self._db.execute("SELECT id, payload FROM queued_events ORDER BY id").fetchall()
        for row_id, payload in rows:
            try:
                data = json.loads(payload)
                from datetime import datetime
                data["client_ts"] = datetime.fromisoformat(data["client_ts"])
                event = Event(**data)
                event.db_id = row_id
                self._queue.append(event)
            except Exception as exc:
                logger.warning(f"Не удалось восстановить событие {row_id}: {exc}")
        if rows:
            logger.info(f"Восстановлено {len(rows)} событий из SQLite.")

    def enqueue(self, event: Event) -> bool:
        """Добавить событие в очередь. Возвращает False если очередь переполнена."""
        with self._lock:
            if len(self._queue) >= self._max_size:
                logger.warning("Очередь переполнена, событие отброшено.")
                return False
            if self._db:
                cursor = self._db.execute(
                    "INSERT INTO queued_events (payload) VALUES (?)",
                    (json.dumps(event.to_dict()),),
                )
                self._db.commit()
                event.db_id = cursor.lastrowid
            self._queue.append(event)
            return True

    def dequeue_batch(self, size: int) -> list[Event]:
        """Извлечь до `size` событий из начала очереди."""
        with self._lock:
            batch = []
            for _ in range(min(size, len(self._queue))):
                batch.append(self._queue.popleft())
            return batch

    def requeue_batch(self, events: list[Event]) -> None:
        """Вернуть события в начало очереди (после неудачной отправки)."""
        with self._lock:
            for event in reversed(events):
                self._queue.appendleft(event)

    def delete_from_db(self, events: list[Event]) -> None:
        """Удалить отправленные события из SQLite по db_id."""
        if not self._db:
            return
        ids = [e.db_id for e in events if e.db_id is not None]
        if not ids:
            return
        with self._lock:
            self._db.execute(
                f"DELETE FROM queued_events WHERE id IN ({','.join('?' * len(ids))})",
                ids,
            )
            self._db.commit()

    def __len__(self) -> int:
        with self._lock:
            return len(self._queue)
