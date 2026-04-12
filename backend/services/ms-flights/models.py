"""
models.py — Modelos Pydantic para ms-flights
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class FlightBase(BaseModel):
    flight_number: str
    aircraft_id: int
    origin: str = Field(..., min_length=3, max_length=3)
    destination: str = Field(..., min_length=3, max_length=3)
    departure_epoch: int
    arrival_epoch: int
    duration_minutes: int
    price_economy: float
    price_first: float
    status: str = "SCHEDULED"
    available_economy: int = 0
    available_first: int = 0
    node_id: int = 1


class FlightOut(FlightBase):
    flight_id: int
    lamport_ts: int
    vector_clock: str
    last_update_epoch: int

    class Config:
        from_attributes = True


class FlightSearchParams(BaseModel):
    origin: Optional[str] = None
    destination: Optional[str] = None
    departure_from: Optional[int] = None
    departure_to: Optional[int] = None
    status: Optional[str] = None
    limit: int = 50
    offset: int = 0


class SeatOut(BaseModel):
    seat_id: int
    flight_id: int
    seat_number: str
    seat_class: str
    status: str
    locked_until: Optional[int]
    price: float
    node_id: int
    lamport_ts: int
    vector_clock: str
    last_update_epoch: int

    class Config:
        from_attributes = True


class AircraftOut(BaseModel):
    aircraft_id: int
    model: str
    manufacturer: str
    seats_first: int
    seats_economy: int
    total_seats: int
    engines: int

    class Config:
        from_attributes = True
