from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from semetrics import Semetrics


@pytest.fixture
def client():
    with patch("semetrics.client.BackgroundWorker") as MockWorker, \
         patch("semetrics.client.HttpTransport"):
        mock_worker = MagicMock()
        MockWorker.return_value = mock_worker
        sm = Semetrics(api_key="sm_live_test", endpoint="https://test.semetrics.ru/events")
        yield sm, mock_worker


def test_track_enqueues_event(client):
    sm, _ = client
    sm.track("page_viewed", user_id="u1")
    assert len(sm._queue) == 1


def test_track_event_name(client):
    sm, _ = client
    sm.track("checkout_completed")
    batch = sm._queue.dequeue_batch(1)
    assert batch[0].event_name == "checkout_completed"


def test_track_user_id(client):
    sm, _ = client
    sm.track("login", user_id="user_42")
    batch = sm._queue.dequeue_batch(1)
    assert batch[0].user_id == "user_42"


def test_track_properties(client):
    sm, _ = client
    sm.track("purchase", properties={"amount": 99, "currency": "RUB"})
    batch = sm._queue.dequeue_batch(1)
    assert batch[0].properties == {"amount": 99, "currency": "RUB"}


def test_track_platform_is_python(client):
    sm, _ = client
    sm.track("event")
    batch = sm._queue.dequeue_batch(1)
    assert batch[0].platform == "python"


def test_track_client_ts_default_is_utc_now(client):
    sm, _ = client
    before = datetime.now(timezone.utc)
    sm.track("event")
    after = datetime.now(timezone.utc)
    batch = sm._queue.dequeue_batch(1)
    assert before <= batch[0].client_ts <= after


def test_track_custom_client_ts(client):
    sm, _ = client
    ts = datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
    sm.track("event", client_ts=ts)
    batch = sm._queue.dequeue_batch(1)
    assert batch[0].client_ts == ts


def test_flush_calls_worker_flush_sync(client):
    sm, mock_worker = client
    sm.flush()
    mock_worker.flush_sync.assert_called_once()


def test_shutdown_calls_worker_stop(client):
    sm, mock_worker = client
    sm.shutdown()
    mock_worker.stop.assert_called_once()


def test_context_manager_calls_shutdown():
    with patch("semetrics.client.BackgroundWorker") as MockWorker, \
         patch("semetrics.client.HttpTransport"):
        mock_worker = MagicMock()
        MockWorker.return_value = mock_worker
        with Semetrics(api_key="sm_live_test", endpoint="https://test.semetrics.ru/events"):
            pass
        mock_worker.stop.assert_called_once()


def test_worker_started_on_init():
    with patch("semetrics.client.BackgroundWorker") as MockWorker, \
         patch("semetrics.client.HttpTransport"):
        mock_worker = MagicMock()
        MockWorker.return_value = mock_worker
        Semetrics(api_key="sm_live_test", endpoint="https://test.semetrics.ru/events")
        mock_worker.start.assert_called_once()
