"""
models.py — Modelos Pydantic para ms-bookings
"""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class PassengerCreate(BaseModel):
    full_name: str
    email: str
    passport_number: str
    phone: Optional[str] = None
    nationality: Optional[str] = None


class PassengerOut(PassengerCreate):
    passenger_id: int
    node_id: int
    lamport_ts: int
    vector_clock: str
    last_update_epoch: int

    class Config:
        from_attributes = True


class BookingCreate(BaseModel):
    passenger: PassengerCreate
    flight_id: int
    seat_id: int


class BookingOut(BaseModel):
    ticket_id: int
    passenger_id: int
    flight_id: int
    seat_id: int
    status: str
    booking_epoch: int
    expiry_epoch: int
    total_price: float
    node_id: int
    vector_clock: str
    lamport_ts: int


class SeatLockRequest(BaseModel):
    seat_id: int
    flight_id: int
    duration_seconds: int = 300  # 5 min máx según CLAUDE.md


class PaymentRequest(BaseModel):
    ticket_id: int
    amount: float
