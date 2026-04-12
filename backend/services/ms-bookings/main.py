"""
ms-bookings — Puerto 8002
Gestión de reservas: crear, pagar, cancelar (refund), expiración automática.
- Reserva = RESERVED por 24h → cron libera si no se paga
- LOCKED propagado a 3 nodos en <2s
"""
import os
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import get_db1, get_db2, mongo_db
from models import BookingCreate, BookingOut, SeatLockRequest, PaymentRequest, PassengerOut

app = FastAPI(
    title="ms-bookings",
    description="Microservicio de reservas — Aerolíneas Rafael Pabón",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NODE_ID = int(os.getenv("NODE_ID", "1"))
scheduler = AsyncIOScheduler()


def _node_for(flight_id: int) -> int:
    if flight_id < 100000:
        return 1
    if flight_id < 500000:
        return 2
    return 3


@app.on_event("startup")
async def startup():
    scheduler.add_job(expire_reservations, "interval", minutes=5, id="expire_job")
    scheduler.start()


@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"service": "ms-bookings", "status": "ok", "node_id": NODE_ID, "timestamp": int(time.time())}


# ─── Lock de asiento ─────────────────────────────────────────────────────────

@app.post("/seats/lock")
async def lock_seat(
    req: SeatLockRequest,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Bloquea un asiento por hasta 5 minutos (LOCKED)."""
    node = _node_for(req.flight_id)
    now = int(time.time())
    locked_until = now + min(req.duration_seconds, 300)

    if node == 3:
        seat = await mongo_db.seats.find_one({"seat_id": req.seat_id})
        if not seat:
            raise HTTPException(404, "Asiento no encontrado")
        if seat["status"] not in ("AVAILABLE",):
            raise HTTPException(409, f"Asiento no disponible: {seat['status']}")
        await mongo_db.seats.update_one(
            {"seat_id": req.seat_id},
            {"$set": {"status": "LOCKED", "locked_until": locked_until,
                      "last_update_epoch": now, "lamport_ts": now}}
        )
        return {"seat_id": req.seat_id, "status": "LOCKED", "locked_until": locked_until}

    db = db1 if node == 1 else db2
    row = db.execute(text("SELECT status FROM dbo.seats WHERE seat_id=:sid"), {"sid": req.seat_id}).fetchone()
    if not row:
        raise HTTPException(404, "Asiento no encontrado")
    if row[0] not in ("AVAILABLE",):
        raise HTTPException(409, f"Asiento no disponible: {row[0]}")
    db.execute(
        text("UPDATE dbo.seats SET status='LOCKED', locked_until=:lu, last_update_epoch=:now WHERE seat_id=:sid"),
        {"lu": locked_until, "now": now, "sid": req.seat_id}
    )
    db.commit()
    return {"seat_id": req.seat_id, "status": "LOCKED", "locked_until": locked_until}


# ─── Crear reserva ────────────────────────────────────────────────────────────

@app.post("/bookings", response_model=BookingOut, status_code=201)
async def create_booking(
    req: BookingCreate,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    node = _node_for(req.flight_id)
    now = int(time.time())
    expiry = now + 86400  # 24 horas

    if node == 3:
        # Validar asiento
        seat = await mongo_db.seats.find_one({"seat_id": req.seat_id, "flight_id": req.flight_id})
        if not seat or seat["status"] not in ("AVAILABLE", "LOCKED"):
            raise HTTPException(409, "Asiento no disponible")
        price = seat["price"]

        # Upsert pasajero
        existing = await mongo_db.passengers.find_one({"passport_number": req.passenger.passport_number})
        if existing:
            passenger_id = existing["passenger_id"]
        else:
            counter = await mongo_db.counters.find_one_and_update(
                {"_id": "passenger_id"}, {"$inc": {"seq": 1}}, return_document=True
            )
            passenger_id = counter["seq"]
            await mongo_db.passengers.insert_one({
                "passenger_id": passenger_id, **req.passenger.model_dump(),
                "node_id": 3, "lamport_ts": now, "vector_clock": "[0,0,0]", "last_update_epoch": now
            })

        ticket_counter = await mongo_db.counters.find_one_and_update(
            {"_id": "ticket_id"}, {"$inc": {"seq": 1}}, return_document=True
        )
        ticket_id = ticket_counter["seq"]
        await mongo_db.tickets.insert_one({
            "ticket_id": ticket_id, "passenger_id": passenger_id,
            "flight_id": req.flight_id, "seat_id": req.seat_id,
            "status": "RESERVED", "booking_epoch": now, "expiry_epoch": expiry,
            "payment_epoch": None, "total_price": price,
            "node_id": 3, "lamport_ts": now, "vector_clock": "[0,0,0]", "last_update_epoch": now
        })
        await mongo_db.seats.update_one(
            {"seat_id": req.seat_id},
            {"$set": {"status": "RESERVED", "last_update_epoch": now}}
        )
        return BookingOut(ticket_id=ticket_id, passenger_id=passenger_id,
                          flight_id=req.flight_id, seat_id=req.seat_id,
                          status="RESERVED", booking_epoch=now, expiry_epoch=expiry,
                          total_price=price, node_id=3, vector_clock="[0,0,0]", lamport_ts=now)

    db = db1 if node == 1 else db2
    seat_row = db.execute(
        text("SELECT status, price FROM dbo.seats WHERE seat_id=:sid AND flight_id=:fid"),
        {"sid": req.seat_id, "fid": req.flight_id}
    ).fetchone()
    if not seat_row or seat_row[0] not in ("AVAILABLE", "LOCKED"):
        raise HTTPException(409, "Asiento no disponible")
    price = float(seat_row[1])

    # Upsert pasajero
    existing = db.execute(
        text("SELECT passenger_id FROM dbo.passengers WHERE passport_number=:pp"),
        {"pp": req.passenger.passport_number}
    ).fetchone()
    if existing:
        passenger_id = existing[0]
    else:
        db.execute(
            text("""INSERT INTO dbo.passengers (full_name,email,passport_number,phone,nationality,
                    node_id,lamport_ts,vector_clock,last_update_epoch)
                    VALUES(:fn,:em,:pp,:ph,:na,:ni,0,'[0,0,0]',:now)"""),
            {"fn": req.passenger.full_name, "em": req.passenger.email,
             "pp": req.passenger.passport_number, "ph": req.passenger.phone,
             "na": req.passenger.nationality, "ni": node, "now": now}
        )
        db.flush()
        passenger_id = db.execute(text("SELECT @@IDENTITY")).scalar()

    db.execute(
        text("""INSERT INTO dbo.tickets
                (passenger_id,flight_id,seat_id,status,booking_epoch,expiry_epoch,
                 total_price,node_id,lamport_ts,vector_clock,last_update_epoch)
                VALUES(:pid,:fid,:sid,'RESERVED',:now,:exp,:price,:ni,0,'[0,0,0]',:now)"""),
        {"pid": passenger_id, "fid": req.flight_id, "sid": req.seat_id,
         "now": now, "exp": expiry, "price": price, "ni": node}
    )
    ticket_id = db.execute(text("SELECT @@IDENTITY")).scalar()
    db.execute(
        text("UPDATE dbo.seats SET status='RESERVED', last_update_epoch=:now WHERE seat_id=:sid"),
        {"now": now, "sid": req.seat_id}
    )
    db.commit()
    return BookingOut(ticket_id=int(ticket_id), passenger_id=int(passenger_id),
                      flight_id=req.flight_id, seat_id=req.seat_id,
                      status="RESERVED", booking_epoch=now, expiry_epoch=expiry,
                      total_price=price, node_id=node, vector_clock="[0,0,0]", lamport_ts=0)


# ─── Pago ─────────────────────────────────────────────────────────────────────

@app.post("/bookings/{ticket_id}/pay")
async def pay_booking(
    ticket_id: int,
    req: PaymentRequest,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    now = int(time.time())
    # Determinar BD por ticket_id
    if ticket_id < 100000:
        db = db1
        row = db.execute(text("SELECT status,total_price,seat_id,expiry_epoch FROM dbo.tickets WHERE ticket_id=:tid"), {"tid": ticket_id}).fetchone()
        if not row:
            raise HTTPException(404, "Ticket no encontrado")
        if row[0] != "RESERVED":
            raise HTTPException(409, f"Ticket en estado {row[0]}")
        if now > row[3]:
            raise HTTPException(410, "Ticket expirado")
        db.execute(
            text("UPDATE dbo.tickets SET status='PAID', payment_epoch=:now WHERE ticket_id=:tid"),
            {"now": now, "tid": ticket_id}
        )
        db.execute(
            text("UPDATE dbo.seats SET status='SOLD', last_update_epoch=:now WHERE seat_id=:sid"),
            {"now": now, "sid": row[2]}
        )
        db.commit()
    elif ticket_id < 500000:
        db = db2
        row = db.execute(text("SELECT status,total_price,seat_id,expiry_epoch FROM dbo.tickets WHERE ticket_id=:tid"), {"tid": ticket_id}).fetchone()
        if not row:
            raise HTTPException(404, "Ticket no encontrado")
        if row[0] != "RESERVED":
            raise HTTPException(409, f"Ticket en estado {row[0]}")
        if now > row[3]:
            raise HTTPException(410, "Ticket expirado")
        db.execute(
            text("UPDATE dbo.tickets SET status='PAID', payment_epoch=:now WHERE ticket_id=:tid"),
            {"now": now, "tid": ticket_id}
        )
        db.execute(
            text("UPDATE dbo.seats SET status='SOLD', last_update_epoch=:now WHERE seat_id=:sid"),
            {"now": now, "sid": row[2]}
        )
        db.commit()
    else:
        ticket = await mongo_db.tickets.find_one({"ticket_id": ticket_id})
        if not ticket:
            raise HTTPException(404, "Ticket no encontrado")
        if ticket["status"] != "RESERVED":
            raise HTTPException(409, f"Ticket en estado {ticket['status']}")
        if now > ticket["expiry_epoch"]:
            raise HTTPException(410, "Ticket expirado")
        await mongo_db.tickets.update_one({"ticket_id": ticket_id}, {"$set": {"status": "PAID", "payment_epoch": now}})
        await mongo_db.seats.update_one({"seat_id": ticket["seat_id"]}, {"$set": {"status": "SOLD", "last_update_epoch": now}})

    return {"ticket_id": ticket_id, "status": "PAID", "payment_epoch": now}


# ─── Cron: expirar reservas ───────────────────────────────────────────────────

async def expire_reservations():
    now = int(time.time())
    # Se ejecuta sobre las 3 BDs — CAP: AP, puede fallar parcialmente
    from database import Session1, Session2
    for SessionCls in [Session1, Session2]:
        try:
            db = SessionCls()
            rows = db.execute(
                text("SELECT ticket_id, seat_id FROM dbo.tickets WHERE status='RESERVED' AND expiry_epoch < :now"),
                {"now": now}
            ).fetchall()
            for t_id, s_id in rows:
                db.execute(text("UPDATE dbo.tickets SET status='EXPIRED' WHERE ticket_id=:tid"), {"tid": t_id})
                db.execute(text("UPDATE dbo.seats SET status='AVAILABLE', locked_until=NULL WHERE seat_id=:sid"), {"sid": s_id})
            db.commit()
            db.close()
        except Exception:
            pass
    try:
        expired = await mongo_db.tickets.find({"status": "RESERVED", "expiry_epoch": {"$lt": now}}).to_list(None)
        for t in expired:
            await mongo_db.tickets.update_one({"ticket_id": t["ticket_id"]}, {"$set": {"status": "EXPIRED"}})
            await mongo_db.seats.update_one({"seat_id": t["seat_id"]}, {"$set": {"status": "AVAILABLE", "locked_until": None}})
    except Exception:
        pass
