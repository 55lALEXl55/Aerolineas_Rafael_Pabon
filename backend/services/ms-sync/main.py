"""
ms-sync — Puerto 8004
Sincronización distribuida: Lamport + Vector Clocks.
Propaga cambios entre los 3 nodos (DB1, DB2, DB3).
Detecta y resuelve conflictos según CLAUDE.md:
  Prioridad: causalidad > epoch > menor node_id.
CAP: AP — disponibilidad sobre consistencia fuerte.
"""
import asyncio
import json
import os
import sys
import time
from typing import List, Optional, Dict, Any

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

sys.path.insert(0, "/app/shared")
from lamport_clock import LamportClock
from vector_clock import VectorClock

from database import get_db1, get_db2, mongo_db, Session1, Session2
from models import (
    SyncEvent, PropagateRequest, ReceiveRequest, ScheduleRefundRequest,
    ClockState, NodeStatus,
)

app = FastAPI(
    title="ms-sync",
    description="Sincronización distribuida — Lamport + Vector Clocks",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NODE_ID    = int(os.getenv("NODE_ID", "1"))
NODE_INDEX = NODE_ID - 1

# URLs de los peers — en Docker cada ms-sync correría en su propio container,
# aquí modelamos los peers como los otros servicios del monorepo.
PEER_URLS = {
    1: os.getenv("NODE1_SYNC_URL", "http://ms-sync:8004"),
    2: os.getenv("NODE2_SYNC_URL", "http://ms-sync:8004"),
    3: os.getenv("NODE3_SYNC_URL", "http://ms-sync:8004"),
}
MS_BOOKINGS_URL = os.getenv("MS_BOOKINGS_URL", "http://ms-bookings:8002")
MS_FLIGHTS_URL  = os.getenv("MS_FLIGHTS_URL",  "http://ms-flights:8001")

lamport  = LamportClock()
vector   = VectorClock(node_index=NODE_INDEX)
scheduler = AsyncIOScheduler()

# Métricas en memoria para el dashboard
_latency_samples: List[float] = []   # últimas latencias medidas (segundos)
_conflict_count: int = 0
_resolved_count: int = 0
_event_log: List[dict] = []          # últimos 100 eventos en memoria


def _clock_tick() -> tuple[int, List[int]]:
    lt = lamport.tick()
    vc = vector.tick()
    return lt, vc


def _clock_update(recv_lt: int, recv_vc: List[int]) -> tuple[int, List[int]]:
    lt = lamport.update(recv_lt)
    vc = vector.merge(recv_vc)
    return lt, vc


def _record_event(event_type: str, source_node: int, payload: dict, latency_ms: float = 0):
    global _event_log
    _event_log.append({
        "ts": int(time.time()),
        "event_type": event_type,
        "source_node": source_node,
        "payload_summary": {k: v for k, v in payload.items() if k in ("seat_id", "flight_id", "status", "event_type")},
        "latency_ms": latency_ms,
        "lamport_ts": lamport.value,
        "vector_clock": vector.to_string(),
    })
    if len(_event_log) > 200:
        _event_log = _event_log[-100:]


# ─── Startup / Shutdown ───────────────────────────────────────────────────────

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
    lt, vc = _clock_tick()
    return {"lamport_ts": lt, "vector_clock": vc}


@app.post("/sync/clock/receive")
async def receive_clock(received_lamport: int, received_vector: List[int]):
    lt, vc = _clock_update(received_lamport, received_vector)
    return {"lamport_ts": lt, "vector_clock": vc}


# ─── POST /sync/propagate ────────────────────────────────────────────────────

@app.post("/sync/propagate")
async def propagate(req: PropagateRequest, db1: Session = Depends(get_db1), db2: Session = Depends(get_db2)):
    """
    Punto de entrada principal para propagación.
    Recibe evento de ms-bookings/ms-flights, actualiza relojes,
    registra en sync_log y envía a los nodos destino.
    """
    global _conflict_count, _resolved_count

    now = int(time.time())
    lt, vc = _clock_update(req.lamport_ts, req.vector_clock)
    vc_str = json.dumps(vc, separators=(",", ":"))

    # Detectar potencial conflicto: si el vector recibido indica concurrencia
    local_vc = vector.value
    is_concurrent = VectorClock.is_concurrent(req.vector_clock, local_vc)
    conflict_resolved = None

    if is_concurrent:
        _conflict_count += 1
        # Resolver con reglas de CLAUDE.md: causalidad > epoch > menor node_id
        winner = VectorClock.resolve_conflict(
            req.vector_clock, req.lamport_ts, req.source_node,
            local_vc, now, NODE_ID,
        )
        conflict_resolved = f"source_node_{req.source_node}" if winner == "a" else f"node_{NODE_ID}"
        _resolved_count += 1

    # Registrar en sync_log de todos los nodos destino
    target_nodes = [n for n in [1, 2, 3] if n != req.source_node]
    payload_json = json.dumps(req.payload)

    for target in target_nodes:
        await _log_sync_event(
            db1, db2,
            source_node=req.source_node,
            target_node=target,
            operation="UPDATE",
            table_name=_event_type_to_table(req.event_type),
            record_id=req.payload.get("seat_id", req.payload.get("flight_id", 0)),
            payload_json=payload_json,
            lt=lt, vc_str=vc_str, now=now,
            status="PENDING",
        )

    # Aplicar cambio a las BDs de los nodos destino (simulación multi-nodo en monorepo)
    for target in target_nodes:
        asyncio.create_task(_apply_to_node(
            target_node=target,
            event_type=req.event_type,
            payload=req.payload,
            lt=lt, vc_str=vc_str, now=now,
            db1=None, db2=None,  # se crean sesiones nuevas en el task
        ))

    _record_event(req.event_type, req.source_node, req.payload)

    return {
        "propagated": True,
        "source_node": req.source_node,
        "target_nodes": target_nodes,
        "lamport_ts": lt,
        "vector_clock": vc,
        "conflict_detected": is_concurrent,
        "conflict_resolved": conflict_resolved,
        "timestamp": now,
    }


# ─── POST /sync/receive ──────────────────────────────────────────────────────

@app.post("/sync/receive")
async def receive_event(req: ReceiveRequest, db1: Session = Depends(get_db1), db2: Session = Depends(get_db2)):
    """
    Recibe propagación de otro nodo peer.
    Mide latencia, detecta conflictos, aplica cambio local.
    """
    global _conflict_count, _resolved_count
    now = int(time.time())
    latency_ms = (now - req.sent_epoch) * 1000

    # Limitar muestras de latencia a últimos 60s
    _latency_samples.append(latency_ms)
    if len(_latency_samples) > 200:
        _latency_samples.pop(0)

    # Actualizar relojes
    lt, vc = _clock_update(req.lamport_ts, req.vector_clock)
    vc_str = json.dumps(vc, separators=(",", ":"))

    # Detectar conflicto
    local_vc = vector.value
    is_concurrent = VectorClock.is_concurrent(req.vector_clock, local_vc)
    conflict_resolved = None

    if is_concurrent:
        _conflict_count += 1
        winner = VectorClock.resolve_conflict(
            req.vector_clock, req.lamport_ts, req.source_node,
            local_vc, req.sent_epoch, NODE_ID,
        )
        conflict_resolved = f"node_{req.source_node}" if winner == "a" else f"node_{NODE_ID}"
        _resolved_count += 1
        # Si el nodo remoto gana, aplicar su cambio
        if winner == "b":
            # Nuestro estado gana — no aplicar
            return {
                "received": True,
                "conflict": True,
                "winner": f"node_{NODE_ID} (local)",
                "action": "skipped",
                "latency_ms": latency_ms,
                "lamport_ts": lt,
                "vector_clock": vc,
            }

    # Aplicar cambio a la BD local
    applied = await _apply_to_node(
        target_node=NODE_ID,
        event_type=req.event_type,
        payload=req.payload,
        lt=lt, vc_str=vc_str, now=now,
        db1=db1, db2=db2,
    )

    # Registrar en sync_log
    await _log_sync_event(
        db1, db2,
        source_node=req.source_node,
        target_node=NODE_ID,
        operation="UPDATE",
        table_name=_event_type_to_table(req.event_type),
        record_id=req.payload.get("seat_id", req.payload.get("flight_id", 0)),
        payload_json=json.dumps(req.payload),
        lt=lt, vc_str=vc_str, now=now,
        status="APPLIED" if applied else "FAILED",
    )

    _record_event(req.event_type, req.source_node, req.payload, latency_ms)

    return {
        "received": True,
        "conflict": is_concurrent,
        "winner": conflict_resolved,
        "applied": applied,
        "latency_ms": latency_ms,
        "lamport_ts": lt,
        "vector_clock": vc,
    }


# ─── POST /sync/events (API original, mantener compatibilidad) ───────────────

@app.post("/sync/events", status_code=201)
async def publish_event(
    event: SyncEvent,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Registra un evento en sync_log para propagación (API original)."""
    lt, vc = _clock_tick()
    now = int(time.time())
    vc_str = json.dumps(vc, separators=(",", ":"))
    payload_json = json.dumps(event.payload) if event.payload else None

    for target_node in [n for n in [1, 2, 3] if n != event.source_node]:
        await _log_sync_event(
            db1, db2,
            source_node=event.source_node,
            target_node=target_node,
            operation=event.operation,
            table_name=event.table_name,
            record_id=event.record_id,
            payload_json=payload_json,
            lt=lt, vc_str=vc_str, now=now,
            status="PENDING",
        )

    return {"status": "published", "lamport_ts": lt, "vector_clock": vc}


# ─── POST /sync/schedule-refund ──────────────────────────────────────────────

@app.post("/sync/schedule-refund")
async def schedule_refund(req: ScheduleRefundRequest):
    """
    Programa la liberación de un asiento REFUNDED → AVAILABLE
    después de delay_minutes minutos (consistencia eventual, CLAUDE.md: 15 min).
    """
    delay_seconds = req.delay_minutes * 60
    asyncio.create_task(_execute_refund_release(
        seat_id=req.seat_id,
        flight_id=req.flight_id,
        delay_seconds=delay_seconds,
    ))
    return {
        "scheduled": True,
        "seat_id": req.seat_id,
        "flight_id": req.flight_id,
        "delay_minutes": req.delay_minutes,
        "available_at_epoch": int(time.time()) + delay_seconds,
    }


async def _execute_refund_release(seat_id: int, flight_id: int, delay_seconds: int):
    """Ejecuta la liberación del asiento tras el delay."""
    await asyncio.sleep(delay_seconds)
    now = int(time.time())
    lt, vc = _clock_tick()
    vc_str = json.dumps(vc, separators=(",", ":"))

    node = _node_for(flight_id)
    if node == 3:
        await mongo_db.seats.update_one(
            {"seat_id": seat_id, "status": "REFUNDED"},
            {"$set": {"status": "AVAILABLE", "locked_until": None,
                      "lamport_ts": lt, "vector_clock": vc_str, "last_update_epoch": now}}
        )
    else:
        SessionCls = Session1 if node == 1 else Session2
        db = SessionCls()
        try:
            db.execute(text("""
                UPDATE dbo.seats SET status='AVAILABLE', locked_until=NULL,
                    lamport_ts=:lt, vector_clock=:vc, last_update_epoch=:now
                WHERE seat_id=:sid AND status='REFUNDED'
            """), {"lt": lt, "vc": vc_str, "now": now, "sid": seat_id})
            db.commit()
        except Exception:
            pass
        finally:
            db.close()

    _record_event("SEAT_AVAILABLE_REFUND", node, {"seat_id": seat_id, "flight_id": flight_id})


# ─── GET /sync/status ────────────────────────────────────────────────────────

@app.get("/sync/status")
async def sync_status():
    """
    Estado de los 3 nodos: salud de servicios, métricas de sync,
    conflictos detectados/resueltos, latencia promedio.
    """
    now = int(time.time())

    # Ping a cada servicio
    service_urls = {
        "ms-flights":  f"{MS_FLIGHTS_URL}/health",
        "ms-bookings": f"{MS_BOOKINGS_URL}/health",
        "ms-sync":     f"http://ms-sync:8004/health",
    }
    node_statuses = {}

    async def _ping(name: str, url: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(url)
                data = resp.json()
                return {
                    "name": name, "status": "OK",
                    "latency_ms": resp.elapsed.total_seconds() * 1000,
                    "node_id": data.get("node_id"),
                    "lamport_ts": data.get("lamport_ts", 0),
                    "vector_clock": data.get("vector_clock", "[0,0,0]"),
                    "last_seen": now,
                }
        except Exception:
            return {"name": name, "status": "DEGRADED", "last_seen": now, "latency_ms": -1}

    ping_tasks = [_ping(name, url) for name, url in service_urls.items()]
    ping_results = await asyncio.gather(*ping_tasks)
    for r in ping_results:
        node_statuses[r["name"]] = r

    # Métricas de latencia (últimos 60s en memoria)
    recent_latency = _latency_samples[-60:] if _latency_samples else []
    avg_latency = sum(recent_latency) / len(recent_latency) if recent_latency else 0

    # Stats del sync_log de DB1
    db1_stats = {}
    try:
        db = Session1()
        row = db.execute(text("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status='PENDING'  THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN status='APPLIED'  THEN 1 ELSE 0 END) AS applied,
                SUM(CASE WHEN status='CONFLICT' THEN 1 ELSE 0 END) AS conflicts,
                SUM(CASE WHEN status='FAILED'   THEN 1 ELSE 0 END) AS failed
            FROM dbo.sync_log
        """)).mappings().first()
        db1_stats = dict(row)
        db.close()
    except Exception:
        db1_stats = {"error": "unavailable"}

    # Último evento de cada nodo (de memoria)
    last_events: Dict[int, dict] = {}
    for ev in reversed(_event_log):
        node = ev.get("source_node")
        if node and node not in last_events:
            last_events[node] = ev

    return {
        "node_id": NODE_ID,
        "lamport_ts": lamport.value,
        "vector_clock": vector.to_string(),
        "timestamp": now,
        "services": node_statuses,
        "sync_stats": {
            "conflicts_detected": _conflict_count,
            "conflicts_resolved": _resolved_count,
            "avg_latency_ms": round(avg_latency, 2),
            "db1_log": db1_stats,
        },
        "last_events_by_node": last_events,
    }


# ─── GET /sync/log ────────────────────────────────────────────────────────────

@app.get("/sync/log")
async def get_sync_log(
    limit: int = Query(20, le=200),
    node_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db1: Session = Depends(get_db1),
):
    """Últimos N eventos del sync_log con vector clocks visibles."""
    conditions = []
    params: dict = {"limit": limit}

    if node_id:
        conditions.append("(source_node = :nid OR target_node = :nid)")
        params["nid"] = node_id
    if status:
        conditions.append("status = :st")
        params["st"] = status.upper()

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    try:
        rows = db1.execute(
            text(f"SELECT TOP(:limit) * FROM dbo.sync_log {where} ORDER BY created_epoch DESC"),
            params
        ).mappings().all()
        return {
            "logs": [dict(r) for r in rows],
            "local_lamport": lamport.value,
            "local_vector": vector.to_string(),
            "recent_events_memory": _event_log[-limit:],
        }
    except Exception as e:
        return {
            "logs": [],
            "local_lamport": lamport.value,
            "local_vector": vector.to_string(),
            "recent_events_memory": _event_log[-limit:],
            "error": str(e),
        }


# ─── GET /sync/stats ─────────────────────────────────────────────────────────

@app.get("/sync/stats")
async def sync_stats(
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Estadísticas de sincronización por nodo."""
    stats: dict = {}
    for node_id, db in [(1, db1), (2, db2)]:
        try:
            row = db.execute(text("""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status='PENDING'  THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN status='APPLIED'  THEN 1 ELSE 0 END) AS applied,
                    SUM(CASE WHEN status='CONFLICT' THEN 1 ELSE 0 END) AS conflicts,
                    SUM(CASE WHEN status='FAILED'   THEN 1 ELSE 0 END) AS failed
                FROM dbo.sync_log
            """)).mappings().first()
            stats[f"node_{node_id}"] = dict(row)
        except Exception:
            stats[f"node_{node_id}"] = {"error": "unavailable"}

    try:
        total     = await mongo_db.sync_log.count_documents({})
        pending   = await mongo_db.sync_log.count_documents({"status": "PENDING"})
        applied   = await mongo_db.sync_log.count_documents({"status": "APPLIED"})
        conflicts = await mongo_db.sync_log.count_documents({"status": "CONFLICT"})
        failed    = await mongo_db.sync_log.count_documents({"status": "FAILED"})
        stats["node_3"] = {
            "total": total, "pending": pending, "applied": applied,
            "conflicts": conflicts, "failed": failed,
        }
    except Exception:
        stats["node_3"] = {"error": "unavailable"}

    return stats


# ─── GET /sync/vector-state ──────────────────────────────────────────────────

@app.get("/sync/vector-state")
async def vector_state():
    """
    Estado del vector clock local y comparación con otros nodos.
    Si los relojes están alineados, los 3 nodos han procesado los mismos eventos.
    """
    now = int(time.time())
    local_vc = vector.value

    # Intentar obtener vector de otros servicios
    peer_states = {}
    for name, url in [("ms-flights", f"{MS_FLIGHTS_URL}/health"),
                      ("ms-bookings", f"{MS_BOOKINGS_URL}/health")]:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(url)
                data = resp.json()
                remote_vc_str = data.get("vector_clock", "[0,0,0]")
                remote_vc = json.loads(remote_vc_str)
                peer_states[name] = {
                    "vector_clock": remote_vc,
                    "lamport_ts": data.get("lamport_ts", 0),
                    "aligned_with_local": remote_vc == local_vc,
                    "relationship": _vc_relationship(local_vc, remote_vc),
                }
        except Exception:
            peer_states[name] = {"status": "unreachable"}

    return {
        "node_id": NODE_ID,
        "local_vector_clock": local_vc,
        "local_lamport": lamport.value,
        "timestamp": now,
        "peers": peer_states,
        "conflicts_total": _conflict_count,
        "conflicts_resolved": _resolved_count,
    }


def _vc_relationship(vc_a: List[int], vc_b: List[int]) -> str:
    """Describe la relación causal entre dos vector clocks."""
    try:
        if vc_a == vc_b:
            return "EQUAL"
        if VectorClock.happens_before(vc_a, vc_b):
            return "LOCAL_BEFORE_PEER"
        if VectorClock.happens_before(vc_b, vc_a):
            return "PEER_BEFORE_LOCAL"
        return "CONCURRENT"
    except Exception:
        return "UNKNOWN"


# ─── Scheduler: procesar sync pendiente ──────────────────────────────────────

async def process_pending_sync():
    """Aplica eventos PENDING del sync_log a sus nodos destino."""
    now = int(time.time())
    lt, vc = _clock_tick()
    vc_str = json.dumps(vc, separators=(",", ":"))

    # MongoDB: aplicar pendientes para node 3
    try:
        pending = await mongo_db.sync_log.find(
            {"status": "PENDING", "target_node": 3}
        ).limit(50).to_list(None)
        for event in pending:
            # Intentar aplicar el payload si tiene información de asiento
            payload = {}
            try:
                payload = json.loads(event.get("payload", "{}") or "{}")
            except Exception:
                pass

            if event.get("table_name") == "seats" and payload.get("seat_id"):
                await _apply_seat_update_mongo(payload, lt, vc_str, now)

            await mongo_db.sync_log.update_one(
                {"log_id": event["log_id"]},
                {"$set": {"status": "APPLIED", "applied_epoch": now}}
            )
    except Exception:
        pass

    # SQL Server: aplicar pendientes para nodes 1 y 2
    for SessionCls, node_id in [(Session1, 1), (Session2, 2)]:
        try:
            db = SessionCls()
            rows = db.execute(
                text("SELECT TOP 50 log_id, payload, table_name FROM dbo.sync_log WHERE status='PENDING' AND target_node=:ni"),
                {"ni": node_id}
            ).fetchall()
            for (log_id, payload_str, table_name) in rows:
                if table_name == "seats" and payload_str:
                    try:
                        payload = json.loads(payload_str)
                        if payload.get("seat_id") and payload.get("status"):
                            db.execute(text("""
                                UPDATE dbo.seats
                                SET status=:st, lamport_ts=:lt, vector_clock=:vc, last_update_epoch=:now
                                WHERE seat_id=:sid
                            """), {
                                "st": payload["status"], "lt": lt, "vc": vc_str,
                                "now": now, "sid": payload["seat_id"]
                            })
                    except Exception:
                        pass

                db.execute(
                    text("UPDATE dbo.sync_log SET status='APPLIED', applied_epoch=:now WHERE log_id=:lid"),
                    {"now": now, "lid": log_id}
                )
            db.commit()
            db.close()
        except Exception:
            pass


# ─── Utilidades internas ─────────────────────────────────────────────────────

def _node_for(flight_id: int) -> int:
    if flight_id < 100_000:
        return 1
    if flight_id < 500_000:
        return 2
    return 3


def _event_type_to_table(event_type: str) -> str:
    if "SEAT" in event_type:
        return "seats"
    if "FLIGHT" in event_type:
        return "flights"
    return "unknown"


def _event_type_to_status(event_type: str) -> Optional[str]:
    mapping = {
        "SEAT_LOCK":       "LOCKED",
        "SEAT_RESERVE":    "RESERVED",
        "SEAT_SELL":       "SOLD",
        "SEAT_AVAILABLE":  "AVAILABLE",
        "SEAT_REFUND":     "REFUNDED",
    }
    return mapping.get(event_type)


async def _log_sync_event(
    db1: Optional[Session], db2: Optional[Session],
    source_node: int, target_node: int,
    operation: str, table_name: str, record_id: int,
    payload_json: Optional[str], lt: int, vc_str: str, now: int,
    status: str = "PENDING",
):
    """Registra un evento en sync_log del nodo destino."""
    if target_node == 3:
        try:
            ctr = await mongo_db.counters.find_one_and_update(
                {"_id": "log_id"}, {"$inc": {"seq": 1}}, return_document=True
            )
            await mongo_db.sync_log.insert_one({
                "log_id": ctr["seq"] if ctr else int(time.time()),
                "source_node": source_node,
                "target_node": target_node,
                "operation": operation,
                "table_name": table_name,
                "record_id": record_id,
                "payload": payload_json,
                "status": status,
                "lamport_ts": lt,
                "vector_clock": vc_str,
                "created_epoch": now,
                "applied_epoch": now if status == "APPLIED" else None,
                "node_id": 3,
                "last_update_epoch": now,
            })
        except Exception:
            pass
    else:
        db = db1 if target_node == 1 else db2
        if not db:
            return
        try:
            db.execute(text("""
                INSERT INTO dbo.sync_log
                    (source_node, target_node, operation, table_name, record_id,
                     payload, status, lamport_ts, vector_clock, created_epoch, node_id, last_update_epoch)
                VALUES (:src, :tgt, :op, :tbl, :rid, :pld, :st, :lt, :vc, :now, :ni, :now)
            """), {
                "src": source_node, "tgt": target_node,
                "op": operation, "tbl": table_name,
                "rid": record_id, "pld": payload_json,
                "st": status, "lt": lt, "vc": vc_str, "now": now, "ni": target_node,
            })
            db.commit()
        except Exception:
            pass


async def _apply_to_node(
    target_node: int, event_type: str, payload: dict,
    lt: int, vc_str: str, now: int,
    db1: Optional[Session], db2: Optional[Session],
) -> bool:
    """
    Aplica el cambio del evento al nodo destino.
    Modela la replicación entre nodos del sistema distribuido.
    """
    new_status = _event_type_to_status(event_type)
    if not new_status:
        return True  # Evento sin cambio de estado directo

    seat_id = payload.get("seat_id")
    if not seat_id:
        return True

    if target_node == 3:
        return await _apply_seat_update_mongo(
            {"seat_id": seat_id, "status": new_status,
             "locked_until": payload.get("locked_until")},
            lt, vc_str, now
        )
    else:
        # Usar sesión nueva para no interferir con la sesión HTTP
        SessionCls = Session1 if target_node == 1 else Session2
        db = SessionCls()
        try:
            locked_until = payload.get("locked_until")
            db.execute(text("""
                UPDATE dbo.seats
                SET status=:st,
                    locked_until=:lu,
                    lamport_ts=:lt,
                    vector_clock=:vc,
                    last_update_epoch=:now
                WHERE seat_id=:sid
            """), {
                "st": new_status, "lu": locked_until,
                "lt": lt, "vc": vc_str, "now": now, "sid": seat_id,
            })
            db.commit()
            return True
        except Exception:
            return False
        finally:
            db.close()


async def _apply_seat_update_mongo(payload: dict, lt: int, vc_str: str, now: int) -> bool:
    """Aplica una actualización de asiento en MongoDB."""
    try:
        update: dict = {
            "lamport_ts": lt,
            "vector_clock": vc_str,
            "last_update_epoch": now,
        }
        if payload.get("status"):
            update["status"] = payload["status"]
        if "locked_until" in payload:
            update["locked_until"] = payload["locked_until"]

        await mongo_db.seats.update_one(
            {"seat_id": payload["seat_id"]},
            {"$set": update}
        )
        return True
    except Exception:
        return False
