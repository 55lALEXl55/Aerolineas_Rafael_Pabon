"""
ms-dashboard — Puerto 8006
Dashboard gerencial: métricas en tiempo real de los 3 nodos.
Estadísticas de ocupación, ingresos, sincronización, rutas populares.
"""
import os
import time
from typing import List, Optional

from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db1, get_db2, mongo_db
from models import NodeStatus, RevenueStats, DashboardSummary

app = FastAPI(
    title="ms-dashboard",
    description="Dashboard gerencial — Aerolíneas Rafael Pabón",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NODE_ID = int(os.getenv("NODE_ID", "1"))


@app.get("/health")
async def health():
    return {"service": "ms-dashboard", "status": "ok", "node_id": NODE_ID, "timestamp": int(time.time())}


# ─── Resumen global ───────────────────────────────────────────────────────────

@app.get("/dashboard/summary")
async def dashboard_summary(
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Resumen global de los 3 nodos para el dashboard."""
    nodes = []
    total_flights = 0
    total_revenue = 0.0

    for node_id, db, region in [(1, db1, "América"), (2, db2, "Europa+MO")]:
        try:
            stats = db.execute(text("""
                SELECT
                    COUNT(DISTINCT f.flight_id)                             AS total_flights,
                    COUNT(s.seat_id)                                        AS total_seats,
                    SUM(CASE WHEN s.status='SOLD'      THEN 1 ELSE 0 END)  AS sold,
                    SUM(CASE WHEN s.status='AVAILABLE' THEN 1 ELSE 0 END)  AS available,
                    SUM(CASE WHEN s.status='RESERVED'  THEN 1 ELSE 0 END)  AS reserved
                FROM dbo.flights f
                LEFT JOIN dbo.seats s ON f.flight_id = s.flight_id
            """)).mappings().first()

            rev = db.execute(text("""
                SELECT ISNULL(SUM(total_price), 0) as revenue
                FROM dbo.tickets WHERE status IN ('PAID','RESERVED')
            """)).scalar()

            tf = stats["total_flights"] or 0
            ts = stats["total_seats"] or 0
            sold = stats["sold"] or 0
            avail = stats["available"] or 0
            resv = stats["reserved"] or 0
            rate = round(sold / ts * 100, 2) if ts > 0 else 0.0

            total_flights += tf
            total_revenue += float(rev or 0)

            nodes.append({
                "node_id": node_id,
                "region": region,
                "status": "online",
                "total_flights": tf,
                "total_seats": ts,
                "sold_seats": sold,
                "available_seats": avail,
                "reserved_seats": resv,
                "occupancy_rate": rate,
                "revenue": float(rev or 0),
            })
        except Exception as e:
            nodes.append({"node_id": node_id, "region": region, "status": "offline", "error": str(e)})

    # DB3 MongoDB
    try:
        tf3 = await mongo_db.flights.count_documents({})
        ts3 = await mongo_db.seats.count_documents({})
        sold3  = await mongo_db.seats.count_documents({"status": "SOLD"})
        avail3 = await mongo_db.seats.count_documents({"status": "AVAILABLE"})
        resv3  = await mongo_db.seats.count_documents({"status": "RESERVED"})
        rev3_docs = await mongo_db.tickets.aggregate([
            {"$match": {"status": {"$in": ["PAID", "RESERVED"]}}},
            {"$group": {"_id": None, "total": {"$sum": "$total_price"}}}
        ]).to_list(1)
        rev3 = rev3_docs[0]["total"] if rev3_docs else 0.0
        rate3 = round(sold3 / ts3 * 100, 2) if ts3 > 0 else 0.0
        total_flights += tf3
        total_revenue += rev3
        nodes.append({
            "node_id": 3,
            "region": "Asia+Oceanía",
            "status": "online",
            "total_flights": tf3,
            "total_seats": ts3,
            "sold_seats": sold3,
            "available_seats": avail3,
            "reserved_seats": resv3,
            "occupancy_rate": rate3,
            "revenue": rev3,
        })
    except Exception as e:
        nodes.append({"node_id": 3, "region": "Asia+Oceanía", "status": "offline", "error": str(e)})

    return {
        "total_flights": total_flights,
        "total_revenue_usd": round(total_revenue, 2),
        "nodes": nodes,
        "timestamp": int(time.time()),
    }


# ─── Rutas más populares ──────────────────────────────────────────────────────

@app.get("/dashboard/popular-routes")
async def popular_routes(
    limit: int = Query(10, le=50),
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Top rutas por número de tickets vendidos."""
    results = []
    sql = text(f"""
        SELECT TOP({limit}) f.origin, f.destination,
               COUNT(t.ticket_id) AS tickets_sold,
               SUM(t.total_price) AS revenue
        FROM dbo.tickets t
        JOIN dbo.flights f ON t.flight_id = f.flight_id
        WHERE t.status IN ('PAID','RESERVED')
        GROUP BY f.origin, f.destination
        ORDER BY tickets_sold DESC
    """)
    for db in [db1, db2]:
        try:
            rows = db.execute(sql).mappings().all()
            results.extend([dict(r) for r in rows])
        except Exception:
            pass
    try:
        pipeline = [
            {"$match": {"status": {"$in": ["PAID", "RESERVED"]}}},
            {"$lookup": {"from": "flights", "localField": "flight_id", "foreignField": "flight_id", "as": "flight"}},
            {"$unwind": "$flight"},
            {"$group": {"_id": {"origin": "$flight.origin", "destination": "$flight.destination"},
                        "tickets_sold": {"$sum": 1}, "revenue": {"$sum": "$total_price"}}},
            {"$sort": {"tickets_sold": -1}},
            {"$limit": limit},
        ]
        async for doc in mongo_db.tickets.aggregate(pipeline):
            results.append({
                "origin": doc["_id"]["origin"],
                "destination": doc["_id"]["destination"],
                "tickets_sold": doc["tickets_sold"],
                "revenue": doc["revenue"],
            })
    except Exception:
        pass

    results.sort(key=lambda x: x.get("tickets_sold", 0), reverse=True)
    return results[:limit]


# ─── Ocupación por aeronave ───────────────────────────────────────────────────

@app.get("/dashboard/aircraft-occupancy")
async def aircraft_occupancy(db1: Session = Depends(get_db1)):
    """Tasa de ocupación por modelo de aeronave."""
    try:
        rows = db1.execute(text("""
            SELECT a.model,
                   COUNT(s.seat_id)                                       AS total,
                   SUM(CASE WHEN s.status='SOLD' THEN 1 ELSE 0 END)      AS sold,
                   ROUND(100.0 * SUM(CASE WHEN s.status='SOLD' THEN 1 ELSE 0 END)
                         / NULLIF(COUNT(s.seat_id), 0), 2)               AS rate
            FROM dbo.aircraft a
            JOIN dbo.flights f ON f.aircraft_id = a.aircraft_id
            JOIN dbo.seats s ON s.flight_id = f.flight_id
            GROUP BY a.model
            ORDER BY rate DESC
        """)).mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        return {"error": str(e)}


# ─── Ingresos por nodo ────────────────────────────────────────────────────────

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
               SUM(t.total_price)    AS revenue,
               AVG(t.total_price)    AS avg_price
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


# ─── Vuelos por estado ────────────────────────────────────────────────────────

@app.get("/dashboard/flights-by-status")
async def flights_by_status(
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    agg: dict = {}
    for db in [db1, db2]:
        try:
            rows = db.execute(text("""
                SELECT status, COUNT(*) as cnt FROM dbo.flights GROUP BY status
            """)).fetchall()
            for status, cnt in rows:
                agg[status] = agg.get(status, 0) + cnt
        except Exception:
            pass
    try:
        pipeline = [{"$group": {"_id": "$status", "cnt": {"$sum": 1}}}]
        async for doc in mongo_db.flights.aggregate(pipeline):
            agg[doc["_id"]] = agg.get(doc["_id"], 0) + doc["cnt"]
    except Exception:
        pass
    return [{"status": k, "count": v} for k, v in agg.items()]
