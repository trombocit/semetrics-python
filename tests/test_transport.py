from datetime import datetime, timezone

import httpx
import pytest
import respx

from semetrics.models import Event
from semetrics.transport import HttpTransport


def make_event() -> Event:
    return Event(
        event_name="test_event",
        client_ts=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        user_id="user_1",
    )


ENDPOINT = "https://test.semetrics.ru/events"
API_KEY = "sm_live_testkey"


@respx.mock
def test_send_batch_success():
    respx.post(f"{ENDPOINT}/ingest/batch").mock(
        return_value=httpx.Response(200, json={"status": {"code": ""}, "data": {"accepted": 1}})
    )
    transport = HttpTransport(api_key=API_KEY, endpoint=ENDPOINT)
    transport.send_batch([make_event()])  # не должно бросать исключение


@respx.mock
def test_send_batch_sends_correct_payload():
    route = respx.post(f"{ENDPOINT}/ingest/batch").mock(
        return_value=httpx.Response(200, json={"status": {"code": ""}, "data": {"accepted": 1}})
    )
    transport = HttpTransport(api_key=API_KEY, endpoint=ENDPOINT)
    transport.send_batch([make_event()])

    request = route.calls[0].request
    body = request.read()
    import json
    payload = json.loads(body)
    assert "events" in payload
    assert payload["events"][0]["event_name"] == "test_event"


@respx.mock
def test_send_batch_includes_api_key_header():
    route = respx.post(f"{ENDPOINT}/ingest/batch").mock(
        return_value=httpx.Response(200, json={"status": {"code": ""}, "data": {"accepted": 1}})
    )
    transport = HttpTransport(api_key=API_KEY, endpoint=ENDPOINT)
    transport.send_batch([make_event()])

    request = route.calls[0].request
    assert request.headers["X-API-Key"] == API_KEY


@respx.mock
def test_send_batch_raises_on_http_401():
    respx.post(f"{ENDPOINT}/ingest/batch").mock(
        return_value=httpx.Response(401)
    )
    transport = HttpTransport(api_key=API_KEY, endpoint=ENDPOINT)
    with pytest.raises(httpx.HTTPStatusError):
        transport.send_batch([make_event()])


@respx.mock
def test_send_batch_raises_on_http_500():
    respx.post(f"{ENDPOINT}/ingest/batch").mock(
        return_value=httpx.Response(500)
    )
    transport = HttpTransport(api_key=API_KEY, endpoint=ENDPOINT)
    with pytest.raises(httpx.HTTPStatusError):
        transport.send_batch([make_event()])


@respx.mock
def test_send_batch_raises_on_app_error_code():
    respx.post(f"{ENDPOINT}/ingest/batch").mock(
        return_value=httpx.Response(
            200,
            json={"status": {"code": "VALIDATION_ERROR", "message": "bad event_name"}},
        )
    )
    transport = HttpTransport(api_key=API_KEY, endpoint=ENDPOINT)
    with pytest.raises(RuntimeError, match="bad event_name"):
        transport.send_batch([make_event()])


@respx.mock
def test_send_batch_endpoint_trailing_slash():
    """Убедиться что лишний слэш в endpoint не ломает URL."""
    route = respx.post(f"{ENDPOINT}/ingest/batch").mock(
        return_value=httpx.Response(200, json={"status": {"code": ""}, "data": {"accepted": 1}})
    )
    transport = HttpTransport(api_key=API_KEY, endpoint=ENDPOINT + "/")
    transport.send_batch([make_event()])
    assert route.called
