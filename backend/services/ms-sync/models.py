"""
models.py — Modelos Pydantic para ms-sync v2
"""
from typing import Optional, Any, List, Dict
from pydantic import BaseModel


# ─── Eventos de sincronización ────────────────────────────────────────────────

class SyncEvent(BaseModel):
    source_node: int
    operation: str          # INSERT | UPDATE | DELETE
    table_name: str
    record_id: int
    payload: Optional[Any] = None
    # Campos opcionales para compatibilidad con API anterior
    target_node: Optional[int] = None
    lamport_ts: int = 0
    vector_clock: str = "[0,0,0]"
    created_epoch: int = 0


class PropagateRequest(BaseModel):
    """Recibido de ms-bookings o ms-flights."""
    event_type: str         # SEAT_LOCK | SEAT_RESERVE | SEAT_SELL | SEAT_AVAILABLE | SEAT_REFUND | FLIGHT_STATUS
    payload: Dict[str, Any]
    source_node: int
    lamport_ts: int = 0
    vector_clock: List[int] = [0, 0, 0]


class ReceiveRequest(BaseModel):
    """Recibido de un nodo peer (otro ms-sync)."""
    event_type: str
    payload: Dict[str, Any]
    source_node: int
    lamport_ts: int
    vector_clock: List[int]
    sent_epoch: int         # Para medir latencia


class ScheduleRefundRequest(BaseModel):
    seat_id: int
    flight_id: int
    delay_minutes: int = 15


# ─── Respuestas ───────────────────────────────────────────────────────────────

class SyncLogOut(BaseModel):
    log_id: int
    source_node: int
    target_node: int
    operation: str
    table_name: str
    record_id: int
    status: str
    lamport_ts: int
    vector_clock: str
    created_epoch: int
    applied_epoch: Optional[int]


class ClockState(BaseModel):
    node_id: int
    lamport_ts: int
    vector_clock: str
    timestamp: int


class NodeStatus(BaseModel):
    node_id: int
    status: str         # OK | DEGRADED | OFFLINE
    last_seen_epoch: int
    lamport_ts: int
    vector_clock: str
