"""
models.py — Modelos Pydantic para ms-bookings v2
"""
from typing import Optional
from pydantic import BaseModel


# ─── Requests ────────────────────────────────────────────────────────────────

class LockRequest(BaseModel):
    seat_id: int
    flight_id: int       # necesario para enrutar a la BD correcta
    session_token: str


class ReserveRequest(BaseModel):
    seat_id: int
    flight_id: int
    session_token: str
    passport: str
    full_name: str
    email: Optional[str] = "sin_email@rafael-pabon.com"
    phone: Optional[str] = None
    nationality: Optional[str] = None


class PurchaseRequest(BaseModel):
    seat_id: int
    flight_id: int
    session_token: str
    passport: str
    full_name: str
    email: Optional[str] = "sin_email@rafael-pabon.com"
    phone: Optional[str] = None
    nationality: Optional[str] = None


class CancelRequest(BaseModel):
    seat_id: int
    flight_id: int
    passport: str


class RefundRequest(BaseModel):
    seat_id: int
    flight_id: int
    passport: str


# ─── Compatibilidad con API anterior ─────────────────────────────────────────

class PassengerCreate(BaseModel):
    full_name: str
    email: str
    passport_number: str
    phone: Optional[str] = None
    nationality: Optional[str] = None


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
    duration_seconds: int = 300


class PaymentRequest(BaseModel):
    ticket_id: int
    amount: float
