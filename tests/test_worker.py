import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from semetrics.models import Event
from semetrics.queue import EventQueue
from semetrics.worker import BackgroundWorker


def make_event(name: str = "test_event") -> Event:
    return Event(
        event_name=name,
        client_ts=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


def make_worker(queue: EventQueue, transport=None, **kwargs) -> BackgroundWorker:
    if transport is None:
        transport = MagicMock()
    defaults = dict(flush_interval=60, batch_size=50, max_retries=3)
    return BackgroundWorker(queue=queue, transport=transport, **{**defaults, **kwargs})


def test_flush_sync_sends_all_events():
    q = EventQueue(max_size=10)
    transport = MagicMock()
    worker = make_worker(q, transport)

    for i in range(5):
        q.enqueue(make_event(f"e{i}"))

    worker.flush_sync()
    assert transport.send_batch.called
    total_sent = sum(len(call.args[0]) for call in transport.send_batch.call_args_list)
    assert total_sent == 5
    assert len(q) == 0


def test_flush_sync_empty_queue_is_noop():
    q = EventQueue(max_size=10)
    transport = MagicMock()
    worker = make_worker(q, transport)
    worker.flush_sync()
    transport.send_batch.assert_not_called()


def test_stop_flushes_remaining_events():
    q = EventQueue(max_size=10)
    transport = MagicMock()
    worker = make_worker(q, transport)

    for i in range(3):
        q.enqueue(make_event(f"e{i}"))

    worker.stop()
    assert transport.send_batch.called
    assert len(q) == 0


def test_retry_on_transient_error():
    q = EventQueue(max_size=10)
    transport = MagicMock()
    transport.send_batch.side_effect = [ConnectionError("timeout"), None]

    worker = make_worker(q, transport, max_retries=3)
    q.enqueue(make_event())

    with patch("time.sleep"):  # не ждём реальный backoff
        worker.flush_sync()

    assert transport.send_batch.call_count == 2
    assert len(q) == 0


def test_batch_dropped_after_max_retries(caplog):
    q = EventQueue(max_size=10)
    transport = MagicMock()
    transport.send_batch.side_effect = ConnectionError("always fails")

    worker = make_worker(q, transport, max_retries=3)
    q.enqueue(make_event())

    import logging
    with patch("time.sleep"), caplog.at_level(logging.ERROR, logger="semetrics.worker"):
        worker.flush_sync()

    assert transport.send_batch.call_count == 3
    assert len(q) == 0
    assert "потерян" in caplog.text


def test_respects_batch_size():
    q = EventQueue(max_size=100)
    transport = MagicMock()
    worker = make_worker(q, transport, batch_size=3)

    for i in range(7):
        q.enqueue(make_event(f"e{i}"))

    worker.flush_sync()
    # 7 событий по 3 = 3 батча (3+3+1)
    call_sizes = [len(call.args[0]) for call in transport.send_batch.call_args_list]
    assert call_sizes == [3, 3, 1]


def test_background_flush_triggered_by_interval():
    q = EventQueue(max_size=10)
    transport = MagicMock()
    worker = make_worker(q, transport, flush_interval=0.05)
    worker.start()

    q.enqueue(make_event())
    time.sleep(0.2)
    worker.stop()

    assert transport.send_batch.called


def test_delete_from_db_called_after_success():
    """После успешной отправки worker должен удалять события из DB."""
    q = MagicMock(spec=EventQueue)
    q.__len__ = MagicMock(side_effect=[1, 0])
    q.dequeue_batch.return_value = [make_event()]
    transport = MagicMock()

    worker = make_worker(q, transport)
    worker.flush_sync()

    q.delete_from_db.assert_called_once()
