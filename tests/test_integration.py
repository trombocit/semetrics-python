"""
Integration-тесты Python SDK против реального svc_events.

Запуск:
    pytest tests/test_integration.py -m integration -v

Требования: Docker Desktop запущен.
"""

import os
import tempfile
import time

import httpx
import pytest

from semetrics import Semetrics

pytestmark = pytest.mark.integration


@pytest.fixture
def sm(sdk_api_key):
    api_key, project_id, endpoint = sdk_api_key
    client = Semetrics(api_key=api_key, endpoint=endpoint, flush_interval=60)
    yield client, project_id
    client.shutdown()


def _get_recent_events(base_url: str, project_id: str, limit: int = 50) -> list[dict]:
    with httpx.Client(base_url=base_url) as client:
        r = client.get("/internal/events/recent", params={"project_id": project_id, "limit": limit})
        r.raise_for_status()
        return r.json()["data"]["events"]


# --- Базовая доставка ---

def test_track_single_event_delivered(sdk_api_key):
    api_key, project_id, endpoint = sdk_api_key
    sm = Semetrics(api_key=api_key, endpoint=endpoint)
    sm.track("integration_single_event", user_id="test_user_1")
    sm.shutdown()

    events = _get_recent_events(endpoint.rsplit("/", 1)[0], project_id)
    names = [e["event_name"] for e in events]
    assert "integration_single_event" in names


def test_track_multiple_events_delivered(sdk_api_key):
    api_key, project_id, endpoint = sdk_api_key
    sm = Semetrics(api_key=api_key, endpoint=endpoint)
    for i in range(5):
        sm.track(f"integration_multi_{i}", user_id="test_user_2")
    sm.shutdown()

    events = _get_recent_events(endpoint.rsplit("/", 1)[0], project_id)
    names = [e["event_name"] for e in events]
    for i in range(5):
        assert f"integration_multi_{i}" in names


def test_track_with_properties_delivered(sdk_api_key):
    api_key, project_id, endpoint = sdk_api_key
    sm = Semetrics(api_key=api_key, endpoint=endpoint)
    sm.track(
        "integration_props_event",
        user_id="test_user_3",
        properties={"plan": "pro", "amount": 990},
    )
    sm.shutdown()

    events = _get_recent_events(endpoint.rsplit("/", 1)[0], project_id)
    matched = [e for e in events if e["event_name"] == "integration_props_event"]
    assert matched, "Событие не найдено"
    import json
    props = json.loads(matched[0]["properties"]) if isinstance(matched[0]["properties"], str) else matched[0]["properties"]
    assert props.get("plan") == "pro"
    assert props.get("amount") == 990


# --- Flush ---

def test_flush_delivers_immediately(sdk_api_key):
    api_key, project_id, endpoint = sdk_api_key
    sm = Semetrics(api_key=api_key, endpoint=endpoint, flush_interval=3600)
    sm.track("integration_flush_test", user_id="test_user_4")
    sm.flush()  # принудительно, не ждём интервал

    events = _get_recent_events(endpoint.rsplit("/", 1)[0], project_id)
    names = [e["event_name"] for e in events]
    assert "integration_flush_test" in names
    sm.shutdown()


# --- SQLite-персистентность ---

def test_sqlite_persistence_survives_restart(sdk_api_key):
    """
    Событие трекается, клиент "падает" (не вызывает shutdown),
    новый клиент с тем же persistence_path при shutdown отправляет события.
    """
    api_key, project_id, endpoint = sdk_api_key

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Первый клиент: трекаем, но НЕ вызываем shutdown (симуляция краша)
        sm1 = Semetrics(api_key=api_key, endpoint=endpoint, persistence_path=db_path, flush_interval=3600)
        sm1.track("integration_persistence_test", user_id="test_user_5")
        # Останавливаем worker без flush (имитируем падение через stop_event без flush_sync)
        sm1._worker._stop_event.set()
        time.sleep(0.1)

        # Второй клиент с тем же файлом: должен восстановить и отправить
        sm2 = Semetrics(api_key=api_key, endpoint=endpoint, persistence_path=db_path)
        sm2.shutdown()  # восстанавливает из SQLite и отправляет

        events = _get_recent_events(endpoint.rsplit("/", 1)[0], project_id)
        names = [e["event_name"] for e in events]
        assert "integration_persistence_test" in names
    finally:
        os.unlink(db_path)
