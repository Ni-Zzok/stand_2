from __future__ import annotations

import asyncio
from datetime import datetime

from app.db import SessionLocal
from app.queue_manager import queue_manager
from app.repositories import Repository


async def run_worker() -> None:
    while True:
        task = await queue_manager.get()
        try:
            while not queue_manager.worker_enabled:
                await asyncio.sleep(0.05)

            if queue_manager.delay_ms > 0:
                await asyncio.sleep(queue_manager.delay_ms / 1000)

            started_at = datetime.utcnow()
            with SessionLocal() as db:
                repo = Repository(db)
                if task.task_type == 'audit':
                    repo.create_audit_log(booking_id=task.booking_id, event_type='booking_created_async')
                elif task.task_type == 'notification' and task.recipient:
                    repo.create_notification(booking_id=task.booking_id, recipient=task.recipient)

                finished_at = datetime.utcnow()
                duration_ms = int((finished_at - started_at).total_seconds() * 1000)
                repo.create_metrics_event(
                    request_id=task.request_id,
                    scenario=task.scenario,
                    mode=task.mode,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=duration_ms,
                    result='worker_task_success',
                    notes=f'processed:{task.task_type}',
                )
                db.commit()
        except Exception as exc:  # noqa: BLE001
            with SessionLocal() as db:
                repo = Repository(db)
                now = datetime.utcnow()
                repo.create_metrics_event(
                    request_id=task.request_id,
                    scenario=task.scenario,
                    mode=task.mode,
                    started_at=now,
                    finished_at=now,
                    duration_ms=0,
                    result='worker_task_error',
                    notes=f'{task.task_type}:{exc}',
                )
                db.commit()
        finally:
            queue_manager.task_done()
