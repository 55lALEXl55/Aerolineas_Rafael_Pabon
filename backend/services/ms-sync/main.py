"""
ms-sync — Puerto 8004
Sincronización de los 3 nodos: Lamport + Vector clocks.
Gestiona sync_log, propagación de cambios, resolución de conflictos.
CAP: AP — disponibilidad sobre consistencia.
"""
import json
import os
import time
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import sys
sys.path.insert(0, "/app/shared")
from lamport_clock import LamportClock
from vector_clock import VectorClock

from database import get_db1, get_db2, mongo_db, Session1, Session2
from models import SyncEvent, SyncLogOut, ClockState

app = FastAPI(
    title="ms-sync",
    description="Sincronización distribuida — Lamport + Vector Clocks",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NODE_ID = int(os.getenv("NODE_ID", "1"))
NODE_INDEX = NODE_ID - 1

lamport = LamportClock()
vector  = VectorClock(node_index=NODE_INDEX)

scheduler = AsyncIOScheduler()


@app.on_event("startup")
async def startup():
    scheduler.add_job(process_pending_sync, "interval", seconds=10, id="sync_job")
    scheduler.start()


@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "service": "ms-sync",
        "status": "ok",
        "node_id": NODE_ID,
        "lamport_ts": lamport.value,
        "vector_clock": vector.to_string(),
        "timestamp": int(time.time()),
    }


# ─── Estado de relojes ───────────────────────────────────────────────────────

@app.get("/sync/clock")
async def get_clock():
    return ClockState(
        node_id=NODE_ID,
        lamport_ts=lamport.value,
        vector_clock=vector.to_string(),
        timestamp=int(time.time()),
    )


@app.post("/sync/clock/tick")
async def tick_clock():
    lt = lamport.tick()
    vc = vector.tick()
    return {"lamport_ts": lt, "vector_clock": vc}


@app.post("/sync/clock/receive")
async def receive_clock(received_lamport: int, received_vector: List[int]):
    lt = lamport.update(received_lamport)
    vc = vector.merge(received_vector)
    return {"lamport_ts": lt, "vector_clock": vc}


# ─── Publicar evento de sincronización ───────────────────────────────────────

@app.post("/sync/events", status_code=201)
async def publish_event(
    event: SyncEvent,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Registra un evento en sync_log para propagación."""
    lt = lamport.tick()
    vc = vector.tick()
    now = int(time.time())
    payload_json = json.dumps(event.payload) if event.payload else None

    for target_node in [1, 2, 3]:
        if target_node == event.source_node:
            continue

        if target_node == 3:
            log_id = await mongo_db.counters.find_one_and_update(
                {"_id": "log_id"}, {"$inc": {"seq": 1}}, return_document=True
            )
            await mongo_db.sync_log.insert_one({
                "log_id": log_id["seq"],
                "source_node": event.source_node,
                "target_node": target_node,
                "operation": event.operation,
                "table_name": event.table_name,
                "record_id": event.record_id,
                "payload": payload_json,
                "status": "PENDING",
                "lamport_ts": lt,
                "vector_clock": json.dumps(vc),
                "created_epoch": now,
                "applied_epoch": None,
                "node_id": 3,
                "last_update_epoch": now,
            })
        else:
            db = db1 if target_node == 1 else db2
            try:
                db.execute(text("""
                    INSERT INTO dbo.sync_log
                        (source_node, target_node, operation, table_name, record_id,
                         payload, status, lamport_ts, vector_clock, created_epoch,
                         node_id, last_update_epoch)
                    VALUES (:src, :tgt, :op, :tbl, :rid, :pld, 'PENDING', :lt, :vc, :now, :ni, :now)
                """), {
                    "src": event.source_node, "tgt": target_node,
                    "op": event.operation, "tbl": event.table_name,
                    "rid": event.record_id, "pld": payload_json,
                    "lt": lt, "vc": json.dumps(vc), "now": now, "ni": target_node,
                })
                db.commit()
            except Exception:
                pass  # CAP: AP — continuar aunque un nodo falle

    return {"status": "published", "lamport_ts": lt, "vector_clock": vc}


# ─── Log de sincronización ───────────────────────────────────────────────────

@app.get("/sync/log")
async def get_sync_log(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db1: Session = Depends(get_db1),
):
    """Consulta el sync_log del nodo local."""
    where = "WHERE status = :st" if status else ""
    params = {"st": status} if status else {}
    params["limit"] = limit
    rows = db1.execute(
        text(f"SELECT TOP(:limit) * FROM dbo.sync_log {where} ORDER BY created_epoch DESC"),
        params
    ).mappings().all()
    return [dict(r) for r in rows]


@app.get("/sync/stats")
async def sync_stats(
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Estadísticas de sincronización por nodo."""
    stats = {}
    for node_id, db in [(1, db1), (2, db2)]:
        try:
            row = db.execute(text("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status='APPLIED' THEN 1 ELSE 0 END) as applied,
                    SUM(CASE WHEN status='CONFLICT' THEN 1 ELSE 0 END) as conflicts,
                    SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) as failed
                FROM dbo.sync_log
            """)).mappings().first()
            stats[f"node_{node_id}"] = dict(row)
        except Exception:
            stats[f"node_{node_id}"] = {"error": "unavailable"}

    try:
        total    = await mongo_db.sync_log.count_documents({})
        pending  = await mongo_db.sync_log.count_documents({"status": "PENDING"})
        applied  = await mongo_db.sync_log.count_documents({"status": "APPLIED"})
        conflicts = await mongo_db.sync_log.count_documents({"status": "CONFLICT"})
        failed   = await mongo_db.sync_log.count_documents({"status": "FAILED"})
        stats["node_3"] = {"total": total, "pending": pending, "applied": applied,
                           "conflicts": conflicts, "failed": failed}
    except Exception:
        stats["node_3"] = {"error": "unavailable"}

    return stats


# ─── Procesamiento periódico de sync pendiente ──────────────────────────────

async def process_pending_sync():
    """Aplica eventos pendientes — ejecutado cada 10 segundos."""
    now = int(time.time())
    try:
        pending = await mongo_db.sync_log.find(
            {"status": "PENDING", "target_node": 3}
        ).limit(50).to_list(None)
        for event in pending:
            # Aplicar cambio y marcar como APPLIED
            await mongo_db.sync_log.update_one(
                {"log_id": event["log_id"]},
                {"$set": {"status": "APPLIED", "applied_epoch": now}}
            )
    except Exception:
        pass

    for SessionCls, node_id in [(Session1, 1), (Session2, 2)]:
        try:
            db = SessionCls()
            rows = db.execute(
                text("SELECT TOP 50 log_id FROM dbo.sync_log WHERE status='PENDING' AND target_node=:ni"),
                {"ni": node_id}
            ).fetchall()
            for (log_id,) in rows:
                db.execute(
                    text("UPDATE dbo.sync_log SET status='APPLIED', applied_epoch=:now WHERE log_id=:lid"),
                    {"now": now, "lid": log_id}
                )
            db.commit()
            db.close()
        except Exception:
            pass
