# Experimental booking stand (FastAPI + PostgreSQL)

Минимальный исследовательский backend-стенд для сравнения двух режимов обработки бизнес-операции «бронирование помещения»:

- `centralized_sync`: все шаги выполняются синхронно в рамках одного HTTP-запроса.
- `hybrid_async`: создание бронирования синхронно, вторичные операции (audit/notification) уходят в in-memory очередь `asyncio.Queue` и обрабатываются воркером.

## 1) Назначение стенда

Стенд позволяет воспроизводимо сравнить два архитектурных режима по:
- времени ответа API;
- количеству успешных бронирований;
- количеству конфликтов (`HTTP 409`);
- метрикам фоновой обработки задач.

## 2) Установка зависимостей

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) Локальный PostgreSQL

Пример через локально установленный PostgreSQL:

1. Создайте БД:
```sql
CREATE DATABASE stand_db;
```
2. Убедитесь, что пользователь/пароль подходят под URL подключения.

## 4) Настройка `DATABASE_URL`

Создайте `.env` на основе `.env.example`:

```bash
cp .env .env
```

Пример:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/stand_db
WORKER_DELAY_MS=0
```

> SQLite не используется.

## 5) Запуск API

```bash
uvicorn app.main:app --reload
```

При старте приложение автоматически создаёт таблицы через `metadata.create_all()`.

## 6) Запуск worker

Отдельный процесс не нужен: воркер запускается как фоновая задача внутри FastAPI при старте.

Управление:
- `POST /experiments/worker/on`
- `POST /experiments/worker/off`
- `POST /experiments/worker/delay` c JSON `{"delay_ms": 300}`

## 7) Основные API endpoint'ы

- `POST /experiments/reset` — очистка таблиц.
- `POST /experiments/seed` — создание 3 комнат и 3 пользователей.
- `GET /rooms`
- `GET /bookings`
- `POST /bookings`
- `GET /experiments/metrics`

Пример `POST /bookings`:

```json
{
  "room_id": 1,
  "user_id": 1,
  "start_time": "2026-04-20T10:00:00",
  "end_time": "2026-04-20T11:00:00",
  "mode": "hybrid_async",
  "scenario": "manual_test"
}
```

## 8) Нагрузочный скрипт

Скрипт: `load/compare_modes.py`

Что делает:
1. reset + seed;
2. прогоняет оба режима (`centralized_sync`, `hybrid_async`);
3. поддерживает два сценария:
   - `A` (`--scenario a`): 20 последовательных неконфликтующих запросов;
   - `B` (`--scenario b`): 20 параллельных запросов, часть конфликтует;
4. сохраняет результат в CSV (`results.csv` по умолчанию).

Запуск:

```bash
python load/compare_modes.py --base-url http://127.0.0.1:8000 --scenario a --output results.csv
python load/compare_modes.py --base-url http://127.0.0.1:8000 --scenario b --output results_scenario_b.csv
```

CSV-колонки:
- `mode`
- `total_requests`
- `success_count`
- `conflict_count`
- `avg_response_ms`
- `max_response_ms`

## 9) Какие метрики собираются

Для каждого `POST /bookings` фиксируется `MetricsEvent`:
- `request_id`
- `scenario`
- `mode`
- `started_at`
- `finished_at`
- `duration_ms`
- `result` (`success` / `conflict` / `error`)
- `notes`

Дополнительно воркер пишет события:
- `worker_task_success`
- `worker_task_error`

Это позволяет отдельно оценить задержки в фоне и влияние режима обработки на latency ответа.
