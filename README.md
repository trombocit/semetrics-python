# Semetrics Python SDK

Python SDK для отправки аналитических событий на платформу Semetrics.

## Установка

```bash
pip install semetrics
```

## Быстрый старт

```python
from semetrics import Semetrics

# Инициализация (один раз при старте приложения)
semetrics = Semetrics(
    api_key="sm_live_ваш_ключ",
    endpoint="https://semetrics.ru/events",
)

# Отправка событий (не блокирует — очередь + фоновый поток)
semetrics.track(
    event_name="user_signed_up",
    user_id="user_123",
    properties={"plan": "pro", "source": "organic"},
)

semetrics.track(
    event_name="checkout_completed",
    user_id="user_123",
    properties={"amount": 1990, "currency": "RUB", "items": 3},
)

# При завершении программы — отправить все накопленные события
semetrics.shutdown()
```

## Использование через контекстный менеджер

```python
with Semetrics(api_key="sm_live_...", endpoint="https://semetrics.ru/events") as sm:
    sm.track("page_viewed", user_id="u1", properties={"page": "/home"})
# shutdown() вызывается автоматически при выходе из блока
```

## Параметры конструктора

| Параметр | По умолчанию | Описание |
|----------|-------------|----------|
| `api_key` | обязательный | API-ключ проекта (`sm_live_...`) |
| `endpoint` | `https://semetrics.ru/events` | URL сервиса |
| `flush_interval` | `5` | Интервал фонового сброса (секунды) |
| `batch_size` | `50` | Максимум событий в одном запросе |
| `max_queue_size` | `10_000` | Максимум событий в памяти |
| `max_retries` | `3` | Попыток при ошибке отправки |
| `request_timeout` | `10` | Таймаут HTTP запроса (секунды) |
| `persistence_path` | `None` | Путь к SQLite для персистентной очереди |

## Персистентная очередь (опционально)

Для серверных приложений с требованием "ни одно событие не должно потеряться":

```python
semetrics = Semetrics(
    api_key="sm_live_...",
    endpoint="https://semetrics.ru/events",
    persistence_path="/var/lib/myapp/semetrics_queue.db",
)
```

События сохраняются в SQLite и отправляются даже после перезапуска процесса.

## Принудительный сброс

```python
# Отправить всё накопленное прямо сейчас (блокирует до завершения)
semetrics.flush()
```

## Поля события

| Поле | Тип | Обязательное | Описание |
|------|-----|-------------|----------|
| `event_name` | str | ✅ | Название события |
| `user_id` | str | — | ID аутентифицированного пользователя |
| `anonymous_id` | str | — | ID анонимного пользователя |
| `session_id` | str | — | ID сессии |
| `properties` | dict | — | Произвольные свойства события |
| `client_ts` | datetime | — | Время события (по умолчанию — `now()`) |
