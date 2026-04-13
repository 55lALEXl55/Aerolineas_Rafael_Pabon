"""
ms-bookings — Puerto 8002
Gestión de reservas: lock → reserve → purchase → refund.
Reglas CLAUDE.md:
  - LOCKED expira en 5 min
  - RESERVED expira en 24h (cron libera automáticamente)
  - REFUNDED tiene 15 min de delay de propagación (consistencia eventual)
CAP: AP — disponibilidad sobre consistencia fuerte.
"""
import asyncio
import json
import os
import sys
import time
from typing import Optional

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

sys.path.insert(0, "/app/shared")
from lamport_clock import LamportClock
from vector_clock import VectorClock

from database import get_db1, get_db2, mongo_db, Session1, Session2
from models import (
    LockRequest, ReserveRequest, PurchaseRequest,
    CancelRequest, RefundRequest,
    BookingCreate, BookingOut, SeatLockRequest, PaymentRequest,
)

app = FastAPI(
    title="ms-bookings",
    description="Microservicio de reservas — Aerolíneas Rafael Pabón",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NODE_ID = int(os.getenv("NODE_ID", "1"))
NODE_INDEX = NODE_ID - 1
MS_SYNC_URL = os.getenv("MS_SYNC_URL", "http://ms-sync:8004")

lamport = LamportClock()
vector  = VectorClock(node_index=NODE_INDEX)
scheduler = AsyncIOScheduler()

# Dict en memoria: seat_id → session_token (para verificar ownership del lock)
# CAP-friendly: en caso de reinicio se pierde, pero los LOCKED en BD expirarán por cron
_seat_locks: dict[int, str] = {}


# ─── Utilidades ──────────────────────────────────────────────────────────────

def _node_for(flight_id: int) -> int:
    if flight_id < 100_000:
        return 1
    if flight_id < 500_000:
        return 2
    return 3


def _clock_tick() -> tuple[int, str]:
    lt = lamport.tick()
    vc = json.dumps(vector.tick(), separators=(",", ":"))
    return lt, vc


async def _propagate(event_type: str, seat_id: int, flight_id: int, payload: dict):
    """Fire-and-forget: notificar ms-sync del cambio."""
    lt, vc = _clock_tick()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(f"{MS_SYNC_URL}/sync/events", json={
                "source_node": NODE_ID,
                "operation": "UPDATE",
                "table_name": "seats",
                "record_id": seat_id,
                "payload": {**payload, "event_type": event_type,
                            "flight_id": flight_id,
                            "lamport_ts": lt, "vector_clock": vc},
            })
    except Exception:
        pass


# ─── Scheduler startup / shutdown ────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    scheduler.add_job(expire_reservations,  "interval", minutes=5,  id="expire_job")
    scheduler.add_job(unlock_expired_seats,  "interval", minutes=1,  id="unlock_job")
    scheduler.start()


@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "service": "ms-bookings",
        "status": "ok",
        "node_id": NODE_ID,
        "lamport_ts": lamport.value,
        "vector_clock": vector.to_string(),
        "timestamp": int(time.time()),
    }


# ─── POST /bookings/lock ─────────────────────────────────────────────────────

@app.post("/bookings/lock")
async def lock_seat(
    req: LockRequest,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """
    Bloquea un asiento por 5 minutos (LOCKED).
    Propaga el estado a ms-sync.
    """
    now = int(time.time())
    locked_until = now + 300  # 5 min
    node = _node_for(req.flight_id)
    lt, vc = _clock_tick()

    if node == 3:
        seat = await mongo_db.seats.find_one({"seat_id": req.seat_id})
        if not seat:
            raise HTTPException(status_code=404, detail="Asiento no encontrado")
        if seat["status"] != "AVAILABLE":
            reason = "ALREADY_LOCKED" if seat["status"] == "LOCKED" else f"STATUS_{seat['status']}"
            return {"locked": False, "reason": reason, "current_status": seat["status"]}

        await mongo_db.seats.update_one(
            {"seat_id": req.seat_id},
            {"$set": {
                "status": "LOCKED",
                "locked_until": locked_until,
                "lamport_ts": lt,
                "vector_clock": vc,
                "last_update_epoch": now,
            }}
        )
    else:
        db = db1 if node == 1 else db2
        row = db.execute(
            text("SELECT status FROM dbo.seats WHERE seat_id = :sid"),
            {"sid": req.seat_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Asiento no encontrado")
        if row[0] != "AVAILABLE":
            reason = "ALREADY_LOCKED" if row[0] == "LOCKED" else f"STATUS_{row[0]}"
            return {"locked": False, "reason": reason, "current_status": row[0]}

        db.execute(text("""
            UPDATE dbo.seats
            SET status = 'LOCKED',
                locked_until = :lu,
                lamport_ts = :lt,
                vector_clock = :vc,
                last_update_epoch = :now
            WHERE seat_id = :sid
        """), {"lu": locked_until, "lt": lt, "vc": vc, "now": now, "sid": req.seat_id})
        db.commit()

    # Guardar en memoria para verificación posterior
    _seat_locks[req.seat_id] = req.session_token

    asyncio.create_task(_propagate("SEAT_LOCK", req.seat_id, req.flight_id, {
        "locked_until": locked_until, "session_token": req.session_token
    }))

    return {
        "locked": True,
        "seat_id": req.seat_id,
        "expires_epoch": locked_until,
        "lamport_ts": lt,
        "vector_clock": vc,
    }


# ─── POST /bookings/reserve ──────────────────────────────────────────────────

@app.post("/bookings/reserve")
async def reserve_seat(
    req: ReserveRequest,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """
    Reserva un asiento LOCKED (24h). Crea el pasajero si no existe.
    """
    now = int(time.time())
    reserved_until = now + 86_400  # 24 horas
    node = _node_for(req.flight_id)
    lt, vc = _clock_tick()

    # Verificar ownership del lock (in-memory)
    stored_token = _seat_locks.get(req.seat_id)
    if stored_token and stored_token != req.session_token:
        return {"reserved": False, "reason": "TOKEN_MISMATCH"}

    if node == 3:
        seat = await mongo_db.seats.find_one({"seat_id": req.seat_id})
        if not seat:
            raise HTTPException(status_code=404, detail="Asiento no encontrado")
        if seat["status"] not in ("LOCKED", "AVAILABLE"):
            raise HTTPException(status_code=409, detail={
                "error": "SEAT_NOT_LOCKABLE",
                "message": f"Asiento en estado {seat['status']}, no se puede reservar",
            })
        price = seat.get("price", 0)

        # Upsert pasajero
        existing = await mongo_db.passengers.find_one({"passport_number": req.passport})
        if existing:
            passenger_id = existing["passenger_id"]
        else:
            ctr = await mongo_db.counters.find_one_and_update(
                {"_id": "passenger_id"}, {"$inc": {"seq": 1}}, return_document=True
            )
            passenger_id = ctr["seq"]
            await mongo_db.passengers.insert_one({
                "passenger_id": passenger_id,
                "full_name": req.full_name,
                "email": req.email,
                "passport_number": req.passport,
                "phone": req.phone,
                "nationality": req.nationality,
                "node_id": 3, "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now,
            })

        ctr = await mongo_db.counters.find_one_and_update(
            {"_id": "ticket_id"}, {"$inc": {"seq": 1}}, return_document=True
        )
        ticket_id = ctr["seq"]
        await mongo_db.tickets.insert_one({
            "ticket_id": ticket_id,
            "passenger_id": passenger_id,
            "flight_id": req.flight_id,
            "seat_id": req.seat_id,
            "status": "RESERVED",
            "booking_epoch": now,
            "expiry_epoch": reserved_until,
            "payment_epoch": None,
            "total_price": price,
            "node_id": 3, "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now,
        })
        await mongo_db.seats.update_one(
            {"seat_id": req.seat_id},
            {"$set": {
                "status": "RESERVED",
                "locked_until": reserved_until,
                "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now,
            }}
        )
    else:
        db = db1 if node == 1 else db2
        seat_row = db.execute(
            text("SELECT status, price FROM dbo.seats WHERE seat_id = :sid"),
            {"sid": req.seat_id}
        ).fetchone()
        if not seat_row:
            raise HTTPException(status_code=404, detail="Asiento no encontrado")
        if seat_row[0] not in ("LOCKED", "AVAILABLE"):
            raise HTTPException(status_code=409, detail={
                "error": "SEAT_NOT_LOCKABLE",
                "message": f"Asiento en estado {seat_row[0]}, no se puede reservar",
            })
        price = float(seat_row[1])

        # Upsert pasajero
        existing = db.execute(
            text("SELECT passenger_id FROM dbo.passengers WHERE passport_number = :pp"),
            {"pp": req.passport}
        ).fetchone()
        if existing:
            passenger_id = existing[0]
        else:
            db.execute(text("""
                INSERT INTO dbo.passengers
                    (full_name, email, passport_number, phone, nationality,
                     node_id, lamport_ts, vector_clock, last_update_epoch)
                VALUES (:fn, :em, :pp, :ph, :na, :ni, :lt, :vc, :now)
            """), {
                "fn": req.full_name, "em": req.email, "pp": req.passport,
                "ph": req.phone, "na": req.nationality,
                "ni": node, "lt": lt, "vc": vc, "now": now,
            })
            db.flush()
            passenger_id = int(db.execute(text("SELECT @@IDENTITY")).scalar())

        db.execute(text("""
            INSERT INTO dbo.tickets
                (passenger_id, flight_id, seat_id, status,
                 booking_epoch, expiry_epoch, total_price,
                 node_id, lamport_ts, vector_clock, last_update_epoch)
            VALUES (:pid, :fid, :sid, 'RESERVED',
                    :now, :exp, :price,
                    :ni, :lt, :vc, :now)
        """), {
            "pid": passenger_id, "fid": req.flight_id, "sid": req.seat_id,
            "now": now, "exp": reserved_until, "price": price,
            "ni": node, "lt": lt, "vc": vc,
        })
        ticket_id = int(db.execute(text("SELECT @@IDENTITY")).scalar())

        db.execute(text("""
            UPDATE dbo.seats
            SET status = 'RESERVED',
                locked_until = :exp,
                lamport_ts = :lt,
                vector_clock = :vc,
                last_update_epoch = :now
            WHERE seat_id = :sid
        """), {"exp": reserved_until, "lt": lt, "vc": vc, "now": now, "sid": req.seat_id})
        db.commit()

    _seat_locks.pop(req.seat_id, None)

    asyncio.create_task(_propagate("SEAT_RESERVE", req.seat_id, req.flight_id, {
        "passenger": req.passport, "reserved_until": reserved_until
    }))

    return {
        "reserved": True,
        "ticket_id": ticket_id,
        "passenger_id": passenger_id,
        "seat_id": req.seat_id,
        "flight_id": req.flight_id,
        "status": "RESERVED",
        "reserved_until_epoch": reserved_until,
        "total_price": price,
        "lamport_ts": lt,
        "vector_clock": vc,
    }


# ─── POST /bookings/purchase ─────────────────────────────────────────────────

@app.post("/bookings/purchase")
async def purchase_seat(
    req: PurchaseRequest,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """
    Compra directa: LOCKED o RESERVED → SOLD.
    Crea o reutiliza el pasajero y genera el ticket.
    """
    now = int(time.time())
    node = _node_for(req.flight_id)
    lt, vc = _clock_tick()

    if node == 3:
        seat = await mongo_db.seats.find_one({"seat_id": req.seat_id})
        if not seat:
            raise HTTPException(status_code=404, detail="Asiento no encontrado")
        if seat["status"] not in ("LOCKED", "RESERVED", "AVAILABLE"):
            raise HTTPException(status_code=409, detail={
                "error": "SEAT_NOT_PURCHASABLE",
                "message": f"Asiento en estado {seat['status']}",
            })
        price = seat.get("price", 0)

        # Upsert pasajero
        existing = await mongo_db.passengers.find_one({"passport_number": req.passport})
        if existing:
            passenger_id = existing["passenger_id"]
        else:
            ctr = await mongo_db.counters.find_one_and_update(
                {"_id": "passenger_id"}, {"$inc": {"seq": 1}}, return_document=True
            )
            passenger_id = ctr["seq"]
            await mongo_db.passengers.insert_one({
                "passenger_id": passenger_id,
                "full_name": req.full_name, "email": req.email,
                "passport_number": req.passport,
                "phone": req.phone, "nationality": req.nationality,
                "node_id": 3, "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now,
            })

        # Verificar si hay ticket RESERVED existente
        existing_ticket = await mongo_db.tickets.find_one({
            "seat_id": req.seat_id,
            "passenger_id": passenger_id,
            "status": "RESERVED",
        })
        if existing_ticket:
            ticket_id = existing_ticket["ticket_id"]
            await mongo_db.tickets.update_one(
                {"ticket_id": ticket_id},
                {"$set": {"status": "PAID", "payment_epoch": now, "lamport_ts": lt, "vector_clock": vc}}
            )
        else:
            ctr = await mongo_db.counters.find_one_and_update(
                {"_id": "ticket_id"}, {"$inc": {"seq": 1}}, return_document=True
            )
            ticket_id = ctr["seq"]
            await mongo_db.tickets.insert_one({
                "ticket_id": ticket_id, "passenger_id": passenger_id,
                "flight_id": req.flight_id, "seat_id": req.seat_id,
                "status": "PAID", "booking_epoch": now,
                "expiry_epoch": now + 86_400, "payment_epoch": now,
                "total_price": price,
                "node_id": 3, "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now,
            })

        await mongo_db.seats.update_one(
            {"seat_id": req.seat_id},
            {"$set": {
                "status": "SOLD",
                "locked_until": None,
                "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now,
            }}
        )
    else:
        db = db1 if node == 1 else db2
        seat_row = db.execute(
            text("SELECT status, price FROM dbo.seats WHERE seat_id = :sid"),
            {"sid": req.seat_id}
        ).fetchone()
        if not seat_row:
            raise HTTPException(status_code=404, detail="Asiento no encontrado")
        if seat_row[0] not in ("LOCKED", "RESERVED", "AVAILABLE"):
            raise HTTPException(status_code=409, detail={
                "error": "SEAT_NOT_PURCHASABLE",
                "message": f"Asiento en estado {seat_row[0]}",
            })
        price = float(seat_row[1])

        # Upsert pasajero
        existing = db.execute(
            text("SELECT passenger_id FROM dbo.passengers WHERE passport_number = :pp"),
            {"pp": req.passport}
        ).fetchone()
        if existing:
            passenger_id = existing[0]
        else:
            db.execute(text("""
                INSERT INTO dbo.passengers
                    (full_name, email, passport_number, phone, nationality,
                     node_id, lamport_ts, vector_clock, last_update_epoch)
                VALUES (:fn, :em, :pp, :ph, :na, :ni, :lt, :vc, :now)
            """), {
                "fn": req.full_name, "em": req.email, "pp": req.passport,
                "ph": req.phone, "na": req.nationality,
                "ni": node, "lt": lt, "vc": vc, "now": now,
            })
            db.flush()
            passenger_id = int(db.execute(text("SELECT @@IDENTITY")).scalar())

        # ¿Hay ticket RESERVED para convertir?
        existing_ticket = db.execute(
            text("""SELECT ticket_id FROM dbo.tickets
                    WHERE seat_id = :sid AND passenger_id = :pid AND status = 'RESERVED'"""),
            {"sid": req.seat_id, "pid": passenger_id}
        ).fetchone()

        if existing_ticket:
            ticket_id = existing_ticket[0]
            db.execute(text("""
                UPDATE dbo.tickets
                SET status = 'PAID', payment_epoch = :now, lamport_ts = :lt, vector_clock = :vc
                WHERE ticket_id = :tid
            """), {"now": now, "lt": lt, "vc": vc, "tid": ticket_id})
        else:
            db.execute(text("""
                INSERT INTO dbo.tickets
                    (passenger_id, flight_id, seat_id, status,
                     booking_epoch, expiry_epoch, payment_epoch, total_price,
                     node_id, lamport_ts, vector_clock, last_update_epoch)
                VALUES (:pid, :fid, :sid, 'PAID',
                        :now, :exp, :now, :price,
                        :ni, :lt, :vc, :now)
            """), {
                "pid": passenger_id, "fid": req.flight_id, "sid": req.seat_id,
                "now": now, "exp": now + 86_400, "price": price,
                "ni": node, "lt": lt, "vc": vc,
            })
            ticket_id = int(db.execute(text("SELECT @@IDENTITY")).scalar())

        db.execute(text("""
            UPDATE dbo.seats
            SET status = 'SOLD',
                locked_until = NULL,
                lamport_ts = :lt,
                vector_clock = :vc,
                last_update_epoch = :now
            WHERE seat_id = :sid
        """), {"lt": lt, "vc": vc, "now": now, "sid": req.seat_id})
        db.commit()

    _seat_locks.pop(req.seat_id, None)

    asyncio.create_task(_propagate("SEAT_SELL", req.seat_id, req.flight_id, {
        "ticket_id": ticket_id, "passenger": req.passport
    }))

    return {
        "purchased": True,
        "ticket_id": ticket_id,
        "passenger_id": passenger_id,
        "seat_id": req.seat_id,
        "flight_id": req.flight_id,
        "status": "SOLD",
        "total_price": price,
        "lamport_ts": lt,
        "vector_clock": vc,
    }


# ─── POST /bookings/cancel-reservation ───────────────────────────────────────

@app.post("/bookings/cancel-reservation")
async def cancel_reservation(
    req: CancelRequest,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Cancela una reserva RESERVED. El pasajero debe ser el dueño del ticket."""
    now = int(time.time())
    node = _node_for(req.flight_id)
    lt, vc = _clock_tick()

    if node == 3:
        pax = await mongo_db.passengers.find_one({"passport_number": req.passport})
        if not pax:
            raise HTTPException(status_code=404, detail="Pasajero no encontrado")

        ticket = await mongo_db.tickets.find_one({
            "seat_id": req.seat_id,
            "passenger_id": pax["passenger_id"],
            "status": "RESERVED",
        })
        if not ticket:
            raise HTTPException(status_code=404, detail={
                "error": "TICKET_NOT_FOUND",
                "message": "No existe reserva activa para este pasajero en este asiento",
            })

        await mongo_db.tickets.update_one(
            {"ticket_id": ticket["ticket_id"]},
            {"$set": {"status": "EXPIRED", "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now}}
        )
        await mongo_db.seats.update_one(
            {"seat_id": req.seat_id},
            {"$set": {
                "status": "AVAILABLE",
                "locked_until": None,
                "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now,
            }}
        )
        ticket_id = ticket["ticket_id"]
    else:
        db = db1 if node == 1 else db2
        pax_row = db.execute(
            text("SELECT passenger_id FROM dbo.passengers WHERE passport_number = :pp"),
            {"pp": req.passport}
        ).fetchone()
        if not pax_row:
            raise HTTPException(status_code=404, detail="Pasajero no encontrado")

        ticket_row = db.execute(
            text("""
                SELECT ticket_id FROM dbo.tickets
                WHERE seat_id = :sid AND passenger_id = :pid AND status = 'RESERVED'
            """),
            {"sid": req.seat_id, "pid": pax_row[0]}
        ).fetchone()
        if not ticket_row:
            raise HTTPException(status_code=404, detail={
                "error": "TICKET_NOT_FOUND",
                "message": "No existe reserva activa para este pasajero en este asiento",
            })

        db.execute(text("""
            UPDATE dbo.tickets
            SET status = 'EXPIRED', lamport_ts = :lt, vector_clock = :vc, last_update_epoch = :now
            WHERE ticket_id = :tid
        """), {"lt": lt, "vc": vc, "now": now, "tid": ticket_row[0]})
        db.execute(text("""
            UPDATE dbo.seats
            SET status = 'AVAILABLE',
                locked_until = NULL,
                lamport_ts = :lt,
                vector_clock = :vc,
                last_update_epoch = :now
            WHERE seat_id = :sid
        """), {"lt": lt, "vc": vc, "now": now, "sid": req.seat_id})
        db.commit()
        ticket_id = ticket_row[0]

    asyncio.create_task(_propagate("SEAT_AVAILABLE", req.seat_id, req.flight_id, {
        "reason": "CANCEL_RESERVATION", "ticket_id": ticket_id
    }))

    return {
        "cancelled": True,
        "ticket_id": ticket_id,
        "seat_id": req.seat_id,
        "status": "AVAILABLE",
        "lamport_ts": lt,
    }


# ─── POST /bookings/refund ────────────────────────────────────────────────────

@app.post("/bookings/refund")
async def refund_seat(
    req: RefundRequest,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """
    Reembolso de asiento SOLD. Estado local: REFUNDED inmediato.
    La propagación a AVAILABLE tiene 15 min de delay (consistencia eventual).
    """
    now = int(time.time())
    node = _node_for(req.flight_id)
    lt, vc = _clock_tick()

    if node == 3:
        pax = await mongo_db.passengers.find_one({"passport_number": req.passport})
        if not pax:
            raise HTTPException(status_code=404, detail="Pasajero no encontrado")

        ticket = await mongo_db.tickets.find_one({
            "seat_id": req.seat_id,
            "passenger_id": pax["passenger_id"],
            "status": "PAID",
        })
        if not ticket:
            raise HTTPException(status_code=404, detail={
                "error": "TICKET_NOT_FOUND",
                "message": "No existe compra activa para este pasajero en este asiento",
            })

        await mongo_db.tickets.update_one(
            {"ticket_id": ticket["ticket_id"]},
            {"$set": {"status": "REFUNDED", "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now}}
        )
        await mongo_db.seats.update_one(
            {"seat_id": req.seat_id},
            {"$set": {
                "status": "REFUNDED",
                "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now,
            }}
        )
        ticket_id = ticket["ticket_id"]
    else:
        db = db1 if node == 1 else db2
        pax_row = db.execute(
            text("SELECT passenger_id FROM dbo.passengers WHERE passport_number = :pp"),
            {"pp": req.passport}
        ).fetchone()
        if not pax_row:
            raise HTTPException(status_code=404, detail="Pasajero no encontrado")

        ticket_row = db.execute(
            text("""
                SELECT ticket_id FROM dbo.tickets
                WHERE seat_id = :sid AND passenger_id = :pid AND status = 'PAID'
            """),
            {"sid": req.seat_id, "pid": pax_row[0]}
        ).fetchone()
        if not ticket_row:
            raise HTTPException(status_code=404, detail={
                "error": "TICKET_NOT_FOUND",
                "message": "No existe compra activa para este pasajero en este asiento",
            })

        db.execute(text("""
            UPDATE dbo.tickets
            SET status = 'REFUNDED', lamport_ts = :lt, vector_clock = :vc, last_update_epoch = :now
            WHERE ticket_id = :tid
        """), {"lt": lt, "vc": vc, "now": now, "tid": ticket_row[0]})
        db.execute(text("""
            UPDATE dbo.seats
            SET status = 'REFUNDED',
                lamport_ts = :lt,
                vector_clock = :vc,
                last_update_epoch = :now
            WHERE seat_id = :sid
        """), {"lt": lt, "vc": vc, "now": now, "sid": req.seat_id})
        db.commit()
        ticket_id = ticket_row[0]

    # Programar liberación del asiento con 15 min de delay (consistencia eventual)
    asyncio.create_task(_delayed_release(
        seat_id=req.seat_id,
        flight_id=req.flight_id,
        delay_seconds=900,  # 15 minutos
    ))

    return {
        "refunded": True,
        "ticket_id": ticket_id,
        "seat_id": req.seat_id,
        "status": "REFUNDED",
        "available_in_minutes": 15,
        "lamport_ts": lt,
    }


async def _delayed_release(seat_id: int, flight_id: int, delay_seconds: int):
    """Libera el asiento a AVAILABLE después del delay (modelo AP de 15 min)."""
    await asyncio.sleep(delay_seconds)
    now = int(time.time())
    lt, vc = _clock_tick()
    node = _node_for(flight_id)

    if node == 3:
        await mongo_db.seats.update_one(
            {"seat_id": seat_id, "status": "REFUNDED"},
            {"$set": {
                "status": "AVAILABLE",
                "locked_until": None,
                "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now,
            }}
        )
    else:
        SessionCls = Session1 if node == 1 else Session2
        db = SessionCls()
        try:
            db.execute(text("""
                UPDATE dbo.seats
                SET status = 'AVAILABLE',
                    locked_until = NULL,
                    lamport_ts = :lt,
                    vector_clock = :vc,
                    last_update_epoch = :now
                WHERE seat_id = :sid AND status = 'REFUNDED'
            """), {"lt": lt, "vc": vc, "now": now, "sid": seat_id})
            db.commit()
        except Exception:
            pass
        finally:
            db.close()

    await _propagate("SEAT_AVAILABLE", seat_id, flight_id, {"reason": "REFUND_COMPLETED"})


# ─── GET /bookings/passenger/{passport} ──────────────────────────────────────

@app.get("/bookings/passenger/{passport}")
async def get_passenger(
    passport: str,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Busca un pasajero por pasaporte (CAP: AP, busca en los nodos disponibles)."""
    # Buscar en DB1
    try:
        row = db1.execute(
            text("SELECT passenger_id, full_name, email, passport_number, phone, nationality FROM dbo.passengers WHERE passport_number = :pp"),
            {"pp": passport}
        ).fetchone()
        if row:
            return {
                "found": True,
                "passenger_id": row[0],
                "full_name": row[1],
                "email": row[2],
                "passport_number": row[3],
                "phone": row[4],
                "nationality": row[5],
                "node": 1,
            }
    except Exception:
        pass

    # Buscar en DB2
    try:
        row = db2.execute(
            text("SELECT passenger_id, full_name, email, passport_number, phone, nationality FROM dbo.passengers WHERE passport_number = :pp"),
            {"pp": passport}
        ).fetchone()
        if row:
            return {
                "found": True,
                "passenger_id": row[0],
                "full_name": row[1],
                "email": row[2],
                "passport_number": row[3],
                "phone": row[4],
                "nationality": row[5],
                "node": 2,
            }
    except Exception:
        pass

    # Buscar en DB3 (MongoDB)
    try:
        pax = await mongo_db.passengers.find_one({"passport_number": passport}, {"_id": 0})
        if pax:
            return {"found": True, **pax, "node": 3}
    except Exception:
        pass

    return {"found": False}


# ─── GET /bookings/ticket/{ticket_id} ────────────────────────────────────────

@app.get("/bookings/ticket/{ticket_id}")
async def get_ticket(
    ticket_id: int,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Retorna datos completos del ticket para el boarding pass / PDF."""
    if ticket_id >= 500_000:
        # MongoDB
        ticket = await mongo_db.tickets.find_one({"ticket_id": ticket_id}, {"_id": 0})
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        pax = await mongo_db.passengers.find_one(
            {"passenger_id": ticket["passenger_id"]}, {"_id": 0}
        )
        flight = await mongo_db.flights.find_one(
            {"flight_id": ticket["flight_id"]}, {"_id": 0}
        )
        seat = await mongo_db.seats.find_one(
            {"seat_id": ticket["seat_id"]}, {"_id": 0}
        )
        return {
            "ticket": ticket,
            "passenger": pax,
            "flight": flight,
            "seat": seat,
        }

    # SQL Server: buscar en ambas BDs
    sql_ticket = text("""
        SELECT t.*, p.full_name, p.email, p.passport_number, p.phone, p.nationality,
               s.seat_number, s.seat_class, s.price,
               f.flight_number, f.origin, f.destination,
               f.departure_epoch, f.arrival_epoch
        FROM dbo.tickets t
        JOIN dbo.passengers p ON p.passenger_id = t.passenger_id
        JOIN dbo.seats s ON s.seat_id = t.seat_id
        JOIN dbo.flights f ON f.flight_id = t.flight_id
        WHERE t.ticket_id = :tid
    """)

    for db in [db1, db2]:
        try:
            row = db.execute(sql_ticket, {"tid": ticket_id}).mappings().first()
            if row:
                data = dict(row)
                # Limpiar NCHAR trailing spaces
                for k in ("origin", "destination"):
                    if isinstance(data.get(k), str):
                        data[k] = data[k].strip()
                return {
                    "ticket": {
                        "ticket_id": data["ticket_id"],
                        "passenger_id": data["passenger_id"],
                        "flight_id": data["flight_id"],
                        "seat_id": data["seat_id"],
                        "status": data["status"],
                        "booking_epoch": data["booking_epoch"],
                        "expiry_epoch": data["expiry_epoch"],
                        "payment_epoch": data.get("payment_epoch"),
                        "total_price": float(data["total_price"]),
                        "node_id": data["node_id"],
                        "lamport_ts": data["lamport_ts"],
                        "vector_clock": data["vector_clock"],
                    },
                    "passenger": {
                        "full_name": data["full_name"],
                        "email": data["email"],
                        "passport_number": data["passport_number"],
                        "phone": data.get("phone"),
                        "nationality": data.get("nationality"),
                    },
                    "flight": {
                        "flight_number": data["flight_number"],
                        "origin": data["origin"],
                        "destination": data["destination"],
                        "departure_epoch": data["departure_epoch"],
                        "arrival_epoch": data["arrival_epoch"],
                    },
                    "seat": {
                        "seat_number": data["seat_number"],
                        "seat_class": data["seat_class"],
                        "price": float(data["price"]),
                    },
                }
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="Ticket no encontrado")


# ─── POST /bookings/cancel-ticket ────────────────────────────────────────────

@app.post("/bookings/cancel-ticket")
async def cancel_ticket_by_id(
    ticket_id: int = Body(..., embed=True),
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Cancela una reserva RESERVED dado solo el ticket_id (usado por el frontend)."""
    now = int(time.time())
    lt, vc = _clock_tick()

    if ticket_id >= 500_000:
        ticket = await mongo_db.tickets.find_one({"ticket_id": ticket_id})
        if not ticket or ticket.get("status") != "RESERVED":
            raise HTTPException(status_code=404, detail={
                "error": "TICKET_NOT_FOUND",
                "message": "Ticket no encontrado o no está en estado RESERVED",
            })
        seat_id = ticket["seat_id"]
        flight_id = ticket["flight_id"]
        await mongo_db.tickets.update_one(
            {"ticket_id": ticket_id},
            {"$set": {"status": "EXPIRED", "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now}}
        )
        await mongo_db.seats.update_one(
            {"seat_id": seat_id},
            {"$set": {"status": "AVAILABLE", "locked_until": None,
                      "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now}}
        )
        asyncio.create_task(_propagate("SEAT_AVAILABLE", seat_id, flight_id,
                                       {"reason": "CANCEL_TICKET", "ticket_id": ticket_id}))
        return {"cancelled": True, "ticket_id": ticket_id, "seat_id": seat_id,
                "status": "AVAILABLE", "lamport_ts": lt}

    for db in [db1, db2]:
        try:
            row = db.execute(
                text("SELECT ticket_id, seat_id, flight_id, status FROM dbo.tickets WHERE ticket_id = :tid"),
                {"tid": ticket_id}
            ).mappings().first()
            if row and row["status"] == "RESERVED":
                seat_id, flight_id = row["seat_id"], row["flight_id"]
                db.execute(text("""
                    UPDATE dbo.tickets SET status = 'EXPIRED',
                    lamport_ts = :lt, vector_clock = :vc, last_update_epoch = :now
                    WHERE ticket_id = :tid
                """), {"lt": lt, "vc": vc, "now": now, "tid": ticket_id})
                db.execute(text("""
                    UPDATE dbo.seats SET status = 'AVAILABLE', locked_until = NULL,
                    lamport_ts = :lt, vector_clock = :vc, last_update_epoch = :now
                    WHERE seat_id = :sid
                """), {"lt": lt, "vc": vc, "now": now, "sid": seat_id})
                db.commit()
                asyncio.create_task(_propagate("SEAT_AVAILABLE", seat_id, flight_id,
                                               {"reason": "CANCEL_TICKET", "ticket_id": ticket_id}))
                return {"cancelled": True, "ticket_id": ticket_id, "seat_id": seat_id,
                        "status": "AVAILABLE", "lamport_ts": lt}
        except Exception:
            pass

    raise HTTPException(status_code=404, detail={
        "error": "TICKET_NOT_FOUND",
        "message": "Ticket no encontrado o no está en estado RESERVED",
    })


# ─── POST /bookings/refund-ticket ─────────────────────────────────────────────

@app.post("/bookings/refund-ticket")
async def refund_ticket_by_id(
    ticket_id: int = Body(..., embed=True),
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Reembolsa un ticket PAID dado solo el ticket_id. Delay 15 min para propagación."""
    now = int(time.time())
    lt, vc = _clock_tick()
    refund_at = now + 900  # 15 min de delay (CLAUDE.md)

    if ticket_id >= 500_000:
        ticket = await mongo_db.tickets.find_one({"ticket_id": ticket_id})
        if not ticket or ticket.get("status") != "PAID":
            raise HTTPException(status_code=404, detail={
                "error": "TICKET_NOT_FOUND",
                "message": "Ticket no encontrado o no está en estado PAID",
            })
        seat_id = ticket["seat_id"]
        flight_id = ticket["flight_id"]
        await mongo_db.tickets.update_one(
            {"ticket_id": ticket_id},
            {"$set": {"status": "REFUNDED", "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now}}
        )
        await mongo_db.seats.update_one(
            {"seat_id": seat_id},
            {"$set": {"status": "REFUNDED", "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now}}
        )
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(f"{MS_SYNC_URL}/sync/schedule-refund",
                                  json={"seat_id": seat_id, "flight_id": flight_id,
                                        "available_at_epoch": refund_at})
        except Exception:
            pass
        return {"refunded": True, "ticket_id": ticket_id, "seat_id": seat_id,
                "status": "REFUNDED", "available_at_epoch": refund_at, "lamport_ts": lt}

    for db in [db1, db2]:
        try:
            row = db.execute(
                text("SELECT ticket_id, seat_id, flight_id, status FROM dbo.tickets WHERE ticket_id = :tid"),
                {"tid": ticket_id}
            ).mappings().first()
            if row and row["status"] == "PAID":
                seat_id, flight_id = row["seat_id"], row["flight_id"]
                db.execute(text("""
                    UPDATE dbo.tickets SET status = 'REFUNDED',
                    lamport_ts = :lt, vector_clock = :vc, last_update_epoch = :now
                    WHERE ticket_id = :tid
                """), {"lt": lt, "vc": vc, "now": now, "tid": ticket_id})
                db.execute(text("""
                    UPDATE dbo.seats SET status = 'REFUNDED',
                    lamport_ts = :lt, vector_clock = :vc, last_update_epoch = :now
                    WHERE seat_id = :sid
                """), {"lt": lt, "vc": vc, "now": now, "sid": seat_id})
                db.commit()
                try:
                    async with httpx.AsyncClient(timeout=2.0) as client:
                        await client.post(f"{MS_SYNC_URL}/sync/schedule-refund",
                                          json={"seat_id": seat_id, "flight_id": flight_id,
                                                "available_at_epoch": refund_at})
                except Exception:
                    pass
                return {"refunded": True, "ticket_id": ticket_id, "seat_id": seat_id,
                        "status": "REFUNDED", "available_at_epoch": refund_at, "lamport_ts": lt}
        except Exception:
            pass

    raise HTTPException(status_code=404, detail={
        "error": "TICKET_NOT_FOUND",
        "message": "Ticket no encontrado o no está en estado PAID",
    })


# ─── APScheduler: expirar reservas (cada 5 min) ──────────────────────────────

async def expire_reservations():
    """Busca RESERVED con expiry_epoch < now y los libera."""
    now = int(time.time())
    lt, vc = _clock_tick()

    for SessionCls in [Session1, Session2]:
        try:
            db = SessionCls()
            rows = db.execute(
                text("""
                    SELECT t.ticket_id, t.seat_id
                    FROM dbo.tickets t
                    WHERE t.status = 'RESERVED' AND t.expiry_epoch < :now
                """),
                {"now": now}
            ).fetchall()
            for (tid, sid) in rows:
                db.execute(
                    text("UPDATE dbo.tickets SET status = 'EXPIRED', last_update_epoch = :now WHERE ticket_id = :tid"),
                    {"now": now, "tid": tid}
                )
                db.execute(
                    text("""UPDATE dbo.seats
                            SET status = 'AVAILABLE', locked_until = NULL,
                                lamport_ts = :lt, vector_clock = :vc, last_update_epoch = :now
                            WHERE seat_id = :sid"""),
                    {"lt": lt, "vc": vc, "now": now, "sid": sid}
                )
            db.commit()
            db.close()
        except Exception:
            pass

    try:
        expired = await mongo_db.tickets.find(
            {"status": "RESERVED", "expiry_epoch": {"$lt": now}}
        ).to_list(None)
        for t in expired:
            await mongo_db.tickets.update_one(
                {"ticket_id": t["ticket_id"]},
                {"$set": {"status": "EXPIRED", "last_update_epoch": now}}
            )
            await mongo_db.seats.update_one(
                {"seat_id": t["seat_id"]},
                {"$set": {
                    "status": "AVAILABLE", "locked_until": None,
                    "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now,
                }}
            )
    except Exception:
        pass


# ─── APScheduler: desbloquear asientos (cada 1 min) ─────────────────────────

async def unlock_expired_seats():
    """Libera asientos LOCKED con locked_until < now."""
    now = int(time.time())
    lt, vc = _clock_tick()

    for SessionCls in [Session1, Session2]:
        try:
            db = SessionCls()
            rows = db.execute(
                text("""
                    SELECT seat_id FROM dbo.seats
                    WHERE status = 'LOCKED' AND locked_until < :now
                """),
                {"now": now}
            ).fetchall()
            for (sid,) in rows:
                db.execute(
                    text("""UPDATE dbo.seats
                            SET status = 'AVAILABLE', locked_until = NULL,
                                lamport_ts = :lt, vector_clock = :vc, last_update_epoch = :now
                            WHERE seat_id = :sid"""),
                    {"lt": lt, "vc": vc, "now": now, "sid": sid}
                )
                _seat_locks.pop(sid, None)
            db.commit()
            db.close()
        except Exception:
            pass

    try:
        async for seat in mongo_db.seats.find(
            {"status": "LOCKED", "locked_until": {"$lt": now}},
            {"seat_id": 1}
        ):
            await mongo_db.seats.update_one(
                {"seat_id": seat["seat_id"]},
                {"$set": {
                    "status": "AVAILABLE", "locked_until": None,
                    "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now,
                }}
            )
            _seat_locks.pop(seat["seat_id"], None)
    except Exception:
        pass


# ─── API antigua (compatibilidad) ────────────────────────────────────────────

@app.post("/seats/lock")
async def lock_seat_legacy(
    req: SeatLockRequest,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Compatibilidad con frontend anterior."""
    return await lock_seat(
        LockRequest(seat_id=req.seat_id, flight_id=req.flight_id, session_token="legacy"),
        db1, db2
    )


@app.post("/bookings", response_model=BookingOut, status_code=201)
async def create_booking_legacy(
    req: BookingCreate,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Compatibilidad con frontend anterior."""
    result = await reserve_seat(
        ReserveRequest(
            seat_id=req.seat_id,
            flight_id=req.flight_id,
            session_token="legacy",
            passport=req.passenger.passport_number,
            full_name=req.passenger.full_name,
            email=req.passenger.email,
            phone=req.passenger.phone,
            nationality=req.passenger.nationality,
        ),
        db1, db2
    )
    return BookingOut(
        ticket_id=result["ticket_id"],
        passenger_id=result["passenger_id"],
        flight_id=result["flight_id"],
        seat_id=result["seat_id"],
        status=result["status"],
        booking_epoch=int(time.time()),
        expiry_epoch=result["reserved_until_epoch"],
        total_price=result["total_price"],
        node_id=NODE_ID,
        vector_clock=result["vector_clock"],
        lamport_ts=result["lamport_ts"],
    )


@app.post("/bookings/{ticket_id}/pay")
async def pay_booking_legacy(
    ticket_id: int,
    req: PaymentRequest,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Compatibilidad con frontend anterior — actualiza ticket RESERVED a PAID."""
    now = int(time.time())
    lt, vc = _clock_tick()

    if ticket_id >= 500_000:
        ticket = await mongo_db.tickets.find_one({"ticket_id": ticket_id})
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        if ticket["status"] not in ("RESERVED",):
            raise HTTPException(status_code=409, detail=f"Ticket en estado {ticket['status']}")
        if now > ticket["expiry_epoch"]:
            raise HTTPException(status_code=410, detail="Ticket expirado")
        await mongo_db.tickets.update_one(
            {"ticket_id": ticket_id},
            {"$set": {"status": "PAID", "payment_epoch": now, "lamport_ts": lt, "vector_clock": vc}}
        )
        await mongo_db.seats.update_one(
            {"seat_id": ticket["seat_id"]},
            {"$set": {"status": "SOLD", "locked_until": None, "lamport_ts": lt, "vector_clock": vc, "last_update_epoch": now}}
        )
        return {"ticket_id": ticket_id, "status": "PAID", "payment_epoch": now}

    for db in [db1, db2]:
        try:
            row = db.execute(
                text("SELECT status, seat_id, expiry_epoch FROM dbo.tickets WHERE ticket_id = :tid"),
                {"tid": ticket_id}
            ).fetchone()
            if not row:
                continue
            if row[0] not in ("RESERVED",):
                raise HTTPException(status_code=409, detail=f"Ticket en estado {row[0]}")
            if now > row[2]:
                raise HTTPException(status_code=410, detail="Ticket expirado")
            db.execute(
                text("UPDATE dbo.tickets SET status='PAID', payment_epoch=:now, lamport_ts=:lt, vector_clock=:vc WHERE ticket_id=:tid"),
                {"now": now, "lt": lt, "vc": vc, "tid": ticket_id}
            )
            db.execute(
                text("UPDATE dbo.seats SET status='SOLD', locked_until=NULL, lamport_ts=:lt, vector_clock=:vc, last_update_epoch=:now WHERE seat_id=:sid"),
                {"now": now, "lt": lt, "vc": vc, "sid": row[1]}
            )
            db.commit()
            return {"ticket_id": ticket_id, "status": "PAID", "payment_epoch": now}
        except HTTPException:
            raise
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="Ticket no encontrado")
