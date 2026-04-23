import os
import tempfile
import threading
from datetime import datetime, timezone

import pytest

from semetrics.models import Event
from semetrics.queue import EventQueue


def make_event(name: str = "test_event") -> Event:
    return Event(
        event_name=name,
        client_ts=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


# --- In-memory ---

def test_enqueue_and_dequeue():
    q = EventQueue(max_size=10)
    q.enqueue(make_event("a"))
    q.enqueue(make_event("b"))
    batch = q.dequeue_batch(10)
    assert [e.event_name for e in batch] == ["a", "b"]


def test_dequeue_respects_size():
    q = EventQueue(max_size=10)
    for i in range(5):
        q.enqueue(make_event(f"e{i}"))
    batch = q.dequeue_batch(3)
    assert len(batch) == 3
    assert len(q) == 2


def test_overflow_drops_new_events():
    q = EventQueue(max_size=3)
    for i in range(5):
        q.enqueue(make_event(f"e{i}"))
    assert len(q) == 3
    batch = q.dequeue_batch(10)
    assert [e.event_name for e in batch] == ["e0", "e1", "e2"]


def test_requeue_prepends():
    q = EventQueue(max_size=10)
    q.enqueue(make_event("first"))
    batch = q.dequeue_batch(1)
    q.enqueue(make_event("second"))
    q.requeue_batch(batch)
    result = q.dequeue_batch(10)
    assert [e.event_name for e in result] == ["first", "second"]


def test_len():
    q = EventQueue(max_size=10)
    assert len(q) == 0
    q.enqueue(make_event())
    assert len(q) == 1
    q.dequeue_batch(1)
    assert len(q) == 0


def test_thread_safety():
    q = EventQueue(max_size=10_000)
    results = []

    def producer():
        for i in range(100):
            q.enqueue(make_event(f"e{i}"))

    threads = [threading.Thread(target=producer) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(q) == 1000


# --- SQLite persistence ---

def test_sqlite_enqueue_sets_db_id():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        q = EventQueue(max_size=10, persistence_path=path)
        event = make_event()
        q.enqueue(event)
        assert event.db_id is not None
        assert event.db_id > 0
    finally:
        os.unlink(path)


def test_sqlite_delete_from_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        q = EventQueue(max_size=10, persistence_path=path)
        q.enqueue(make_event("a"))
        q.enqueue(make_event("b"))
        batch = q.dequeue_batch(2)
        q.delete_from_db(batch)

        # Перезапустить очередь — DB должна быть пустой
        q2 = EventQueue(max_size=10, persistence_path=path)
        assert len(q2) == 0
    finally:
        os.unlink(path)


def test_sqlite_restore_on_restart():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        q = EventQueue(max_size=10, persistence_path=path)
        q.enqueue(make_event("persisted"))
        # Не удаляем из DB — симулируем падение процесса

        q2 = EventQueue(max_size=10, persistence_path=path)
        assert len(q2) == 1
        batch = q2.dequeue_batch(1)
        assert batch[0].event_name == "persisted"
        assert batch[0].db_id is not None
    finally:
        os.unlink(path)


def test_sqlite_no_duplicates_after_successful_send():
    """После delete_from_db события не должны появляться при перезапуске."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        q = EventQueue(max_size=10, persistence_path=path)
        q.enqueue(make_event("sent"))
        batch = q.dequeue_batch(1)
        q.delete_from_db(batch)

        q2 = EventQueue(max_size=10, persistence_path=path)
        assert len(q2) == 0
    finally:
        os.unlink(path)


def test_delete_from_db_without_db_is_noop():
    q = EventQueue(max_size=10)  # in-memory
    event = make_event()
    q.enqueue(event)
    batch = q.dequeue_batch(1)
    # Не должно падать
    q.delete_from_db(batch)
