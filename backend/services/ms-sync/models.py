"""
models.py — Modelos Pydantic para ms-sync
"""
from typing import Optional, Any
from pydantic import BaseModel


class SyncEvent(BaseModel):
    source_node: int
    target_node: int
    operation: str          # INSERT | UPDATE | DELETE
    table_name: str
    record_id: int
    payload: Optional[Any] = None
    lamport_ts: int = 0
    vector_clock: str = "[0,0,0]"
    created_epoch: int


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
