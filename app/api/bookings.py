from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories import Repository
from app.schemas import BookingCreate, BookingRead
from app.services import BookingService

router = APIRouter(tags=['bookings'])


@router.get('/bookings', response_model=list[BookingRead])
def get_bookings(db: Session = Depends(get_db)) -> list[BookingRead]:
    repo = Repository(db)
    return [BookingRead.model_validate(item) for item in repo.list_bookings()]


@router.post('/bookings')
async def create_booking(payload: BookingCreate, db: Session = Depends(get_db)) -> dict:
    service = BookingService(db)
    result = await service.create_booking(payload)
    return {
        'request_id': result['request_id'],
        'booking': BookingRead.model_validate(result['booking']).model_dump(),
    }
