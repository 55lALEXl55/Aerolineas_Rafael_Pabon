"""
ms-routes — Puerto 8003
Algoritmos de rutas: Dijkstra puro (sin librerías) + TSP nearest-neighbor + 2-opt.
Regla CLAUDE.md: precio primero, tiempo segundo.
Consulta ms-flights para verificar disponibilidad real de vuelos.
CAP: AP — si ms-flights no responde, retorna ruta teórica.
"""
import asyncio
import heapq
import os
import time
from typing import List, Optional, Dict, Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db1, get_db2, mongo_db

app = FastAPI(
    title="ms-routes",
    description="Microservicio de rutas — Dijkstra + TSP — Aerolíneas Rafael Pabón",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NODE_ID = int(os.getenv("NODE_ID", "1"))
MS_FLIGHTS_URL = os.getenv("MS_FLIGHTS_URL", "http://ms-flights:8001")

# ─── Datos de aeropuertos ─────────────────────────────────────────────────────

AIRPORTS = {
    "ATL": {"name": "Atlanta Hartsfield–Jackson",   "city": "Atlanta",     "country": "US", "region": "America",     "lat": 33.64,  "lon": -84.43},
    "LAX": {"name": "Los Angeles International",    "city": "Los Angeles", "country": "US", "region": "America",     "lat": 33.94,  "lon": -118.41},
    "DFW": {"name": "Dallas/Fort Worth",            "city": "Dallas",      "country": "US", "region": "America",     "lat": 32.90,  "lon": -97.04},
    "SAO": {"name": "São Paulo Guarulhos",          "city": "São Paulo",   "country": "BR", "region": "America",     "lat": -23.43, "lon": -46.47},
    "LON": {"name": "London Heathrow",              "city": "London",      "country": "GB", "region": "Europe",      "lat": 51.48,  "lon": -0.46},
    "PAR": {"name": "Paris Charles de Gaulle",      "city": "Paris",       "country": "FR", "region": "Europe",      "lat": 49.01,  "lon": 2.55},
    "FRA": {"name": "Frankfurt Main",               "city": "Frankfurt",   "country": "DE", "region": "Europe",      "lat": 50.04,  "lon": 8.55},
    "IST": {"name": "Istanbul Airport",             "city": "Istanbul",    "country": "TR", "region": "Europe",      "lat": 41.26,  "lon": 28.74},
    "MAD": {"name": "Madrid Barajas",               "city": "Madrid",      "country": "ES", "region": "Europe",      "lat": 40.47,  "lon": -3.57},
    "AMS": {"name": "Amsterdam Schiphol",           "city": "Amsterdam",   "country": "NL", "region": "Europe",      "lat": 52.31,  "lon": 4.77},
    "DXB": {"name": "Dubai International",          "city": "Dubai",       "country": "AE", "region": "Middle East", "lat": 25.25,  "lon": 55.36},
    "PEK": {"name": "Beijing Capital",              "city": "Beijing",     "country": "CN", "region": "Asia",        "lat": 40.08,  "lon": 116.58},
    "TYO": {"name": "Tokyo Haneda",                 "city": "Tokyo",       "country": "JP", "region": "Asia",        "lat": 35.55,  "lon": 139.78},
    "SIN": {"name": "Singapore Changi",             "city": "Singapore",   "country": "SG", "region": "Asia",        "lat": 1.36,   "lon": 103.99},
    "CAN": {"name": "Guangzhou Baiyun",             "city": "Guangzhou",   "country": "CN", "region": "Asia",        "lat": 23.39,  "lon": 113.30},
}

# ─── Matrices de costos ───────────────────────────────────────────────────────

COST_MATRIX: Dict[str, Dict[str, float]] = {
    "ATL": {"TYO":1400,"LAX":400,"LON":700,"PAR":750,"FRA":800,"IST":950,"SIN":1500,"MAD":800,"AMS":780,"DFW":200,"DXB":1100,"SAO":900,"PEK":1350,"CAN":1400},
    "PEK": {"DXB":700,"TYO":500,"LON":900,"PAR":950,"FRA":850,"IST":900,"SIN":600,"MAD":950,"AMS":900,"CAN":200,"SAO":1700,"ATL":1350,"LAX":1100,"DFW":1300},
    "DXB": {"PEK":700,"TYO":750,"LON":650,"LAX":1300,"PAR":700,"FRA":600,"IST":400,"SIN":600,"MAD":750,"AMS":650,"DFW":1200,"CAN":650,"SAO":1400,"ATL":1100},
    "TYO": {"ATL":1400,"PEK":500,"DXB":750,"LON":1000,"LAX":900,"PAR":1050,"FRA":950,"IST":900,"SIN":700,"MAD":1100,"AMS":1000,"CAN":550,"SAO":1800,"DFW":1300},
    "LON": {"ATL":700,"DXB":650,"TYO":1000,"LAX":800,"PAR":150,"FRA":200,"IST":400,"MAD":200,"AMS":150,"DFW":750,"CAN":950,"SAO":1100,"PEK":900,"SIN":950},
    "LAX": {"ATL":400,"PEK":1100,"DXB":1300,"TYO":900,"LON":800,"PAR":850,"FRA":900,"IST":1100,"SIN":1400,"MAD":900,"AMS":850,"DFW":300,"CAN":1150,"SAO":1000},
    "PAR": {"ATL":750,"DXB":700,"TYO":1050,"LAX":850,"LON":150,"FRA":150,"IST":450,"MAD":200,"AMS":180,"CAN":950,"SAO":1050,"PEK":950,"SIN":950,"DFW":800},
    "FRA": {"PEK":850,"DXB":600,"TYO":950,"LON":200,"LAX":900,"PAR":150,"IST":350,"CAN":850,"SAO":900,"ATL":800,"MAD":250,"AMS":200,"SIN":950,"DFW":800},
    "IST": {"DXB":400,"TYO":900,"FRA":350,"LON":400,"PAR":450,"SIN":800,"MAD":500,"AMS":450,"DFW":1000,"CAN":800,"SAO":1200,"PEK":900,"ATL":950,"LAX":1100},
    "SIN": {"PEK":600,"DXB":600,"TYO":700,"LON":950,"LAX":1400,"PAR":950,"FRA":950,"IST":800,"MAD":1000,"AMS":950,"CAN":500,"ATL":1500,"DFW":1600,"SAO":1800},
    "MAD": {"DXB":750,"LON":200,"PAR":200,"FRA":250,"IST":500,"SIN":1000,"AMS":200,"DFW":850,"CAN":950,"SAO":1000,"PEK":950,"TYO":1100,"ATL":800,"LAX":900},
    "AMS": {"ATL":780,"PEK":900,"DXB":650,"TYO":1000,"LON":150,"LAX":850,"PAR":180,"FRA":200,"IST":450,"MAD":200,"DFW":800,"CAN":900,"SAO":1050,"SIN":950},
    "DFW": {"ATL":200,"DXB":1200,"LAX":300,"LON":750,"PAR":800,"FRA":800,"IST":1000,"MAD":850,"AMS":800,"CAN":1200,"SAO":950,"PEK":1300,"TYO":1300,"SIN":1600},
    "CAN": {"PEK":200,"DXB":650,"TYO":550,"LON":950,"LAX":1150,"PAR":950,"FRA":850,"IST":800,"SIN":500,"MAD":950,"AMS":900,"DFW":1200,"SAO":1700,"ATL":1400},
    "SAO": {"ATL":900,"PEK":1700,"DXB":1400,"TYO":1800,"LON":1100,"LAX":1000,"PAR":1050,"FRA":900,"IST":1200,"SIN":1800,"MAD":1000,"AMS":1050,"DFW":950,"CAN":1700},
}

TIME_MATRIX: Dict[str, Dict[str, float]] = {
    "ATL": {"PEK":15,"DXB":14,"TYO":16,"LON":8,"LAX":5,"PAR":9,"FRA":9,"IST":11,"SIN":18,"MAD":8,"AMS":9,"DFW":2,"CAN":16,"SAO":9},
    "PEK": {"DXB":8,"TYO":3,"LON":10,"LAX":12,"PAR":11,"FRA":10,"IST":9,"SIN":6,"MAD":12,"AMS":10,"DFW":14,"CAN":3,"SAO":22,"ATL":15},
    "DXB": {"PEK":8,"TYO":10,"LON":7,"LAX":16,"PAR":7,"FRA":7,"IST":4,"SIN":7,"MAD":8,"AMS":7,"DFW":15,"CAN":8,"SAO":15,"ATL":14},
    "TYO": {"ATL":16,"PEK":3,"DXB":10,"LON":12,"LAX":11,"PAR":13,"FRA":12,"IST":11,"SIN":7,"MAD":14,"AMS":12,"DFW":13,"CAN":4,"SAO":24},
    "LON": {"ATL":8,"DXB":7,"TYO":12,"LAX":11,"PAR":1,"FRA":1,"IST":4,"SIN":13,"MAD":2,"AMS":1,"DFW":10,"CAN":11,"SAO":12,"PEK":10},
    "LAX": {"ATL":5,"PEK":12,"DXB":16,"TYO":11,"LON":11,"PAR":11,"FRA":11,"IST":13,"SIN":17,"MAD":11,"AMS":11,"DFW":3,"CAN":14,"SAO":12},
    "PAR": {"ATL":9,"DXB":7,"TYO":13,"LON":1,"LAX":11,"FRA":1,"IST":3,"SIN":13,"MAD":2,"AMS":1,"DFW":10,"CAN":11,"SAO":12,"PEK":11},
    "FRA": {"ATL":9,"PEK":10,"DXB":7,"TYO":12,"LON":1,"LAX":11,"PAR":1,"IST":3,"SIN":12,"MAD":2,"AMS":1,"DFW":10,"CAN":10,"SAO":12},
    "IST": {"ATL":11,"PEK":9,"DXB":4,"TYO":11,"LON":4,"LAX":13,"PAR":3,"FRA":3,"SIN":10,"MAD":4,"AMS":3,"DFW":12,"CAN":9,"SAO":13},
    "SIN": {"PEK":6,"DXB":7,"TYO":7,"LON":13,"LAX":17,"PAR":13,"FRA":12,"IST":10,"MAD":14,"AMS":13,"DFW":17,"CAN":4,"ATL":18,"SAO":25},
    "MAD": {"ATL":8,"DXB":8,"TYO":14,"LON":2,"LAX":11,"PAR":2,"FRA":2,"IST":4,"SIN":14,"AMS":2,"DFW":10,"CAN":12,"SAO":10,"PEK":12},
    "AMS": {"ATL":9,"PEK":10,"DXB":7,"TYO":12,"LON":1,"LAX":11,"PAR":1,"FRA":1,"IST":3,"SIN":13,"MAD":2,"DFW":10,"CAN":10,"SAO":12},
    "DFW": {"ATL":2,"DXB":15,"TYO":13,"LON":10,"LAX":3,"PAR":10,"FRA":10,"IST":12,"SIN":17,"MAD":10,"AMS":10,"CAN":15,"SAO":10,"PEK":14},
    "CAN": {"PEK":3,"DXB":8,"TYO":4,"LON":11,"LAX":14,"PAR":11,"FRA":10,"IST":9,"SIN":4,"MAD":12,"AMS":10,"DFW":15,"SAO":23,"ATL":16},
    "SAO": {"ATL":9,"PEK":22,"DXB":15,"TYO":24,"LON":12,"LAX":12,"PAR":12,"FRA":12,"IST":13,"SIN":25,"MAD":10,"AMS":12,"DFW":10,"CAN":23},
}


# ─── Dijkstra puro (sin librerías externas) ───────────────────────────────────

def dijkstra(graph: Dict[str, Dict[str, float]], start: str, end: str) -> tuple[float, List[str]]:
    """
    Dijkstra estándar sobre diccionario de adyacencia.
    Retorna (distancia, path). Si no hay ruta: (inf, []).
    """
    if start not in graph or end not in graph:
        return float("inf"), []

    distances: Dict[str, float] = {node: float("inf") for node in graph}
    distances[start] = 0.0
    predecessors: Dict[str, Optional[str]] = {node: None for node in graph}
    pq: List[tuple[float, str]] = [(0.0, start)]

    while pq:
        current_dist, current = heapq.heappop(pq)
        if current_dist > distances[current]:
            continue
        if current == end:
            break
        for neighbor, weight in graph.get(current, {}).items():
            if neighbor not in distances:
                distances[neighbor] = float("inf")
                predecessors[neighbor] = None
            dist = current_dist + weight
            if dist < distances[neighbor]:
                distances[neighbor] = dist
                predecessors[neighbor] = current
                heapq.heappush(pq, (dist, neighbor))

    # Reconstruir camino
    if distances[end] == float("inf"):
        return float("inf"), []

    path: List[str] = []
    node: Optional[str] = end
    while node is not None:
        path.append(node)
        node = predecessors.get(node)
    path.reverse()
    return distances[end], path


def dijkstra_all(graph: Dict[str, Dict[str, float]], start: str) -> Dict[str, tuple[float, List[str]]]:
    """
    Dijkstra desde un nodo fuente a TODOS los demás.
    Retorna dict: destino → (distancia, path).
    """
    all_nodes = set(graph.keys())
    for neighbors in graph.values():
        all_nodes.update(neighbors.keys())

    distances: Dict[str, float] = {node: float("inf") for node in all_nodes}
    distances[start] = 0.0
    predecessors: Dict[str, Optional[str]] = {node: None for node in all_nodes}
    pq: List[tuple[float, str]] = [(0.0, start)]

    while pq:
        current_dist, current = heapq.heappop(pq)
        if current_dist > distances[current]:
            continue
        for neighbor, weight in graph.get(current, {}).items():
            dist = current_dist + weight
            if dist < distances[neighbor]:
                distances[neighbor] = dist
                predecessors[neighbor] = current
                heapq.heappush(pq, (dist, neighbor))

    # Reconstruir todos los caminos
    results: Dict[str, tuple[float, List[str]]] = {}
    for dest in all_nodes:
        if dest == start or distances[dest] == float("inf"):
            continue
        path: List[str] = []
        node: Optional[str] = dest
        while node is not None:
            path.append(node)
            node = predecessors.get(node)
        path.reverse()
        results[dest] = (distances[dest], path)
    return results


# ─── TSP: Nearest Neighbor + 2-opt ───────────────────────────────────────────

def _route_cost(path: List[str], matrix: Dict[str, Dict[str, float]]) -> float:
    total = 0.0
    for i in range(len(path) - 1):
        total += matrix.get(path[i], {}).get(path[i + 1], 9999.0)
    return total


def nearest_neighbor_tsp(nodes: List[str], matrix: Dict[str, Dict[str, float]], start: str) -> List[str]:
    """
    Heurística del vecino más cercano para TSP.
    Empieza en `start`, visita todos los nodos, vuelve al inicio.
    """
    unvisited = set(nodes)
    tour = [start]
    unvisited.discard(start)

    while unvisited:
        current = tour[-1]
        nearest = min(
            unvisited,
            key=lambda n: matrix.get(current, {}).get(n, float("inf"))
        )
        tour.append(nearest)
        unvisited.discard(nearest)

    tour.append(start)  # Volver al origen
    return tour


def two_opt_improve(tour: List[str], matrix: Dict[str, Dict[str, float]]) -> List[str]:
    """
    Mejora del tour con 2-opt.
    Intercambia pares de aristas si la inversión del segmento reduce el costo.
    """
    best = tour[:]
    best_cost = _route_cost(best, matrix)
    improved = True

    while improved:
        improved = False
        n = len(best) - 1  # excluir el nodo de retorno
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                # Invertir segmento [i..j]
                candidate = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                cost = _route_cost(candidate, matrix)
                if cost < best_cost - 1e-9:
                    best = candidate
                    best_cost = cost
                    improved = True

    return best


# ─── Consultas a ms-flights ───────────────────────────────────────────────────

async def _get_flights_for_segment(
    origin: str, destination: str, date_epoch: int, seat_class: str = "ECONOMY"
) -> List[dict]:
    """Consulta ms-flights para obtener vuelos disponibles en un segmento."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{MS_FLIGHTS_URL}/flights/search",
                params={
                    "origin": origin,
                    "destination": destination,
                    "date_epoch": date_epoch,
                    "seat_class": seat_class,
                },
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return []  # CAP: AP — continuar sin vuelos reales


async def _enrich_path_with_flights(
    path: List[str], date_epoch: int, seat_class: str = "ECONOMY"
) -> tuple[bool, List[dict]]:
    """
    Para cada arista del path, busca el vuelo más barato disponible.
    Retorna (todos_disponibles, [flight_data_por_segmento]).
    """
    segment_flights = []
    tasks = [
        _get_flights_for_segment(path[i], path[i + 1], date_epoch, seat_class)
        for i in range(len(path) - 1)
    ]
    results = await asyncio.gather(*tasks)

    all_available = True
    for i, flights in enumerate(results):
        if not flights:
            all_available = False
            # Ruta teórica sin vuelo real
            segment_flights.append({
                "origin": path[i],
                "destination": path[i + 1],
                "available": False,
                "flights": [],
                "best_price": COST_MATRIX.get(path[i], {}).get(path[i + 1], 0),
                "duration_hours": TIME_MATRIX.get(path[i], {}).get(path[i + 1], 0),
            })
        else:
            # El más barato según seat_class
            key = "first_class_price" if seat_class == "FIRST" else "economy_price"
            best = min(flights, key=lambda f: f.get(key, 9999))
            segment_flights.append({
                "origin": path[i],
                "destination": path[i + 1],
                "available": True,
                "flights": flights[:3],  # Los 3 primeros para mostrar opciones
                "best_flight_id": best.get("flight_id"),
                "best_flight_number": best.get("flight_number"),
                "best_price": best.get(key, 0),
                "departure_epoch": best.get("flight_date_epoch"),
                "arrival_epoch": best.get("arrival_epoch"),
                "duration_hours": best.get("duration_hours", 0),
                "aircraft_model": best.get("aircraft_model"),
            })

    return all_available, segment_flights


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "service": "ms-routes",
        "status": "ok",
        "node_id": NODE_ID,
        "airports": len(AIRPORTS),
        "timestamp": int(time.time()),
    }


# ─── GET /routes/shortest ────────────────────────────────────────────────────

@app.get("/routes/shortest")
async def shortest_route(
    origin: str = Query(..., min_length=3, max_length=3),
    destination: str = Query(..., min_length=3, max_length=3),
    date_epoch: int = Query(...),
    mode: str = Query("price", regex="^(price|time)$"),
    seat_class: str = Query("ECONOMY", regex="^(FIRST|ECONOMY)$"),
):
    """
    Ruta óptima entre dos aeropuertos usando Dijkstra puro.
    Prioridad CLAUDE.md: precio primero, luego tiempo.
    Verifica disponibilidad real de vuelos en ms-flights.
    """
    o = origin.upper().strip()
    d = destination.upper().strip()

    if o not in COST_MATRIX:
        raise HTTPException(400, {"error": "AEROPUERTO_INVALIDO", "message": f"Origen '{o}' no reconocido"})
    if d not in COST_MATRIX and d not in {k for v in COST_MATRIX.values() for k in v}:
        raise HTTPException(400, {"error": "AEROPUERTO_INVALIDO", "message": f"Destino '{d}' no reconocido"})

    # Siempre calcular primero por precio (CLAUDE.md: prioridad precio)
    cost_dist, cost_path = dijkstra(COST_MATRIX, o, d)
    time_dist, time_path = dijkstra(TIME_MATRIX, o, d)

    if cost_dist == float("inf"):
        return {"routes": [], "message": "No hay ruta disponible entre estos aeropuertos"}

    # Según mode, ordenar las rutas
    if mode == "price":
        primary_path, primary_metric = cost_path, cost_dist
        secondary_path, secondary_metric = time_path, time_dist
    else:
        primary_path, primary_metric = time_path, time_dist
        secondary_path, secondary_metric = cost_path, cost_dist

    routes = []

    # Ruta primaria
    all_avail, segments = await _enrich_path_with_flights(primary_path, date_epoch, seat_class)
    total_price = sum(s.get("best_price", 0) for s in segments)
    total_hours = sum(s.get("duration_hours", 0) for s in segments)
    routes.append({
        "path": primary_path,
        "mode": mode,
        "available": all_avail,
        "total_cost_usd": total_price if all_avail else cost_dist,
        "total_hours": total_hours if all_avail else time_dist,
        "stops": len(primary_path) - 2,
        "segments": segments,
        "algorithm": "dijkstra",
    })

    # Si la ruta secundaria tiene distinto camino, incluirla
    if secondary_path != primary_path:
        all_avail2, segments2 = await _enrich_path_with_flights(secondary_path, date_epoch, seat_class)
        total_price2 = sum(s.get("best_price", 0) for s in segments2)
        total_hours2 = sum(s.get("duration_hours", 0) for s in segments2)
        routes.append({
            "path": secondary_path,
            "mode": "time" if mode == "price" else "price",
            "available": all_avail2,
            "total_cost_usd": total_price2 if all_avail2 else cost_dist,
            "total_hours": total_hours2 if all_avail2 else time_dist,
            "stops": len(secondary_path) - 2,
            "segments": segments2,
            "algorithm": "dijkstra",
        })

    return {
        "origin": o,
        "destination": d,
        "date_epoch": date_epoch,
        "seat_class": seat_class,
        "routes": routes,
    }


# ─── GET /routes/tsp ─────────────────────────────────────────────────────────

@app.get("/routes/tsp")
async def tsp_route(
    origin: str = Query(..., min_length=3, max_length=3),
    destinations: List[str] = Query(..., description="Lista de destinos a visitar"),
    mode: str = Query("price", regex="^(price|time)$"),
):
    """
    TSP con heurística Nearest Neighbor + mejora 2-opt.
    Encuentra el orden óptimo para visitar todos los destinos partiendo del origen.
    """
    all_nodes = [origin.upper()] + [d.upper() for d in destinations]
    all_nodes = list(dict.fromkeys(all_nodes))  # deduplicate preservando orden

    if len(all_nodes) < 2:
        raise HTTPException(400, {"error": "DESTINOS_INSUFICIENTES", "message": "Se necesitan al menos 2 aeropuertos"})

    matrix = COST_MATRIX if mode == "price" else TIME_MATRIX

    # Validar aeropuertos
    for airport in all_nodes:
        if airport not in AIRPORTS:
            raise HTTPException(400, {"error": "AEROPUERTO_INVALIDO", "message": f"'{airport}' no es un aeropuerto válido"})

    # Nearest Neighbor desde el origen
    tour = nearest_neighbor_tsp(all_nodes, matrix, start=all_nodes[0])

    # Mejora con 2-opt
    tour_improved = two_opt_improve(tour, matrix)

    # Calcular métricas
    total_cost = _route_cost(tour_improved, COST_MATRIX)
    total_hours = _route_cost(tour_improved, TIME_MATRIX)

    # Construir segmentos
    segments = []
    for i in range(len(tour_improved) - 1):
        a, b = tour_improved[i], tour_improved[i + 1]
        # Dijkstra entre cada par (puede haber escalas en la ruta teórica)
        seg_cost, seg_path = dijkstra(COST_MATRIX, a, b)
        seg_time, _ = dijkstra(TIME_MATRIX, a, b)
        segments.append({
            "origin": a,
            "destination": b,
            "path": seg_path,
            "cost_usd": COST_MATRIX.get(a, {}).get(b, seg_cost),
            "duration_hours": TIME_MATRIX.get(a, {}).get(b, seg_time),
            "origin_info": AIRPORTS.get(a, {}),
            "destination_info": AIRPORTS.get(b, {}),
        })

    # Costo antes de 2-opt para comparar mejora
    cost_before = _route_cost(tour, matrix)
    cost_after  = _route_cost(tour_improved, matrix)
    improvement_pct = round((cost_before - cost_after) / cost_before * 100, 2) if cost_before > 0 else 0

    return {
        "algorithm": "nearest_neighbor + 2-opt",
        "mode": mode,
        "origin": all_nodes[0],
        "tour": tour_improved,
        "total_cost_usd": round(total_cost, 2),
        "total_hours": round(total_hours, 2),
        "stops": len(tour_improved) - 2,
        "segments": segments,
        "optimization": {
            "initial_tour": tour,
            "initial_cost": round(cost_before, 2),
            "optimized_cost": round(cost_after, 2),
            "improvement_percent": improvement_pct,
        },
    }


# ─── GET /routes/available ───────────────────────────────────────────────────

@app.get("/routes/available")
async def available_destinations(
    origin: str = Query(..., min_length=3, max_length=3),
    date_epoch: int = Query(...),
    seat_class: str = Query("ECONOMY", regex="^(FIRST|ECONOMY)$"),
):
    """
    Lista todos los destinos alcanzables desde origin en date_epoch.
    Dijkstra desde el origen a todos los nodos, luego verifica disponibilidad.
    """
    o = origin.upper().strip()
    if o not in COST_MATRIX:
        raise HTTPException(400, {"error": "AEROPUERTO_INVALIDO", "message": f"'{o}' no reconocido"})

    # Dijkstra a todos los destinos (precio y tiempo)
    cost_results = dijkstra_all(COST_MATRIX, o)
    time_results = dijkstra_all(TIME_MATRIX, o)

    # Verificar disponibilidad directa (sin escala) en paralelo
    direct_neighbors = list(COST_MATRIX.get(o, {}).keys())
    flight_tasks = [
        _get_flights_for_segment(o, dest, date_epoch, seat_class)
        for dest in direct_neighbors
    ]
    flight_results = await asyncio.gather(*flight_tasks)
    direct_availability: Dict[str, List[dict]] = {
        dest: flights
        for dest, flights in zip(direct_neighbors, flight_results)
    }

    destinations = []
    for dest, (cost, path) in sorted(cost_results.items(), key=lambda x: x[1][0]):
        if dest not in AIRPORTS:
            continue
        time_cost = time_results.get(dest, (0, []))[0]
        is_direct = len(path) == 2
        direct_flights = direct_availability.get(dest, []) if is_direct else []

        key = "first_class_price" if seat_class == "FIRST" else "economy_price"
        if direct_flights:
            min_price = min(f.get(key, 9999) for f in direct_flights)
        else:
            min_price = cost

        destinations.append({
            "destination": dest,
            "airport_info": AIRPORTS.get(dest, {}),
            "path": path,
            "stops": len(path) - 2,
            "is_direct": is_direct,
            "min_price_usd": min_price,
            "duration_hours": time_cost,
            "theoretical_cost": cost,
            "direct_flights_count": len(direct_flights),
            "available": len(direct_flights) > 0 if is_direct else True,
        })

    return {
        "origin": o,
        "date_epoch": date_epoch,
        "seat_class": seat_class,
        "destinations": destinations,
        "total": len(destinations),
    }


# ─── GET /routes/top ─────────────────────────────────────────────────────────

@app.get("/routes/top")
async def top_routes(limit: int = Query(10, le=50)):
    """Top N rutas más solicitadas según tickets vendidos/reservados."""
    from database import Session1, Session2

    route_counts: Dict[str, int] = {}

    # Consultar DB1 y DB2
    for SessionCls in [Session1, Session2]:
        try:
            db = SessionCls()
            rows = db.execute(text("""
                SELECT RTRIM(f.origin) AS origin, RTRIM(f.destination) AS destination, COUNT(*) AS cnt
                FROM dbo.tickets t
                JOIN dbo.flights f ON f.flight_id = t.flight_id
                WHERE t.status IN ('RESERVED', 'PAID', 'REFUNDED')
                GROUP BY f.origin, f.destination
            """)).fetchall()
            for (orig, dest, cnt) in rows:
                key = f"{orig.strip()}-{dest.strip()}"
                route_counts[key] = route_counts.get(key, 0) + cnt
            db.close()
        except Exception:
            pass

    # Consultar DB3 (MongoDB)
    try:
        pipeline = [
            {"$match": {"status": {"$in": ["RESERVED", "PAID", "REFUNDED"]}}},
            {"$lookup": {
                "from": "flights",
                "localField": "flight_id",
                "foreignField": "flight_id",
                "as": "flight",
            }},
            {"$unwind": "$flight"},
            {"$group": {
                "_id": {"origin": "$flight.origin", "destination": "$flight.destination"},
                "count": {"$sum": 1},
            }},
        ]
        async for doc in mongo_db.tickets.aggregate(pipeline):
            key = f"{doc['_id']['origin']}-{doc['_id']['destination']}"
            route_counts[key] = route_counts.get(key, 0) + doc["count"]
    except Exception:
        pass

    # Ordenar y construir respuesta
    sorted_routes = sorted(route_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

    top = []
    for rank, (route_key, cnt) in enumerate(sorted_routes, 1):
        parts = route_key.split("-")
        if len(parts) != 2:
            continue
        orig, dest = parts
        cost_dist, cost_path = dijkstra(COST_MATRIX, orig, dest)
        time_dist, _ = dijkstra(TIME_MATRIX, orig, dest)
        top.append({
            "rank": rank,
            "origin": orig,
            "destination": dest,
            "origin_info": AIRPORTS.get(orig, {}),
            "destination_info": AIRPORTS.get(dest, {}),
            "bookings": cnt,
            "cheapest_path": cost_path,
            "min_cost_usd": cost_dist,
            "min_hours": time_dist,
            "stops": len(cost_path) - 2 if cost_dist < float("inf") else -1,
        })

    return {
        "top_routes": top,
        "total_tracked": len(route_counts),
        "generated_at": int(time.time()),
    }


# ─── Endpoints de compatibilidad ─────────────────────────────────────────────

@app.get("/routes/dijkstra")
async def dijkstra_legacy(
    origin: str = Query(...),
    destination: str = Query(...),
    weight: str = Query("cost"),
):
    """Compatibilidad con API anterior."""
    o, d = origin.upper(), destination.upper()
    matrix = COST_MATRIX if weight == "cost" else TIME_MATRIX
    dist, path = dijkstra(matrix, o, d)
    if dist == float("inf"):
        return {"error": "No hay ruta disponible", "origin": o, "destination": d}

    total_cost = sum(COST_MATRIX.get(path[i], {}).get(path[i+1], 0) for i in range(len(path)-1))
    total_time = sum(TIME_MATRIX.get(path[i], {}).get(path[i+1], 0) for i in range(len(path)-1))
    segments = [
        {"origin": path[i], "destination": path[i+1],
         "price_economy": COST_MATRIX.get(path[i], {}).get(path[i+1], 0),
         "duration_hours": TIME_MATRIX.get(path[i], {}).get(path[i+1], 0)}
        for i in range(len(path)-1)
    ]
    return {
        "algorithm": "dijkstra",
        "weight": weight,
        "path": path,
        "segments": segments,
        "total_cost_usd": total_cost,
        "total_duration_hours": total_time,
        "stops": len(path) - 2,
    }


@app.get("/routes/all-airports")
async def list_airports():
    return AIRPORTS


@app.get("/routes/cost-matrix")
async def get_cost_matrix():
    return {"cost_matrix": COST_MATRIX, "time_matrix": TIME_MATRIX}


@app.post("/routes/tsp")
async def tsp_legacy(airports: List[str]):
    """Compatibilidad con API anterior."""
    if len(airports) < 2:
        return {"error": "Se necesitan al menos 2 aeropuertos"}
    nodes = [a.upper() for a in airports]
    tour = nearest_neighbor_tsp(nodes, COST_MATRIX, start=nodes[0])
    tour_opt = two_opt_improve(tour, COST_MATRIX)
    total = _route_cost(tour_opt, COST_MATRIX)
    return {
        "algorithm": "tsp_nearest_neighbor_2opt",
        "path": tour_opt,
        "total_cost_usd": round(total, 2),
        "stops": len(tour_opt) - 2,
    }
