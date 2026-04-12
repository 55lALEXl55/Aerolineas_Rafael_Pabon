"""
ms-flights — Puerto 8001
Gestión de vuelos: búsqueda, detalle, asientos, disponibilidad.
Consulta las 3 BDs (DB1 América, DB2 Europa, DB3 Asia).
"""
import os
import time
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db1, get_db2, mongo_db
from models import FlightOut, SeatOut, AircraftOut, FlightSearchParams

app = FastAPI(
    title="ms-flights",
    description="Microservicio de vuelos — Aerolíneas Rafael Pabón",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NODE_ID = int(os.getenv("NODE_ID", "1"))

# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "service": "ms-flights",
        "status": "ok",
        "node_id": NODE_ID,
        "timestamp": int(time.time()),
    }


# ─── Búsqueda de vuelos (todas las BDs) ─────────────────────────────────────

@app.get("/flights", response_model=List[dict])
async def search_flights(
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
    """Busca vuelos en las 3 BDs y retorna resultados combinados."""
    conditions = []
    params: dict = {}

    if origin:
        conditions.append("origin = :origin")
        params["origin"] = origin.upper()
    if destination:
        conditions.append("destination = :destination")
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
        SELECT flight_id, flight_number, aircraft_id, origin, destination,
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

    # DB1
    try:
        rows = db1.execute(sql, params).mappings().all()
        results.extend([dict(r) for r in rows])
    except Exception as e:
        pass  # CAP: AP — continuar aunque falle un nodo

    # DB2
    try:
        rows = db2.execute(sql, params).mappings().all()
        results.extend([dict(r) for r in rows])
    except Exception as e:
        pass

    # DB3 (MongoDB)
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
        cursor = mongo_db.flights.find(mongo_filter, {"_id": 0}).skip(offset).limit(limit)
        async for doc in cursor:
            results.append(doc)
    except Exception:
        pass

    results.sort(key=lambda x: x.get("departure_epoch", 0))
    return results[:limit]


# ─── Detalle de un vuelo ─────────────────────────────────────────────────────

@app.get("/flights/{flight_id}")
async def get_flight(
    flight_id: int,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    sql = text("SELECT * FROM dbo.flights WHERE flight_id = :fid")

    if flight_id < 100000:
        row = db1.execute(sql, {"fid": flight_id}).mappings().first()
    elif flight_id < 500000:
        row = db2.execute(sql, {"fid": flight_id}).mappings().first()
    else:
        doc = await mongo_db.flights.find_one({"flight_id": flight_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Vuelo no encontrado")
        return doc

    if not row:
        raise HTTPException(status_code=404, detail="Vuelo no encontrado")
    return dict(row)


# ─── Asientos de un vuelo ────────────────────────────────────────────────────

@app.get("/flights/{flight_id}/seats")
async def get_seats(
    flight_id: int,
    seat_class: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    conditions = ["flight_id = :fid"]
    params: dict = {"fid": flight_id}
    if seat_class:
        conditions.append("seat_class = :cls")
        params["cls"] = seat_class.upper()
    if status:
        conditions.append("status = :st")
        params["st"] = status.upper()

    where = " AND ".join(conditions)
    sql = text(f"SELECT * FROM dbo.seats WHERE {where} ORDER BY seat_number")

    if flight_id < 100000:
        rows = db1.execute(sql, params).mappings().all()
    elif flight_id < 500000:
        rows = db2.execute(sql, params).mappings().all()
    else:
        mongo_filter: dict = {"flight_id": flight_id}
        if seat_class:
            mongo_filter["seat_class"] = seat_class.upper()
        if status:
            mongo_filter["status"] = status.upper()
        docs = []
        async for doc in mongo_db.seats.find(mongo_filter, {"_id": 0}):
            docs.append(doc)
        return docs

    return [dict(r) for r in rows]


# ─── Aeronaves ───────────────────────────────────────────────────────────────

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
