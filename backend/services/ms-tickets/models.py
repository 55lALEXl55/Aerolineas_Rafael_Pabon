"""
models.py — Modelos Pydantic para ms-tickets
"""
from typing import Optional
from pydantic import BaseModel


class TicketOut(BaseModel):
    ticket_id: int
    passenger_id: int
    flight_id: int
    seat_id: int
    status: str
    booking_epoch: int
    expiry_epoch: int
    payment_epoch: Optional[int]
    total_price: float
    pdf_url: Optional[str]
    node_id: int
    lamport_ts: int
    vector_clock: str
    last_update_epoch: int

    class Config:
        from_attributes = True


class RefundRequest(BaseModel):
    ticket_id: int
    reason: Optional[str] = None


class PDFRequest(BaseModel):
    ticket_id: int
