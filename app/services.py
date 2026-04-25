from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.queue_manager import AsyncTask, queue_manager
from app.repositories import Repository
from app.schemas import BookingCreate


class BookingService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = Repository(db)

    async def create_booking(self, payload: BookingCreate) -> dict:
        started_at = datetime.utcnow()
        request_id = str(uuid4())

        try:
            if payload.end_time <= payload.start_time:
                raise HTTPException(status_code=400, detail='end_time must be greater than start_time')

            room = self.repo.get_room(payload.room_id)
            if room is None:
                raise HTTPException(status_code=404, detail='Room not found')

            user = self.repo.get_user(payload.user_id)
            if user is None:
                raise HTTPException(status_code=404, detail='User not found')

            if self.repo.has_conflict(payload.room_id, payload.start_time, payload.end_time):
                finished_at = datetime.utcnow()
                duration_ms = int((finished_at - started_at).total_seconds() * 1000)
                self.repo.create_metrics_event(
                    request_id=request_id,
                    scenario=payload.scenario,
                    mode=payload.mode,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=duration_ms,
                    result='conflict',
                    notes='overlap_detected',
                )
                self.db.commit()
                raise HTTPException(status_code=409, detail='Booking conflict for selected room and time interval')

            booking = self.repo.create_booking(
                room_id=payload.room_id,
                user_id=payload.user_id,
                start_time=payload.start_time,
                end_time=payload.end_time,
                mode=payload.mode,
            )

            if payload.mode == 'centralized_sync':
                self.repo.create_audit_log(booking.id, 'booking_created_sync')
                self.repo.create_notification(booking.id, recipient=user.name)
            elif payload.mode == 'hybrid_async':
                await queue_manager.put(
                    AsyncTask(
                        task_type='audit',
                        booking_id=booking.id,
                        recipient=None,
                        request_id=request_id,
                        scenario=payload.scenario,
                        mode=payload.mode,
                        enqueued_at=datetime.utcnow(),
                    )
                )
                await queue_manager.put(
                    AsyncTask(
                        task_type='notification',
                        booking_id=booking.id,
                        recipient=user.name,
                        request_id=request_id,
                        scenario=payload.scenario,
                        mode=payload.mode,
                        enqueued_at=datetime.utcnow(),
                    )
                )
            else:
                raise HTTPException(status_code=400, detail='Unsupported mode')

            finished_at = datetime.utcnow()
            duration_ms = int((finished_at - started_at).total_seconds() * 1000)
            self.repo.create_metrics_event(
                request_id=request_id,
                scenario=payload.scenario,
                mode=payload.mode,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                result='success',
                notes=f'booking_id={booking.id}',
            )
            self.db.commit()
            self.db.refresh(booking)

            return {
                'request_id': request_id,
                'booking': booking,
            }
        except HTTPException:
            if self.db.in_transaction():
                self.db.rollback()
            raise
        except Exception as exc:  # noqa: BLE001
            if self.db.in_transaction():
                self.db.rollback()
            now = datetime.utcnow()
            self.repo.create_metrics_event(
                request_id=request_id,
                scenario=payload.scenario,
                mode=payload.mode,
                started_at=started_at,
                finished_at=now,
                duration_ms=int((now - started_at).total_seconds() * 1000),
                result='error',
                notes=str(exc),
            )
            self.db.commit()
            raise HTTPException(status_code=500, detail='Internal booking error') from exc
