from datetime import datetime, timezone

from semetrics.models import Event


def make_event(**kwargs) -> Event:
    defaults = dict(
        event_name="test_event",
        client_ts=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    return Event(**{**defaults, **kwargs})


def test_to_dict_minimal():
    event = make_event()
    d = event.to_dict()
    assert d["event_name"] == "test_event"
    assert d["platform"] == "python"
    assert d["sdk_version"] == "0.1.0"
    assert d["properties"] == {}
    assert d["user_id"] is None
    assert d["anonymous_id"] is None
    assert d["session_id"] is None


def test_to_dict_datetime_iso():
    event = make_event()
    d = event.to_dict()
    assert d["client_ts"] == "2026-01-01T12:00:00+00:00"


def test_to_dict_properties():
    event = make_event(properties={"plan": "pro", "amount": 99})
    d = event.to_dict()
    assert d["properties"] == {"plan": "pro", "amount": 99}


def test_to_dict_excludes_db_id():
    event = make_event(db_id=42)
    d = event.to_dict()
    assert "db_id" not in d


def test_db_id_default_none():
    event = make_event()
    assert event.db_id is None
