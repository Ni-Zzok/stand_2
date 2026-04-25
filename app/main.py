from __future__ import annotations

import asyncio

from fastapi import FastAPI

from app.api.bookings import router as bookings_router
from app.api.experiments import router as experiments_router
from app.api.rooms import router as rooms_router
from app.config import settings
from app.db import Base, engine
from app.queue_manager import queue_manager
from app.worker import run_worker

app = FastAPI(title=settings.app_name)

app.include_router(rooms_router)
app.include_router(bookings_router)
app.include_router(experiments_router)


@app.on_event('startup')
async def startup() -> None:
    Base.metadata.create_all(bind=engine)
    queue_manager.delay_ms = settings.worker_delay_ms
    app.state.worker_task = asyncio.create_task(run_worker())


@app.on_event('shutdown')
async def shutdown() -> None:
    worker_task: asyncio.Task = app.state.worker_task
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass


@app.get('/')
def health() -> dict:
    return {'status': 'ok', 'service': settings.app_name}
