"""
ms-dashboard — Puerto 8006
Dashboard gerencial: métricas en tiempo real de los 3 nodos.
Usa asyncio.gather para consultas paralelas; si un nodo cae (timeout 5s) → DEGRADED.
"""
import asyncio
import os
import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db1, get_db2, mongo_db

app = FastAPI(
    title="ms-dashboard",
    description="Dashboard gerencial — Aerolíneas Rafael Pabón",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NODE_ID      = int(os.getenv("NODE_ID", "1"))
MS_SYNC_URL  = os.getenv("MS_SYNC_URL", "http://ms-sync:8004")

# ── Flota (datos de CLAUDE.md) ─────────────────────────────────────────────────
AIRCRAFT_SPECS: Dict[str, dict] = {
    "A380-800": {
        "manufacturer": "Airbus", "model": "A380-800",
        "primera_clase": 10, "turista": 439, "total_seats": 449,
        "motores": 4, "longitud_m": 72.7, "envergadura_m": 79.75,
        "alcance_km": 15200, "vel_crucero_kmh": 903,
        "aircraft_ids": list(range(1, 7)),
    },
    "B777-300ER": {
        "manufacturer": "Boeing", "model": "777-300ER",
        "primera_clase": 10, "turista": 300, "total_seats": 310,
        "motores": 2, "longitud_m": 73.9, "envergadura_m": 64.8,
        "alcance_km": 13650, "vel_crucero_kmh": 905,
        "aircraft_ids": list(range(7, 25)),
    },
    "A350-900": {
        "manufacturer": "Airbus", "model": "A350-900",
        "primera_clase": 12, "turista": 250, "total_seats": 262,
        "motores": 2, "longitud_m": 66.89, "envergadura_m": 64.75,
        "alcance_km": 15000, "vel_crucero_kmh": 903,
        "aircraft_ids": list(range(25, 36)),
    },
    "B787-9": {
        "manufacturer": "Boeing", "model": "787-9 Dreamliner",
        "primera_clase": 8, "turista": 220, "total_seats": 228,
        "motores": 2, "longitud_m": 62.8, "envergadura_m": 60.12,
        "alcance_km": 14140, "vel_crucero_kmh": 903,
        "aircraft_ids": list(range(36, 51)),
    },
}

# Alias de búsqueda para el endpoint /aircraft/{model}
MODEL_ALIASES: Dict[str, str] = {
    "a380": "A380-800", "a380-800": "A380-800",
    "b777": "B777-300ER", "777": "B777-300ER", "b777-300er": "B777-300ER",
    "a350": "A350-900", "a350-900": "A350-900",
    "b787": "B787-9", "787": "B787-9", "b787-9": "B787-9",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _sql_node(db: Session, sql: str, params: dict = None) -> Any:
    """Ejecuta SQL y devuelve el primer row como dict, o Exception."""
    try:
        return db.execute(text(sql), params or {}).mappings().first()
    except Exception as e:
        return e


async def _gather_sql(db1: Session, db2: Session, sql: str, params: dict = None):
    """Ejecuta la misma SQL en DB1 y DB2 en paralelo."""
    r1, r2 = await asyncio.gather(
        asyncio.to_thread(_safe_sql, db1, sql, params or {}),
        asyncio.to_thread(_safe_sql, db2, sql, params or {}),
        return_exceptions=True,
    )
    return r1, r2


def _safe_sql(db: Session, sql: str, params: dict):
    try:
        return db.execute(text(sql), params).mappings().all()
    except Exception as e:
        return e


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"service": "ms-dashboard", "status": "ok", "node_id": NODE_ID, "timestamp": int(time.time())}


# ─── Overview (KPIs globales) ─────────────────────────────────────────────────

@app.get("/dashboard/overview")
async def dashboard_overview(
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """KPIs principales agregados de los 3 nodos en paralelo."""
    now = int(time.time())

    # SQL queries (SQL Server)
    STATS_SQL = """
        SELECT
            COUNT(DISTINCT f.flight_id)                                         AS total_flights,
            COUNT(s.seat_id)                                                    AS total_seats,
            SUM(CASE WHEN s.status='AVAILABLE' THEN 1 ELSE 0 END)              AS seats_available,
            SUM(CASE WHEN s.status='RESERVED'  THEN 1 ELSE 0 END)              AS seats_reserved,
            SUM(CASE WHEN s.status='SOLD'      THEN 1 ELSE 0 END)              AS seats_sold,
            SUM(CASE WHEN s.status='LOCKED'    THEN 1 ELSE 0 END)              AS seats_locked,
            SUM(CASE WHEN s.status='REFUNDED'  THEN 1 ELSE 0 END)              AS seats_refunded,
            SUM(CASE WHEN f.status='SCHEDULED' THEN 1 ELSE 0 END)              AS fl_scheduled,
            SUM(CASE WHEN f.status='BOARDING'  THEN 1 ELSE 0 END)              AS fl_boarding,
            SUM(CASE WHEN f.status='DEPARTED'  THEN 1 ELSE 0 END)              AS fl_departed,
            SUM(CASE WHEN f.status='IN_FLIGHT' THEN 1 ELSE 0 END)              AS fl_in_flight,
            SUM(CASE WHEN f.status='LANDED'    THEN 1 ELSE 0 END)              AS fl_landed,
            SUM(CASE WHEN f.status='ARRIVED'   THEN 1 ELSE 0 END)              AS fl_arrived,
            SUM(CASE WHEN f.status='DELAYED'   THEN 1 ELSE 0 END)              AS fl_delayed,
            COUNT(DISTINCT t.passenger_id)                                      AS passengers
        FROM dbo.flights f
        LEFT JOIN dbo.seats s   ON f.flight_id = s.flight_id
        LEFT JOIN dbo.tickets t ON t.flight_id = f.flight_id
                               AND t.status IN ('PAID','RESERVED')
    """
    REV_SQL = """
        SELECT
            ISNULL(SUM(t.total_price), 0)                                          AS revenue,
            ISNULL(SUM(CASE WHEN s.seat_class IN ('FIRST','PRIMERA') THEN t.total_price ELSE 0 END), 0)
                                                                                    AS rev_first,
            ISNULL(SUM(CASE WHEN s.seat_class NOT IN ('FIRST','PRIMERA') THEN t.total_price ELSE 0 END), 0)
                                                                                    AS rev_economy
        FROM dbo.tickets t
        JOIN dbo.seats s ON t.seat_id = s.seat_id
        WHERE t.status IN ('PAID','RESERVED')
    """

    def _node_stats(db: Session, node_id: int, region: str) -> dict:
        try:
            s = db.execute(text(STATS_SQL)).mappings().first()
            r = db.execute(text(REV_SQL)).mappings().first()
            return {
                "node_id": node_id, "region": region, "status": "UP",
                "revenue": float(r["revenue"] or 0),
                "flights": int(s["total_flights"] or 0),
                "seats_sold": int(s["seats_sold"] or 0),
                "seats_available": int(s["seats_available"] or 0),
                "seats_reserved": int(s["seats_reserved"] or 0),
                "seats_locked": int(s["seats_locked"] or 0),
                "seats_refunded": int(s["seats_refunded"] or 0),
                "total_seats": int(s["total_seats"] or 0),
                "passengers": int(s["passengers"] or 0),
                "rev_first": float(r["rev_first"] or 0),
                "rev_economy": float(r["rev_economy"] or 0),
                "flights_by_status": {
                    "SCHEDULED": int(s["fl_scheduled"] or 0),
                    "BOARDING":  int(s["fl_boarding"]  or 0),
                    "DEPARTED":  int(s["fl_departed"]  or 0),
                    "IN_FLIGHT": int(s["fl_in_flight"] or 0),
                    "LANDED":    int(s["fl_landed"]    or 0),
                    "ARRIVED":   int(s["fl_arrived"]   or 0),
                    "DELAYED":   int(s["fl_delayed"]   or 0),
                },
            }
        except Exception as e:
            return {"node_id": node_id, "region": region, "status": "DEGRADED", "error": str(e),
                    "revenue": 0, "flights": 0, "seats_sold": 0}

    async def _node3_stats() -> dict:
        try:
            tf  = await mongo_db.flights.count_documents({})
            ts  = await mongo_db.seats.count_documents({})
            rev_docs = await mongo_db.tickets.aggregate([
                {"$match": {"status": {"$in": ["PAID", "RESERVED"]}}},
                {"$lookup": {"from": "seats", "localField": "seat_id",
                             "foreignField": "seat_id", "as": "seat"}},
                {"$unwind": {"path": "$seat", "preserveNullAndEmptyArrays": True}},
                {"$group": {
                    "_id": None,
                    "revenue":     {"$sum": "$total_price"},
                    "rev_first":   {"$sum": {"$cond": [
                        {"$in": ["$seat.seat_class", ["FIRST", "PRIMERA"]]},
                        "$total_price", 0
                    ]}},
                    "passengers":  {"$addToSet": "$passenger_id"},
                    "seats_sold":  {"$sum": 1},
                }},
            ]).to_list(1)
            r = rev_docs[0] if rev_docs else {}

            seat_counts = {}
            for status in ["AVAILABLE", "RESERVED", "SOLD", "LOCKED", "REFUNDED"]:
                seat_counts[status] = await mongo_db.seats.count_documents({"status": status})

            fl_counts = {}
            for status in ["SCHEDULED", "BOARDING", "DEPARTED", "IN_FLIGHT", "LANDED", "ARRIVED", "DELAYED"]:
                fl_counts[status] = await mongo_db.flights.count_documents({"status": status})

            return {
                "node_id": 3, "region": "Asia+Oceanía", "status": "UP",
                "revenue":        float(r.get("revenue", 0) or 0),
                "rev_first":      float(r.get("rev_first", 0) or 0),
                "rev_economy":    float((r.get("revenue", 0) or 0) - (r.get("rev_first", 0) or 0)),
                "flights":        tf,
                "total_seats":    ts,
                "seats_sold":     seat_counts["SOLD"],
                "seats_available":seat_counts["AVAILABLE"],
                "seats_reserved": seat_counts["RESERVED"],
                "seats_locked":   seat_counts["LOCKED"],
                "seats_refunded": seat_counts["REFUNDED"],
                "passengers":     len(r.get("passengers", [])),
                "flights_by_status": fl_counts,
            }
        except Exception as e:
            return {"node_id": 3, "region": "Asia+Oceanía", "status": "DEGRADED", "error": str(e),
                    "revenue": 0, "flights": 0, "seats_sold": 0}

    n1, n2, n3 = await asyncio.gather(
        asyncio.to_thread(_node_stats, db1, 1, "América"),
        asyncio.to_thread(_node_stats, db2, 2, "Europa+MO"),
        _node3_stats(),
    )

    def _int(v): return int(v or 0)
    def _flt(v): return float(v or 0)

    total_revenue  = _flt(n1["revenue"]) + _flt(n2["revenue"]) + _flt(n3["revenue"])
    rev_first      = _flt(n1.get("rev_first", 0)) + _flt(n2.get("rev_first", 0)) + _flt(n3.get("rev_first", 0))
    rev_economy    = total_revenue - rev_first
    total_flights  = _int(n1["flights"]) + _int(n2["flights"]) + _int(n3["flights"])
    total_seats    = sum(_int(n.get("total_seats", 0)) for n in [n1, n2, n3])
    total_pax      = sum(_int(n.get("passengers", 0)) for n in [n1, n2, n3])

    seats_by_status: Dict[str, int] = {}
    fl_by_status:    Dict[str, int] = {}
    for n in [n1, n2, n3]:
        for k in ["AVAILABLE", "RESERVED", "SOLD", "LOCKED", "REFUNDED"]:
            seats_by_status[k] = seats_by_status.get(k, 0) + _int(n.get(f"seats_{k.lower()}", 0))
        for k in ["SCHEDULED", "BOARDING", "DEPARTED", "IN_FLIGHT", "LANDED", "ARRIVED", "DELAYED"]:
            fs = n.get("flights_by_status", {})
            fl_by_status[k] = fl_by_status.get(k, 0) + _int(fs.get(k, 0))

    return {
        "total_revenue":      round(total_revenue, 2),
        "revenue_first_class":round(rev_first, 2),
        "revenue_economy":    round(rev_economy, 2),
        "total_flights":      total_flights,
        "total_seats":        total_seats,
        "seats_by_status":    seats_by_status,
        "flights_by_status":  fl_by_status,
        "total_passengers":   total_pax,
        "by_node": {
            "node1": {"revenue": round(_flt(n1["revenue"]), 2),
                      "flights": _int(n1["flights"]),
                      "seats_sold": _int(n1["seats_sold"]),
                      "status": n1["status"]},
            "node2": {"revenue": round(_flt(n2["revenue"]), 2),
                      "flights": _int(n2["flights"]),
                      "seats_sold": _int(n2["seats_sold"]),
                      "status": n2["status"]},
            "node3": {"revenue": round(_flt(n3["revenue"]), 2),
                      "flights": _int(n3["flights"]),
                      "seats_sold": _int(n3["seats_sold"]),
                      "status": n3["status"]},
        },
        "timestamp": now,
    }


# ─── Revenue por ruta ─────────────────────────────────────────────────────────

@app.get("/dashboard/revenue-by-route")
async def revenue_by_route(
    limit: int = Query(10, le=50),
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Top N rutas por ingreso total."""
    results: List[dict] = []
    sql = f"""
        SELECT TOP({limit}) f.origin, f.destination,
               COUNT(t.ticket_id) AS tickets,
               ISNULL(SUM(t.total_price), 0) AS revenue
        FROM dbo.tickets t
        JOIN dbo.flights f ON t.flight_id = f.flight_id
        WHERE t.status IN ('PAID','RESERVED')
        GROUP BY f.origin, f.destination
        ORDER BY revenue DESC
    """
    for db in [db1, db2]:
        try:
            rows = db.execute(text(sql)).mappings().all()
            for r in rows:
                results.append({
                    "route":   f"{r['origin']}→{r['destination']}",
                    "origin":  r["origin"],
                    "destination": r["destination"],
                    "revenue": float(r["revenue"]),
                    "tickets": int(r["tickets"]),
                })
        except Exception:
            pass
    try:
        pipeline = [
            {"$match": {"status": {"$in": ["PAID", "RESERVED"]}}},
            {"$lookup": {"from": "flights", "localField": "flight_id",
                         "foreignField": "flight_id", "as": "f"}},
            {"$unwind": "$f"},
            {"$group": {
                "_id": {"origin": "$f.origin", "destination": "$f.destination"},
                "revenue": {"$sum": "$total_price"},
                "tickets": {"$sum": 1},
            }},
            {"$sort": {"revenue": -1}},
            {"$limit": limit},
        ]
        async for doc in mongo_db.tickets.aggregate(pipeline):
            results.append({
                "route":       f"{doc['_id']['origin']}→{doc['_id']['destination']}",
                "origin":      doc["_id"]["origin"],
                "destination": doc["_id"]["destination"],
                "revenue":     float(doc["revenue"]),
                "tickets":     int(doc["tickets"]),
            })
    except Exception:
        pass

    # Combinar rutas duplicadas entre nodos
    merged: Dict[str, dict] = {}
    for r in results:
        key = r["route"]
        if key in merged:
            merged[key]["revenue"] += r["revenue"]
            merged[key]["tickets"] += r["tickets"]
        else:
            merged[key] = dict(r)

    sorted_routes = sorted(merged.values(), key=lambda x: x["revenue"], reverse=True)
    for r in sorted_routes:
        r["revenue"] = round(r["revenue"], 2)
    return sorted_routes[:limit]


# ─── Top flights por ocupación ────────────────────────────────────────────────

@app.get("/dashboard/top-flights")
async def top_flights(
    limit: int = Query(5, le=20),
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Top N vuelos por porcentaje de ocupación."""
    results: List[dict] = []
    sql = f"""
        SELECT TOP({limit})
            f.flight_id, f.origin, f.destination, f.departure_epoch,
            f.flight_number,
            COUNT(s.seat_id)                                                AS total_seats,
            SUM(CASE WHEN s.status IN ('SOLD','RESERVED') THEN 1 ELSE 0 END) AS occupied,
            ISNULL(SUM(CASE WHEN t.status IN ('PAID','RESERVED') THEN t.total_price ELSE 0 END), 0)
                                                                            AS revenue
        FROM dbo.flights f
        JOIN dbo.seats s ON f.flight_id = s.flight_id
        LEFT JOIN dbo.tickets t ON t.flight_id = f.flight_id
                               AND t.status IN ('PAID','RESERVED')
        GROUP BY f.flight_id, f.origin, f.destination, f.departure_epoch, f.flight_number
        HAVING COUNT(s.seat_id) > 0
        ORDER BY CAST(SUM(CASE WHEN s.status IN ('SOLD','RESERVED') THEN 1 ELSE 0 END) AS FLOAT)
                 / COUNT(s.seat_id) DESC
    """
    for db in [db1, db2]:
        try:
            rows = db.execute(text(sql)).mappings().all()
            for r in rows:
                total = int(r["total_seats"] or 1)
                occ   = int(r["occupied"] or 0)
                results.append({
                    "flight_id":       int(r["flight_id"]),
                    "flight_number":   r.get("flight_number", ""),
                    "origin":          r["origin"],
                    "destination":     r["destination"],
                    "date_epoch":      int(r["departure_epoch"] or 0),
                    "occupancy_pct":   round(occ / total * 100, 1),
                    "revenue":         round(float(r["revenue"]), 2),
                    "occupied_seats":  occ,
                    "total_seats":     total,
                })
        except Exception:
            pass
    try:
        pipeline = [
            {"$lookup": {"from": "seats", "localField": "flight_id",
                         "foreignField": "flight_id", "as": "seats"}},
            {"$addFields": {
                "total_seats": {"$size": "$seats"},
                "occupied":    {"$size": {"$filter": {
                    "input": "$seats",
                    "cond":  {"$in": ["$$this.status", ["SOLD", "RESERVED"]]},
                }}},
            }},
            {"$match": {"total_seats": {"$gt": 0}}},
            {"$addFields": {"occupancy_pct": {
                "$multiply": [{"$divide": ["$occupied", "$total_seats"]}, 100]
            }}},
            {"$sort": {"occupancy_pct": -1}},
            {"$limit": limit},
        ]
        async for doc in mongo_db.flights.aggregate(pipeline):
            results.append({
                "flight_id":     int(doc["flight_id"]),
                "flight_number": doc.get("flight_number", ""),
                "origin":        doc.get("origin", ""),
                "destination":   doc.get("destination", ""),
                "date_epoch":    int(doc.get("departure_epoch") or 0),
                "occupancy_pct": round(float(doc.get("occupancy_pct", 0)), 1),
                "revenue":       0.0,
                "occupied_seats":int(doc.get("occupied", 0)),
                "total_seats":   int(doc.get("total_seats", 0)),
            })
    except Exception:
        pass

    results.sort(key=lambda x: x["occupancy_pct"], reverse=True)
    return results[:limit]


# ─── Fleet status ─────────────────────────────────────────────────────────────

@app.get("/dashboard/fleet-status")
async def fleet_status(
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Estado de los 50 aviones: ocupación por aeronave."""
    # Base: generar los 50 aviones con sus specs
    fleet = []
    for model_key, spec in AIRCRAFT_SPECS.items():
        for ac_id in spec["aircraft_ids"]:
            fleet.append({
                "aircraft_id":   ac_id,
                "model":         spec["model"],
                "manufacturer":  spec["manufacturer"],
                "total_seats":   spec["total_seats"],
                "primera_clase": spec["primera_clase"],
                "turista":       spec["turista"],
                "sold":          0,
                "reserved":      0,
                "available":     0,
                "locked":        0,
                "occupancy_pct": 0.0,
            })

    fleet_by_id = {a["aircraft_id"]: a for a in fleet}

    sql = """
        SELECT a.aircraft_id,
               SUM(CASE WHEN s.status='SOLD'      THEN 1 ELSE 0 END) AS sold,
               SUM(CASE WHEN s.status='RESERVED'  THEN 1 ELSE 0 END) AS reserved,
               SUM(CASE WHEN s.status='AVAILABLE' THEN 1 ELSE 0 END) AS available,
               SUM(CASE WHEN s.status='LOCKED'    THEN 1 ELSE 0 END) AS locked
        FROM dbo.aircraft a
        JOIN dbo.flights f  ON f.aircraft_id = a.aircraft_id
        JOIN dbo.seats   s  ON s.flight_id   = f.flight_id
        GROUP BY a.aircraft_id
    """
    for db in [db1, db2]:
        try:
            rows = db.execute(text(sql)).mappings().all()
            for r in rows:
                aid = int(r["aircraft_id"])
                if aid in fleet_by_id:
                    a = fleet_by_id[aid]
                    a["sold"]      += int(r["sold"] or 0)
                    a["reserved"]  += int(r["reserved"] or 0)
                    a["available"] += int(r["available"] or 0)
                    a["locked"]    += int(r["locked"] or 0)
        except Exception:
            pass

    # Calcular ocupación
    for a in fleet:
        total = a["total_seats"]
        if total > 0:
            a["occupancy_pct"] = round((a["sold"] + a["reserved"]) / total * 100, 1)

    return sorted(fleet, key=lambda x: x["aircraft_id"])


# ─── Sync — proxy a ms-sync ───────────────────────────────────────────────────

@app.get("/dashboard/sync/status")
async def dashboard_sync_status():
    """Re-exporta el estado de sincronización de ms-sync."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{MS_SYNC_URL}/sync/status")
            return resp.json()
    except Exception as e:
        return {
            "error": f"ms-sync no disponible: {str(e)}",
            "node_id": NODE_ID,
            "timestamp": int(time.time()),
        }


@app.get("/dashboard/sync/log")
async def dashboard_sync_log(limit: int = Query(20, le=200)):
    """Re-exporta el log de sincronización de ms-sync."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{MS_SYNC_URL}/sync/log", params={"limit": limit})
            return resp.json()
    except Exception as e:
        return {
            "logs": [],
            "error": f"ms-sync no disponible: {str(e)}",
            "timestamp": int(time.time()),
        }


# ─── Compras por ciudad ───────────────────────────────────────────────────────

@app.get("/dashboard/purchases-by-city")
async def purchases_by_city(
    limit: int = Query(20, le=100),
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Agregación de compras por ciudad de compra para el mapa Leaflet."""
    results: List[dict] = []

    # Intentar con columna purchase_city si existe, si no usar origin del vuelo
    sql_city = f"""
        SELECT TOP({limit}) purchase_city AS city,
               COUNT(*) AS count,
               SUM(total_price) AS revenue
        FROM dbo.tickets
        WHERE status IN ('PAID','RESERVED') AND purchase_city IS NOT NULL
        GROUP BY purchase_city
        ORDER BY count DESC
    """
    sql_origin = f"""
        SELECT TOP({limit}) f.origin AS city,
               COUNT(t.ticket_id) AS count,
               ISNULL(SUM(t.total_price), 0) AS revenue
        FROM dbo.tickets t
        JOIN dbo.flights f ON t.flight_id = f.flight_id
        WHERE t.status IN ('PAID','RESERVED')
        GROUP BY f.origin
        ORDER BY count DESC
    """

    for db in [db1, db2]:
        for sql in [sql_city, sql_origin]:
            try:
                rows = db.execute(text(sql)).mappings().all()
                if rows:
                    for r in rows:
                        results.append({
                            "city":    r["city"] or "Unknown",
                            "count":   int(r["count"]),
                            "revenue": round(float(r["revenue"] or 0), 2),
                        })
                    break  # si city funcionó, no seguir con origin
            except Exception:
                continue

    # MongoDB
    try:
        for pipeline in [
            # Intento con purchase_city
            [
                {"$match": {"status": {"$in": ["PAID", "RESERVED"]}, "purchase_city": {"$exists": True}}},
                {"$group": {"_id": "$purchase_city", "count": {"$sum": 1}, "revenue": {"$sum": "$total_price"}}},
                {"$sort": {"count": -1}}, {"$limit": limit},
            ],
            # Fallback: origin del vuelo
            [
                {"$match": {"status": {"$in": ["PAID", "RESERVED"]}}},
                {"$lookup": {"from": "flights", "localField": "flight_id",
                             "foreignField": "flight_id", "as": "f"}},
                {"$unwind": "$f"},
                {"$group": {"_id": "$f.origin", "count": {"$sum": 1}, "revenue": {"$sum": "$total_price"}}},
                {"$sort": {"count": -1}}, {"$limit": limit},
            ],
        ]:
            docs = await mongo_db.tickets.aggregate(pipeline).to_list(limit)
            if docs:
                for d in docs:
                    results.append({
                        "city":    d["_id"] or "Unknown",
                        "count":   int(d["count"]),
                        "revenue": round(float(d["revenue"] or 0), 2),
                    })
                break
    except Exception:
        pass

    # Consolidar
    merged: Dict[str, dict] = {}
    for r in results:
        k = r["city"]
        if k in merged:
            merged[k]["count"]   += r["count"]
            merged[k]["revenue"] += r["revenue"]
        else:
            merged[k] = dict(r)

    return sorted(merged.values(), key=lambda x: x["count"], reverse=True)[:limit]


# ─── Reservas próximas a expirar ──────────────────────────────────────────────

@app.get("/dashboard/reservations-expiring")
async def reservations_expiring(
    hours: int = Query(2, le=24),
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Reservas que expiran en las próximas X horas."""
    now  = int(time.time())
    until = now + hours * 3600

    results: List[dict] = []
    sql = """
        SELECT t.ticket_id, t.seat_id, t.flight_id, t.expiry_epoch,
               p.full_name AS passenger_name, p.passport_number,
               f.origin, f.destination, f.departure_epoch,
               s.seat_number
        FROM dbo.tickets t
        JOIN dbo.passengers p ON t.passenger_id = p.passenger_id
        JOIN dbo.flights    f ON t.flight_id    = f.flight_id
        JOIN dbo.seats      s ON t.seat_id      = s.seat_id
        WHERE t.status = 'RESERVED'
          AND t.expiry_epoch BETWEEN :now AND :until
        ORDER BY t.expiry_epoch ASC
    """
    for db in [db1, db2]:
        try:
            rows = db.execute(text(sql), {"now": now, "until": until}).mappings().all()
            results.extend([dict(r) for r in rows])
        except Exception:
            pass
    try:
        async for doc in mongo_db.tickets.aggregate([
            {"$match": {"status": "RESERVED", "expiry_epoch": {"$gte": now, "$lte": until}}},
            {"$lookup": {"from": "passengers", "localField": "passenger_id",
                         "foreignField": "passenger_id", "as": "pax"}},
            {"$lookup": {"from": "flights", "localField": "flight_id",
                         "foreignField": "flight_id", "as": "flt"}},
            {"$lookup": {"from": "seats", "localField": "seat_id",
                         "foreignField": "seat_id", "as": "st"}},
            {"$unwind": {"path": "$pax", "preserveNullAndEmptyArrays": True}},
            {"$unwind": {"path": "$flt", "preserveNullAndEmptyArrays": True}},
            {"$unwind": {"path": "$st",  "preserveNullAndEmptyArrays": True}},
            {"$project": {"_id": 0}},
            {"$sort": {"expiry_epoch": 1}},
        ]):
            results.append({
                "ticket_id":      doc["ticket_id"],
                "seat_id":        doc["seat_id"],
                "flight_id":      doc["flight_id"],
                "expiry_epoch":   doc.get("expiry_epoch"),
                "passenger_name": (doc.get("pax") or {}).get("full_name", ""),
                "passport_number":(doc.get("pax") or {}).get("passport_number", ""),
                "origin":         (doc.get("flt") or {}).get("origin", ""),
                "destination":    (doc.get("flt") or {}).get("destination", ""),
                "seat_number":    (doc.get("st")  or {}).get("seat_number", ""),
            })
    except Exception:
        pass

    results.sort(key=lambda x: x.get("expiry_epoch") or 0)
    return results


# ─── Ficha técnica de aeronave ────────────────────────────────────────────────

@app.get("/dashboard/aircraft/{model}")
async def aircraft_specs(model: str):
    """Ficha técnica completa de un modelo de avión."""
    key = MODEL_ALIASES.get(model.lower().replace(" ", "-"), model.upper())
    spec = AIRCRAFT_SPECS.get(key) or AIRCRAFT_SPECS.get(model.upper())
    if not spec:
        return {
            "error": f"Modelo '{model}' no encontrado",
            "available": list(AIRCRAFT_SPECS.keys()),
        }
    return {
        **spec,
        "total_in_fleet": len(spec["aircraft_ids"]),
        "capacity_info": {
            "primera_clase": spec["primera_clase"],
            "turista":       spec["turista"],
            "total":         spec["total_seats"],
        },
    }


# ─── Endpoints legacy (mantener compatibilidad) ───────────────────────────────

@app.get("/dashboard/summary")
async def dashboard_summary(
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """[Legacy] Resumen global. Usar /dashboard/overview."""
    return await dashboard_overview(db1=db1, db2=db2)


@app.get("/dashboard/popular-routes")
async def popular_routes(
    limit: int = Query(10, le=50),
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """[Legacy] Top rutas. Usar /dashboard/revenue-by-route."""
    return await revenue_by_route(limit=limit, db1=db1, db2=db2)


@app.get("/dashboard/aircraft-occupancy")
async def aircraft_occupancy(
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """[Legacy] Ocupación por modelo."""
    return await fleet_status(db1=db1, db2=db2)


@app.get("/dashboard/revenue")
async def revenue_by_node(
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Desglose de ingresos por nodo y clase de asiento."""
    results = []
    sql = text("""
        SELECT s.seat_class,
               COUNT(t.ticket_id)    AS tickets,
               ISNULL(SUM(t.total_price), 0)  AS revenue,
               ISNULL(AVG(t.total_price), 0)  AS avg_price
        FROM dbo.tickets t
        JOIN dbo.seats s ON t.seat_id = s.seat_id
        WHERE t.status IN ('PAID','RESERVED')
        GROUP BY s.seat_class
    """)
    for node_id, db in [(1, db1), (2, db2)]:
        try:
            rows = db.execute(sql).mappings().all()
            for r in rows:
                results.append({"node_id": node_id, **dict(r)})
        except Exception:
            pass
    return results


@app.get("/dashboard/flights-by-status")
async def flights_by_status(
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    agg: dict = {}
    for db in [db1, db2]:
        try:
            rows = db.execute(text(
                "SELECT status, COUNT(*) as cnt FROM dbo.flights GROUP BY status"
            )).fetchall()
            for status, cnt in rows:
                agg[status] = agg.get(status, 0) + cnt
        except Exception:
            pass
    try:
        async for doc in mongo_db.flights.aggregate([{"$group": {"_id": "$status", "cnt": {"$sum": 1}}}]):
            agg[doc["_id"]] = agg.get(doc["_id"], 0) + doc["cnt"]
    except Exception:
        pass
    return [{"status": k, "count": v} for k, v in agg.items()]
