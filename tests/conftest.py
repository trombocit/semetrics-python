"""
Фикстуры для integration-тестов.

Запуск:
    pytest tests/ -m integration -v

Требования:
    - Docker Desktop запущен
    - docker compose доступен в PATH
    - порт 18765 свободен
"""

import subprocess
import time
from pathlib import Path

import httpx
import pytest

COMPOSE_FILE = Path(__file__).parent.parent / "docker-compose.sdk-test.yml"
BASE_URL = "http://localhost:18765"
INGEST_ENDPOINT = f"{BASE_URL}/events"


def _compose(*args):
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _wait_for_service(url: str, timeout: int = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=2)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError(f"Сервис {url} не ответил за {timeout}с")


@pytest.fixture(scope="session")
def svc_events_stack():
    """Поднимает svc_events + postgres локально, останавливает после сессии."""
    _compose("up", "--build", "-d")
    try:
        _wait_for_service(f"{BASE_URL}/health")
        yield BASE_URL
    finally:
        _compose("down", "--volumes")


@pytest.fixture(scope="session")
def sdk_api_key(svc_events_stack):
    """Создаёт тестовый проект и API-ключ через internal API."""
    with httpx.Client(base_url=svc_events_stack) as client:
        # Создать проект
        r = client.post("/internal/projects", json={"name": "sdk-integration-test"})
        r.raise_for_status()
        project_id = r.json()["data"]["id"]

        # Создать API-ключ
        r = client.post(
            f"/internal/projects/{project_id}/api-keys",
            json={"name": "test-key"},
        )
        r.raise_for_status()
        api_key = r.json()["data"]["key"]

    return api_key, project_id, INGEST_ENDPOINT
