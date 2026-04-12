"""
models.py — Modelos Pydantic para ms-dashboard
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel


class NodeStatus(BaseModel):
    node_id: int
    region: str
    status: str
    total_flights: int
    total_seats: int
    sold_seats: int
    available_seats: int
    reserved_seats: int
    occupancy_rate: float


class RevenueStats(BaseModel):
    node_id: int
    region: str
    total_revenue: float
    paid_tickets: int
    avg_ticket_price: float


class SyncStatus(BaseModel):
    node_id: int
    pending_events: int
    applied_events: int
    conflict_events: int
    last_sync_epoch: Optional[int]


class DashboardSummary(BaseModel):
    total_flights: int
    total_passengers: int
    total_revenue: float
    nodes: List[NodeStatus]
    sync: List[SyncStatus]
    timestamp: int
