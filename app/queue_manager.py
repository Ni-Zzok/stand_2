from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Literal


TaskType = Literal['audit', 'notification']


@dataclass(slots=True)
class AsyncTask:
    task_type: TaskType
    booking_id: int
    recipient: str | None
    request_id: str
    scenario: str
    mode: str
    enqueued_at: datetime


class QueueManager:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[AsyncTask] = asyncio.Queue()
        self.worker_enabled: bool = True
        self.delay_ms: int = 0

    async def put(self, task: AsyncTask) -> None:
        await self.queue.put(task)

    async def get(self) -> AsyncTask:
        return await self.queue.get()

    def task_done(self) -> None:
        self.queue.task_done()


queue_manager = QueueManager()
