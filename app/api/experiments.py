from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.queue_manager import queue_manager
from app.repositories import Repository
from app.schemas import MetricsRead, WorkerDelayRequest

router = APIRouter(prefix='/experiments', tags=['experiments'])


@router.post('/reset')
def reset_data(db: Session = Depends(get_db)) -> dict:
    repo = Repository(db)
    repo.clear_all()
    db.commit()
    return {'status': 'ok'}


@router.post('/seed')
def seed_data(db: Session = Depends(get_db)) -> dict:
    repo = Repository(db)
    repo.seed_defaults()
    db.commit()
    return {'status': 'ok'}


@router.get('/metrics', response_model=list[MetricsRead])
def get_metrics(db: Session = Depends(get_db)) -> list[MetricsRead]:
    repo = Repository(db)
    return [MetricsRead.model_validate(item) for item in repo.list_metrics()]


@router.post('/worker/on')
def worker_on() -> dict:
    queue_manager.worker_enabled = True
    return {'worker_enabled': True, 'delay_ms': queue_manager.delay_ms}


@router.post('/worker/off')
def worker_off() -> dict:
    queue_manager.worker_enabled = False
    return {'worker_enabled': False, 'delay_ms': queue_manager.delay_ms}


@router.post('/worker/delay')
def worker_delay(payload: WorkerDelayRequest) -> dict:
    queue_manager.delay_ms = payload.delay_ms
    return {'worker_enabled': queue_manager.worker_enabled, 'delay_ms': queue_manager.delay_ms}
