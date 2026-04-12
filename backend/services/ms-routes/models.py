"""
models.py — Modelos Pydantic para ms-routes
"""
from typing import List, Optional
from pydantic import BaseModel


class RouteSegment(BaseModel):
    origin: str
    destination: str
    flight_id: int
    flight_number: str
    departure_epoch: int
    arrival_epoch: int
    duration_minutes: int
    price_economy: float
    price_first: float
    aircraft_model: Optional[str] = None


class RouteResult(BaseModel):
    segments: List[RouteSegment]
    total_price_economy: float
    total_price_first: float
    total_duration_minutes: int
    stops: int  # 0 = directo


class RouteSearchParams(BaseModel):
    origin: str
    destination: str
    departure_from: int
    departure_to: Optional[int] = None
    seat_class: str = "ECONOMY"
    max_stops: int = 2
    algorithm: str = "dijkstra"  # dijkstra | tsp
