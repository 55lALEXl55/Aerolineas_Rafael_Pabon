"""
ms-flights — Puerto 8001
Gestión de vuelos: búsqueda, detalle, asientos, estadísticas.
Consulta las 3 BDs (DB1 América, DB2 Europa, DB3 Asia).
"""
import json
import os
import sys
import time
from typing import List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

sys.path.insert(0, "/app/shared")
from lamport_clock import LamportClock
from vector_clock import VectorClock

from database import get_db1, get_db2, mongo_db

app = FastAPI(
    title="ms-flights",
    description="Microservicio de vuelos — Aerolíneas Rafael Pabón",
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

# ─── Routing por aeropuerto ───────────────────────────────────────────────────

DB1_AIRPORTS = frozenset(["ATL", "LAX", "DFW", "SAO"])
DB2_AIRPORTS = frozenset(["LON", "PAR", "FRA", "IST", "MAD", "AMS", "DXB"])
DB3_AIRPORTS = frozenset(["PEK", "TYO", "SIN", "CAN"])


def _node_for_airport(iata: str) -> int:
    o = iata.upper().strip()
    if o in DB1_AIRPORTS:
        return 1
    if o in DB2_AIRPORTS:
        return 2
    return 3


def _node_for_flight(flight_id: int) -> int:
    if flight_id < 100_000:
        return 1
    if flight_id < 500_000:
        return 2
    return 3


async def _propagate(operation: str, table: str, record_id: int, payload: dict):
    """Fire-and-forget: registrar evento en ms-sync."""
    lt = lamport.tick()
    vc = vector.tick()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(f"{MS_SYNC_URL}/sync/events", json={
                "source_node": NODE_ID,
                "operation": operation,
                "table_name": table,
                "record_id": record_id,
                "payload": payload,
            })
    except Exception:
        pass  # CAP: AP — continuar aunque ms-sync no esté disponible


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "service": "ms-flights",
        "status": "ok",
        "node_id": NODE_ID,
        "lamport_ts": lamport.value,
        "vector_clock": vector.to_string(),
        "timestamp": int(time.time()),
    }


# ─── GET /flights/search ─────────────────────────────────────────────────────

@app.get("/flights/search")
async def search_flights(
    origin: str = Query(..., min_length=3, max_length=3),
    destination: str = Query(..., min_length=3, max_length=3),
    date_epoch: int = Query(..., description="Inicio del día en epoch unix"),
    seat_class: Optional[str] = Query(None, regex="^(FIRST|ECONOMY)$"),
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """
    Busca vuelos directos en la BD correspondiente al aeropuerto de origen.
    Retorna lista vacía si no hay directos (ms-routes calculará escalas).
    """
    origin = origin.upper().strip()
    destination = destination.upper().strip()
    date_from = date_epoch
    date_to = date_epoch + 86_400  # fin del día

    seat_filter = ""
    if seat_class == "FIRST":
        seat_filter = " AND f.available_first > 0"
    elif seat_class == "ECONOMY":
        seat_filter = " AND f.available_economy > 0"
    else:
        seat_filter = " AND (f.available_first > 0 OR f.available_economy > 0)"

    sql = text(f"""
        SELECT
            f.flight_id,
            RTRIM(f.origin)      AS origin,
            RTRIM(f.destination) AS destination,
            f.departure_epoch    AS flight_date_epoch,
            f.arrival_epoch,
            f.duration_minutes,
            ROUND(f.duration_minutes / 60.0, 2) AS duration_hours,
            a.model              AS aircraft_model,
            a.manufacturer,
            a.engines,
            a.seats_first,
            a.seats_economy,
            a.total_seats,
            f.available_first,
            f.available_economy,
            f.price_first        AS first_class_price,
            f.price_economy      AS economy_price,
            f.status,
            f.flight_number,
            f.node_id,
            f.lamport_ts,
            f.vector_clock,
            f.last_update_epoch
        FROM dbo.flights f
        JOIN dbo.aircraft a ON a.aircraft_id = f.aircraft_id
        WHERE RTRIM(f.origin) = :origin
          AND RTRIM(f.destination) = :destination
          AND f.departure_epoch >= :date_from
          AND f.departure_epoch < :date_to
          AND f.status IN ('SCHEDULED', 'BOARDING')
          {seat_filter}
        ORDER BY f.departure_epoch
    """)

    params = {
        "origin": origin,
        "destination": destination,
        "date_from": date_from,
        "date_to": date_to,
    }

    node = _node_for_airport(origin)

    if node == 3:
        mongo_filter: dict = {
            "origin": origin,
            "destination": destination,
            "departure_epoch": {"$gte": date_from, "$lt": date_to},
            "status": {"$in": ["SCHEDULED", "BOARDING"]},
        }
        if seat_class == "FIRST":
            mongo_filter["available_first"] = {"$gt": 0}
        elif seat_class == "ECONOMY":
            mongo_filter["available_economy"] = {"$gt": 0}
        else:
            mongo_filter["$or"] = [
                {"available_first": {"$gt": 0}},
                {"available_economy": {"$gt": 0}},
            ]

        results = []
        async for doc in mongo_db.flights.find(mongo_filter, {"_id": 0}):
            # Enriquecer con datos del avión
            aircraft_doc = await mongo_db.aircraft.find_one(
                {"aircraft_id": doc.get("aircraft_id")}, {"_id": 0}
            )
            if aircraft_doc:
                doc["aircraft_model"] = aircraft_doc.get("model", "")
                doc["manufacturer"] = aircraft_doc.get("manufacturer", "")
                doc["engines"] = aircraft_doc.get("engines", 0)
                doc["seats_first"] = aircraft_doc.get("seats_first", 0)
                doc["seats_economy"] = aircraft_doc.get("seats_economy", 0)
                doc["total_seats"] = aircraft_doc.get("total_seats", 0)
            doc["first_class_price"] = doc.get("price_first", 0)
            doc["economy_price"] = doc.get("price_economy", 0)
            doc["flight_date_epoch"] = doc.get("departure_epoch", 0)
            doc["duration_hours"] = round(doc.get("duration_minutes", 0) / 60, 2)
            results.append(doc)
        return results

    db = db1 if node == 1 else db2
    try:
        rows = db.execute(sql, params).mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        return []


# ─── GET /flights/{flight_id} ────────────────────────────────────────────────

@app.get("/flights/{flight_id}")
async def get_flight(
    flight_id: int,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Detalle completo del vuelo incluyendo ficha técnica del avión."""
    node = _node_for_flight(flight_id)

    if node == 3:
        doc = await mongo_db.flights.find_one({"flight_id": flight_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Vuelo no encontrado")
        aircraft_doc = await mongo_db.aircraft.find_one(
            {"aircraft_id": doc.get("aircraft_id")}, {"_id": 0}
        )
        if aircraft_doc:
            aircraft_doc.pop("_id", None)
            doc["aircraft"] = aircraft_doc
        doc.setdefault("duration_hours", round(doc.get("duration_minutes", 0) / 60, 2))
        return doc

    db = db1 if node == 1 else db2
    sql = text("""
        SELECT
            f.*,
            a.model              AS aircraft_model,
            a.manufacturer,
            a.engines,
            a.seats_first,
            a.seats_economy,
            a.total_seats,
            ROUND(f.duration_minutes / 60.0, 2) AS duration_hours,
            RTRIM(f.origin)      AS origin,
            RTRIM(f.destination) AS destination
        FROM dbo.flights f
        JOIN dbo.aircraft a ON a.aircraft_id = f.aircraft_id
        WHERE f.flight_id = :fid
    """)
    row = db.execute(sql, {"fid": flight_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Vuelo no encontrado")
    return dict(row)


# ─── GET /flights/{flight_id}/seats ─────────────────────────────────────────

@app.get("/flights/{flight_id}/seats")
async def get_seats(
    flight_id: int,
    seat_class: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """
    Retorna todos los asientos con estado, precios y datos del pasajero
    (para tooltip en la UI).
    """
    node = _node_for_flight(flight_id)

    if node == 3:
        mongo_filter: dict = {"flight_id": flight_id}
        if seat_class:
            mongo_filter["seat_class"] = seat_class.upper()
        if status:
            mongo_filter["status"] = status.upper()

        results = []
        async for seat in mongo_db.seats.find(mongo_filter, {"_id": 0}):
            # Buscar nombre de pasajero para tooltip
            if seat.get("status") in ("RESERVED", "SOLD"):
                ticket = await mongo_db.tickets.find_one(
                    {"seat_id": seat["seat_id"], "status": {"$in": ["RESERVED", "PAID"]}},
                    {"_id": 0}
                )
                if ticket:
                    seat["reserved_until_epoch"] = ticket.get("expiry_epoch")
                    pax = await mongo_db.passengers.find_one(
                        {"passenger_id": ticket["passenger_id"]}, {"_id": 0}
                    )
                    if pax:
                        seat["passenger_name"] = pax.get("full_name")
            seat.setdefault("locked_until_epoch", seat.get("locked_until"))
            results.append(seat)
        return results

    db = db1 if node == 1 else db2

    extra_conds = ""
    params: dict = {"fid": flight_id}
    if seat_class:
        extra_conds += " AND s.seat_class = :cls"
        params["cls"] = seat_class.upper()
    if status:
        extra_conds += " AND s.status = :st"
        params["st"] = status.upper()

    sql = text(f"""
        SELECT
            s.seat_id,
            s.flight_id,
            s.seat_number,
            s.seat_class,
            s.status,
            s.price,
            s.locked_until          AS locked_until_epoch,
            s.locked_until          AS reserved_until_epoch,
            s.node_id,
            s.lamport_ts,
            s.vector_clock,
            s.last_update_epoch,
            p.full_name             AS passenger_name
        FROM dbo.seats s
        LEFT JOIN dbo.tickets t
            ON t.seat_id = s.seat_id
           AND t.status IN ('RESERVED', 'PAID')
        LEFT JOIN dbo.passengers p
            ON p.passenger_id = t.passenger_id
        WHERE s.flight_id = :fid {extra_conds}
        ORDER BY s.seat_number
    """)

    rows = db.execute(sql, params).mappings().all()
    return [dict(r) for r in rows]


# ─── GET /flights/{flight_id}/stats ─────────────────────────────────────────

@app.get("/flights/{flight_id}/stats")
async def get_flight_stats(
    flight_id: int,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Estadísticas del vuelo: totales por estado, ingresos, lista de pasajeros."""
    node = _node_for_flight(flight_id)

    if node == 3:
        # Totales por estado
        pipeline_status = [
            {"$match": {"flight_id": flight_id}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        status_counts: dict = {}
        async for doc in mongo_db.seats.aggregate(pipeline_status):
            status_counts[doc["_id"]] = doc["count"]

        # Ingresos por clase
        pipeline_revenue = [
            {"$match": {"flight_id": flight_id, "status": {"$in": ["SOLD", "RESERVED"]}}},
            {"$group": {
                "_id": "$seat_class",
                "revenue": {"$sum": "$price"},
                "count": {"$sum": 1},
            }},
        ]
        revenue: dict = {}
        async for doc in mongo_db.seats.aggregate(pipeline_revenue):
            revenue[doc["_id"]] = {"revenue": doc["revenue"], "count": doc["count"]}

        # Lista de pasajeros
        tickets = await mongo_db.tickets.find(
            {"flight_id": flight_id, "status": {"$in": ["RESERVED", "PAID", "REFUNDED"]}},
            {"_id": 0}
        ).to_list(None)
        passengers = []
        for t in tickets:
            pax = await mongo_db.passengers.find_one(
                {"passenger_id": t["passenger_id"]}, {"_id": 0}
            )
            if pax:
                passengers.append({
                    "ticket_id": t["ticket_id"],
                    "status": t["status"],
                    "full_name": pax.get("full_name"),
                    "passport_number": pax.get("passport_number"),
                    "seat_id": t.get("seat_id"),
                    "total_price": t.get("total_price"),
                    "booking_epoch": t.get("booking_epoch"),
                })

        return {
            "flight_id": flight_id,
            "status_counts": status_counts,
            "revenue_by_class": revenue,
            "passengers": passengers,
        }

    db = db1 if node == 1 else db2

    status_rows = db.execute(text("""
        SELECT status, COUNT(*) AS count
        FROM dbo.seats
        WHERE flight_id = :fid
        GROUP BY status
    """), {"fid": flight_id}).mappings().all()
    status_counts = {r["status"]: r["count"] for r in status_rows}

    revenue_rows = db.execute(text("""
        SELECT seat_class, SUM(price) AS revenue, COUNT(*) AS count
        FROM dbo.seats
        WHERE flight_id = :fid AND status IN ('SOLD', 'RESERVED')
        GROUP BY seat_class
    """), {"fid": flight_id}).mappings().all()
    revenue = {r["seat_class"]: {"revenue": float(r["revenue"]), "count": r["count"]}
               for r in revenue_rows}

    pax_rows = db.execute(text("""
        SELECT t.ticket_id, t.status, p.full_name, p.passport_number,
               t.seat_id, t.total_price, t.booking_epoch
        FROM dbo.tickets t
        JOIN dbo.passengers p ON p.passenger_id = t.passenger_id
        WHERE t.flight_id = :fid AND t.status IN ('RESERVED', 'PAID', 'REFUNDED')
    """), {"fid": flight_id}).mappings().all()

    return {
        "flight_id": flight_id,
        "status_counts": status_counts,
        "revenue_by_class": revenue,
        "passengers": [dict(r) for r in pax_rows],
    }


# ─── PUT /flights/{flight_id}/status ────────────────────────────────────────

@app.put("/flights/{flight_id}/status")
async def update_flight_status(
    flight_id: int,
    new_status: str = Body(..., embed=True),
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """
    Actualiza el estado del vuelo.
    Válidos: SCHEDULED | BOARDING | DEPARTED | ARRIVED | CANCELLED
    """
    VALID_STATUSES = {"SCHEDULED", "BOARDING", "DEPARTED", "ARRIVED", "CANCELLED"}
    if new_status.upper() not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail={
            "error": "STATUS_INVALIDO",
            "message": f"Estado debe ser uno de: {', '.join(VALID_STATUSES)}",
        })

    lt = lamport.tick()
    vc = vector.tick()
    now = int(time.time())
    vc_str = json.dumps(vc, separators=(",", ":"))
    node = _node_for_flight(flight_id)

    if node == 3:
        result = await mongo_db.flights.find_one_and_update(
            {"flight_id": flight_id},
            {"$set": {
                "status": new_status.upper(),
                "lamport_ts": lt,
                "vector_clock": vc_str,
                "last_update_epoch": now,
            }},
            return_document=True,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Vuelo no encontrado")
    else:
        db = db1 if node == 1 else db2
        res = db.execute(text("""
            UPDATE dbo.flights
            SET status = :st,
                lamport_ts = :lt,
                vector_clock = :vc,
                last_update_epoch = :now
            WHERE flight_id = :fid
        """), {"st": new_status.upper(), "lt": lt, "vc": vc_str,
               "now": now, "fid": flight_id})
        if res.rowcount == 0:
            db.rollback()
            raise HTTPException(status_code=404, detail="Vuelo no encontrado")
        db.commit()

    # Propagar a ms-sync (fire and forget)
    await _propagate("UPDATE", "flights", flight_id, {
        "status": new_status.upper(),
        "lamport_ts": lt,
        "vector_clock": vc_str,
        "last_update_epoch": now,
    })

    return {
        "flight_id": flight_id,
        "status": new_status.upper(),
        "lamport_ts": lt,
        "vector_clock": vc_str,
        "last_update_epoch": now,
    }


# ─── GET /flights/seats/query ────────────────────────────────────────────────

@app.get("/flights/seats/query")
async def query_seats(
    flight_id: Optional[int] = Query(None),
    seat_class: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Panel de consultas avanzadas: filtrar asientos por vuelo, clase y estado."""
    if flight_id is not None:
        # Delegate to existing seats endpoint logic
        return await get_seats(flight_id=flight_id, seat_class=seat_class,
                               status=status, db1=db1, db2=db2)

    # Sin flight_id: consulta agregada en SQL Server (hasta limit registros por nodo)
    extra = []
    params: dict = {"limit": limit}
    if seat_class:
        extra.append("s.seat_class = :cls")
        params["cls"] = seat_class.upper()
    if status:
        extra.append("s.status = :st")
        params["st"] = status.upper()
    where = ("WHERE " + " AND ".join(extra)) if extra else ""
    sql = text(f"""
        SELECT TOP (:limit) s.seat_id, s.flight_id, s.seat_number, s.seat_class,
               s.status, s.price, s.node_id, s.lamport_ts, s.vector_clock
        FROM dbo.seats s {where}
        ORDER BY s.seat_id
    """)
    results = []
    for db in [db1, db2]:
        try:
            rows = db.execute(sql, params).mappings().all()
            results.extend([dict(r) for r in rows])
        except Exception:
            pass
    return results[:limit]


# ─── GET /flights (listado general, mantener compatibilidad) ─────────────────

@app.get("/flights")
async def list_flights(
    origin: Optional[str] = Query(None),
    destination: Optional[str] = Query(None),
    departure_from: Optional[int] = Query(None),
    departure_to: Optional[int] = Query(None),
    status: Optional[str] = Query("SCHEDULED"),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Búsqueda general de vuelos en las 3 BDs."""
    conditions = []
    params: dict = {}

    if origin:
        conditions.append("RTRIM(origin) = :origin")
        params["origin"] = origin.upper()
    if destination:
        conditions.append("RTRIM(destination) = :destination")
        params["destination"] = destination.upper()
    if departure_from:
        conditions.append("departure_epoch >= :dep_from")
        params["dep_from"] = departure_from
    if departure_to:
        conditions.append("departure_epoch <= :dep_to")
        params["dep_to"] = departure_to
    if status:
        conditions.append("status = :status")
        params["status"] = status

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = text(f"""
        SELECT flight_id, flight_number, aircraft_id,
               RTRIM(origin) AS origin, RTRIM(destination) AS destination,
               departure_epoch, arrival_epoch, duration_minutes,
               price_economy, price_first, status,
               available_economy, available_first, node_id,
               lamport_ts, vector_clock, last_update_epoch
        FROM dbo.flights {where}
        ORDER BY departure_epoch
        OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
    """)
    params["offset"] = offset
    params["limit"]  = limit

    results = []

    for db in [db1, db2]:
        try:
            rows = db.execute(sql, params).mappings().all()
            results.extend([dict(r) for r in rows])
        except Exception:
            pass

    try:
        mongo_filter: dict = {}
        if origin:
            mongo_filter["origin"] = origin.upper()
        if destination:
            mongo_filter["destination"] = destination.upper()
        if departure_from or departure_to:
            mongo_filter["departure_epoch"] = {}
            if departure_from:
                mongo_filter["departure_epoch"]["$gte"] = departure_from
            if departure_to:
                mongo_filter["departure_epoch"]["$lte"] = departure_to
        if status:
            mongo_filter["status"] = status
        async for doc in mongo_db.flights.find(mongo_filter, {"_id": 0}).skip(offset).limit(limit):
            results.append(doc)
    except Exception:
        pass

    results.sort(key=lambda x: x.get("departure_epoch", 0))
    return results[:limit]


# ─── Aeronaves (endpoints de compatibilidad) ─────────────────────────────────

@app.get("/aircraft")
async def list_aircraft(db1: Session = Depends(get_db1)):
    rows = db1.execute(text("SELECT * FROM dbo.aircraft ORDER BY aircraft_id")).mappings().all()
    return [dict(r) for r in rows]


@app.get("/aircraft/{aircraft_id}")
async def get_aircraft(aircraft_id: int, db1: Session = Depends(get_db1)):
    row = db1.execute(
        text("SELECT * FROM dbo.aircraft WHERE aircraft_id = :aid"),
        {"aid": aircraft_id}
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Aeronave no encontrada")
    return dict(row)
