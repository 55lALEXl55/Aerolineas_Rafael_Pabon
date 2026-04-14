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
from datetime import datetime, timezone
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

# ─── Matrices de costos (rutas REALES del dataset) ────────────────────────────
# None = sin ruta directa en el dataset. Solo 51 de 70 rutas posibles existen.

# Precio turista en USD por ruta directa
COST_ECONOMY: Dict[str, Dict[str, Optional[float]]] = {
    "ATL": {"TYO":1400,"LAX":400,"FRA":800,"SIN":1500,"MAD":800,"AMS":None,"DFW":200,"SAO":900,"LON":None,"PAR":None,"DXB":None,"IST":None,"PEK":None,"CAN":None},
    "PEK": {"DXB":700,"TYO":500,"LON":900,"PAR":950,"SIN":600,"MAD":950,"AMS":900,"DFW":1150,"CAN":None,"SAO":1700,"ATL":None,"LAX":None,"FRA":None,"IST":None},
    "DXB": {"PEK":700,"TYO":750,"LON":650,"LAX":1300,"PAR":700,"FRA":600,"IST":400,"SIN":600,"AMS":650,"DFW":1200,"SAO":1400,"ATL":None,"MAD":None,"CAN":None},
    "TYO": {"ATL":1400,"PEK":500,"DXB":750,"LON":1000,"LAX":900,"PAR":1050,"IST":900,"SIN":700,"MAD":1100,"DFW":1350,"FRA":None,"AMS":None,"CAN":None,"SAO":None},
    "LON": {"ATL":700,"DXB":650,"TYO":1000,"LAX":800,"PAR":150,"IST":400,"MAD":200,"AMS":150,"SAO":1100,"FRA":None,"DFW":None,"PEK":None,"SIN":None,"CAN":None},
    "LAX": {"ATL":400,"PEK":1100,"DXB":1300,"TYO":900,"PAR":850,"FRA":900,"IST":1100,"SIN":1400,"AMS":850,"DFW":300,"LON":None,"MAD":None,"CAN":None,"SAO":None},
    "PAR": {"ATL":750,"DXB":700,"TYO":1050,"LAX":850,"FRA":150,"IST":450,"MAD":200,"AMS":180,"SAO":1050,"LON":None,"PEK":None,"CAN":None,"DFW":None,"SIN":None},
    "FRA": {"PEK":850,"DXB":600,"TYO":950,"LON":200,"LAX":900,"PAR":150,"IST":350,"SIN":900,"DFW":850,"ATL":None,"MAD":None,"AMS":None,"CAN":None,"SAO":None},
    "IST": {"PEK":800,"DXB":400,"TYO":900,"FRA":350,"SIN":800,"MAD":500,"AMS":450,"DFW":1000,"SAO":1200,"ATL":None,"LON":None,"LAX":None,"PAR":None,"CAN":None},
    "SIN": {"PEK":600,"TYO":700,"LON":900,"PAR":950,"IST":800,"MAD":1000,"DFW":1400,"ATL":None,"DXB":None,"LAX":None,"FRA":None,"AMS":None,"CAN":None,"SAO":None},
    "MAD": {"DXB":750,"LAX":900,"PAR":200,"FRA":250,"IST":500,"SIN":1000,"AMS":200,"DFW":850,"SAO":1000,"ATL":None,"LON":None,"TYO":None,"PEK":None,"CAN":None},
    "AMS": {"ATL":780,"PEK":900,"DXB":650,"TYO":1000,"LON":150,"LAX":850,"IST":450,"MAD":200,"DFW":800,"SAO":1050,"FRA":None,"PAR":None,"SIN":None,"CAN":None},
    "DFW": {"ATL":200,"DXB":1200,"LAX":300,"PAR":800,"IST":1000,"MAD":850,"AMS":800,"CAN":1200,"SAO":950,"LON":None,"FRA":None,"TYO":None,"PEK":None,"SIN":None},
    "CAN": {"ATL":1250,"PEK":200,"DXB":650,"TYO":550,"LON":950,"LAX":1150,"PAR":950,"IST":800,"SIN":500,"AMS":900,"DFW":1200,"SAO":1700,"FRA":None,"MAD":None},
    "SAO": {"ATL":900,"DFW":950,"LON":None,"PEK":None,"DXB":None,"TYO":None,"LAX":None,"PAR":None,"FRA":None,"IST":None,"SIN":None,"MAD":None,"AMS":None,"CAN":None},
}

# Precio primera clase en USD
COST_FIRST: Dict[str, Dict[str, Optional[float]]] = {
    "ATL": {"TYO":1890,"LAX":540,"FRA":1080,"SIN":2025,"MAD":1080,"DFW":270,"SAO":1215,"AMS":None,"LON":None,"PAR":None,"DXB":None,"IST":None,"PEK":None,"CAN":None},
    "PEK": {"DXB":945,"TYO":675,"LON":1215,"PAR":1283,"SIN":810,"MAD":1283,"AMS":1215,"DFW":1553,"SAO":2295,"ATL":None,"LAX":None,"FRA":None,"IST":None,"CAN":None},
    "DXB": {"PEK":945,"TYO":1013,"LON":878,"LAX":1755,"PAR":945,"FRA":810,"IST":540,"SIN":810,"AMS":878,"DFW":1620,"SAO":1890,"ATL":None,"MAD":None,"CAN":None},
    "TYO": {"ATL":1890,"PEK":675,"DXB":1013,"LON":1350,"LAX":1215,"PAR":1418,"IST":1215,"SIN":945,"MAD":1485,"DFW":1823,"FRA":None,"AMS":None,"CAN":None,"SAO":None},
    "LON": {"ATL":945,"DXB":878,"TYO":1350,"LAX":1080,"PAR":203,"IST":540,"MAD":270,"AMS":203,"SAO":1485,"FRA":None,"DFW":None,"PEK":None,"SIN":None,"CAN":None},
    "LAX": {"ATL":540,"PEK":1485,"DXB":1755,"TYO":1215,"PAR":1148,"FRA":1215,"IST":4049,"SIN":1890,"AMS":1148,"DFW":405,"LON":None,"MAD":None,"CAN":None,"SAO":None},
    "PAR": {"ATL":1013,"DXB":945,"TYO":1418,"LAX":1148,"FRA":203,"IST":608,"MAD":270,"AMS":243,"SAO":1418,"LON":None,"PEK":None,"CAN":None,"DFW":None,"SIN":None},
    "FRA": {"PEK":1148,"DXB":810,"TYO":1283,"LON":270,"LAX":1215,"PAR":203,"IST":473,"SIN":1215,"DFW":1148,"ATL":None,"MAD":None,"AMS":None,"CAN":None,"SAO":None},
    "IST": {"PEK":1080,"DXB":540,"TYO":1215,"FRA":473,"SIN":1080,"MAD":675,"AMS":608,"DFW":1350,"SAO":1620,"ATL":None,"LON":None,"LAX":None,"PAR":None,"CAN":None},
    "SIN": {"PEK":810,"TYO":945,"LON":1215,"PAR":1283,"IST":1080,"MAD":1350,"DFW":1890,"ATL":None,"DXB":None,"LAX":None,"FRA":None,"AMS":None,"CAN":None,"SAO":None},
    "MAD": {"DXB":1013,"LAX":1215,"PAR":270,"FRA":338,"IST":675,"SIN":1350,"AMS":270,"DFW":1148,"SAO":1350,"ATL":None,"LON":None,"TYO":None,"PEK":None,"CAN":None},
    "AMS": {"ATL":1053,"PEK":1215,"DXB":878,"TYO":1350,"LON":203,"LAX":1148,"IST":608,"MAD":270,"DFW":1080,"SAO":1418,"FRA":None,"PAR":None,"SIN":None,"CAN":None},
    "DFW": {"ATL":270,"DXB":1620,"LAX":405,"PAR":1080,"IST":1350,"MAD":1148,"AMS":1080,"CAN":1620,"SAO":1283,"LON":None,"FRA":None,"TYO":None,"PEK":None,"SIN":None},
    "CAN": {"ATL":1688,"PEK":270,"DXB":878,"TYO":743,"LON":1283,"LAX":1553,"PAR":1283,"IST":1080,"SIN":675,"AMS":1215,"DFW":1620,"SAO":2295,"FRA":None,"MAD":None},
    "SAO": {"ATL":1215,"DFW":1283,"LON":None,"PEK":None,"DXB":None,"TYO":None,"LAX":None,"PAR":None,"FRA":None,"IST":None,"SIN":None,"MAD":None,"AMS":None,"CAN":None},
}

# Tiempo de vuelo en horas — simétrico, cubre todas las rutas
TIME_MATRIX: Dict[str, Dict[str, float]] = {
    "ATL": {"ATL":0,"PEK":15,"DXB":14,"TYO":16,"LON":8,"LAX":5,"PAR":9,"FRA":9,"IST":11,"SIN":18,"MAD":8,"AMS":9,"DFW":2,"CAN":16,"SAO":9},
    "PEK": {"ATL":15,"PEK":0,"DXB":8,"TYO":3,"LON":10,"LAX":12,"PAR":11,"FRA":10,"IST":9,"SIN":6,"MAD":12,"AMS":10,"DFW":14,"CAN":3,"SAO":22},
    "DXB": {"ATL":14,"PEK":8,"DXB":0,"TYO":10,"LON":7,"LAX":16,"PAR":7,"FRA":7,"IST":4,"SIN":7,"MAD":8,"AMS":7,"DFW":15,"CAN":8,"SAO":15},
    "TYO": {"ATL":16,"PEK":3,"DXB":10,"TYO":0,"LON":12,"LAX":11,"PAR":13,"FRA":12,"IST":11,"SIN":7,"MAD":14,"AMS":12,"DFW":13,"CAN":4,"SAO":24},
    "LON": {"ATL":8,"PEK":10,"DXB":7,"TYO":12,"LON":0,"LAX":11,"PAR":1,"FRA":1,"IST":4,"SIN":13,"MAD":2,"AMS":1,"DFW":10,"CAN":11,"SAO":12},
    "LAX": {"ATL":5,"PEK":12,"DXB":16,"TYO":11,"LON":11,"LAX":0,"PAR":11,"FRA":11,"IST":13,"SIN":17,"MAD":11,"AMS":11,"DFW":3,"CAN":14,"SAO":12},
    "PAR": {"ATL":9,"PEK":11,"DXB":7,"TYO":13,"LON":1,"LAX":11,"PAR":0,"FRA":1,"IST":3,"SIN":13,"MAD":2,"AMS":1,"DFW":10,"CAN":11,"SAO":12},
    "FRA": {"ATL":9,"PEK":10,"DXB":7,"TYO":12,"LON":1,"LAX":11,"PAR":1,"FRA":0,"IST":3,"SIN":12,"MAD":2,"AMS":1,"DFW":10,"CAN":10,"SAO":12},
    "IST": {"ATL":11,"PEK":9,"DXB":4,"TYO":11,"LON":4,"LAX":13,"PAR":3,"FRA":3,"IST":0,"SIN":10,"MAD":4,"AMS":3,"DFW":12,"CAN":9,"SAO":13},
    "SIN": {"ATL":18,"PEK":6,"DXB":7,"TYO":7,"LON":13,"LAX":17,"PAR":13,"FRA":12,"IST":10,"SIN":0,"MAD":14,"AMS":13,"DFW":17,"CAN":4,"SAO":25},
    "MAD": {"ATL":8,"PEK":12,"DXB":8,"TYO":14,"LON":2,"LAX":11,"PAR":2,"FRA":2,"IST":4,"SIN":14,"MAD":0,"AMS":2,"DFW":10,"CAN":12,"SAO":10},
    "AMS": {"ATL":9,"PEK":10,"DXB":7,"TYO":12,"LON":1,"LAX":11,"PAR":1,"FRA":1,"IST":3,"SIN":13,"MAD":2,"AMS":0,"DFW":10,"CAN":10,"SAO":12},
    "DFW": {"ATL":2,"PEK":14,"DXB":15,"TYO":13,"LON":10,"LAX":3,"PAR":10,"FRA":10,"IST":12,"SIN":17,"MAD":10,"AMS":10,"DFW":0,"CAN":15,"SAO":10},
    "CAN": {"ATL":16,"PEK":3,"DXB":8,"TYO":4,"LON":11,"LAX":14,"PAR":11,"FRA":10,"IST":9,"SIN":4,"MAD":12,"AMS":10,"DFW":15,"CAN":0,"SAO":23},
    "SAO": {"ATL":9,"PEK":22,"DXB":15,"TYO":24,"LON":12,"LAX":12,"PAR":12,"FRA":12,"IST":13,"SIN":25,"MAD":10,"AMS":12,"DFW":10,"CAN":23,"SAO":0},
}

# Alias para compatibilidad con código heredado (Dijkstra estático / TSP)
COST_MATRIX: Dict[str, Dict[str, float]] = {
    src: {dst: price for dst, price in dests.items() if price is not None}
    for src, dests in COST_ECONOMY.items()
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
                data = resp.json()
                # ms-flights puede retornar lista o dict con "flights"
                if isinstance(data, list):
                    return data
                return data.get("flights", [])
    except Exception:
        pass
    return []  # CAP: AP — continuar sin vuelos reales


def _matrix_price(origin: str, destination: str, seat_class: str) -> Optional[float]:
    """Precio desde las matrices. None si no hay ruta directa en el dataset."""
    matrix = COST_FIRST if seat_class == "FIRST" else COST_ECONOMY
    return matrix.get(origin, {}).get(destination)


def _theoretical_leg(origin: str, destination: str, seat_class: str, date_epoch: int) -> dict:
    """Crea un tramo teórico desde las matrices cuando ms-flights no tiene datos."""
    eco  = COST_ECONOMY.get(origin, {}).get(destination) or 0
    fst  = COST_FIRST.get(origin, {}).get(destination) or 0
    price = fst if seat_class == "FIRST" else eco
    dur_h = TIME_MATRIX.get(origin, {}).get(destination, 8)
    return {
        "flight_id":      None,
        "flight_number":  None,
        "origin":         origin,
        "destination":    destination,
        "departure_epoch": date_epoch,
        "arrival_epoch":  date_epoch + int(dur_h * 3600),
        "duration_h":     dur_h,
        "duration_minutes": int(dur_h * 60),
        "price":          price,
        "price_economy":  eco,
        "price_first":    fst,
        "economy_price":  eco,
        "first_class_price": fst,
        "aircraft_model": None,
        "aircraft_id":    None,
        "available_first":   0,
        "available_economy": 0,
        "status":         "THEORETICAL",
        "theoretical":    True,
    }


async def _search_best_flight(
    origin: str, destination: str, date_epoch: int, seat_class: str = "ECONOMY"
) -> Optional[dict]:
    """
    Retorna el vuelo más barato para origin→destination en date_epoch.
    Si ms-flights no tiene datos reales, cae a la matriz como tramo teórico.
    Retorna None si la ruta no existe en el dataset (celda None en la matriz).
    """
    # Primero verificar que la ruta existe en el dataset
    matrix_p = _matrix_price(origin, destination, seat_class)
    if matrix_p is None:
        return None  # ruta sin vuelo directo, nunca existirá

    flights = await _get_flights_for_segment(origin, destination, date_epoch, seat_class)
    real = [f for f in flights if not f.get("date_note")]

    if not real and flights:
        real = flights  # acepta fallback de fecha cercana si no hay del día exacto

    if real:
        price_key = "first_class_price" if seat_class == "FIRST" else "economy_price"
        return min(real, key=lambda f: f.get(price_key) or matrix_p)

    # Sin datos de ms-flights: retornar tramo teórico desde matrices
    return _theoretical_leg(origin, destination, seat_class, date_epoch)


async def _build_flight_graph(
    date_epoch: int, seat_class: str
) -> Dict[tuple, dict]:
    """
    Construye el grafo de vuelos disponibles para date_epoch.
    Para cada ruta del dataset (no-None en las matrices):
      - Intenta obtener vuelo real de ms-flights
      - Si no hay, usa precio/tiempo de la matriz como fallback teórico
    Retorna dict: (origin, dest) → {price, time_h, flight, real}
    """
    price_matrix = COST_FIRST if seat_class == "FIRST" else COST_ECONOMY

    known_pairs = [
        (src, dst)
        for src, dests in price_matrix.items()
        for dst, price in dests.items()
        if price is not None
    ]

    # Consultar ms-flights en paralelo para todas las rutas conocidas
    tasks = [
        _get_flights_for_segment(src, dst, date_epoch, seat_class)
        for src, dst in known_pairs
    ]
    results = await asyncio.gather(*tasks)

    price_key = "first_class_price" if seat_class == "FIRST" else "economy_price"
    graph: Dict[tuple, dict] = {}

    for (src, dst), flights in zip(known_pairs, results):
        time_h = TIME_MATRIX.get(src, {}).get(dst, 8)
        matrix_p = price_matrix[src][dst]

        real = [f for f in flights if not f.get("date_note")]
        if not real and flights:
            real = flights  # acepta fallback de fecha cercana

        if real:
            best = min(real, key=lambda f: f.get(price_key) or matrix_p)
            actual_price = best.get(price_key) or matrix_p
            graph[(src, dst)] = {
                "price":  actual_price,
                "time_h": time_h,
                "flight": best,
                "real":   True,
            }
        else:
            # Fallback teórico desde matrices
            graph[(src, dst)] = {
                "price":  matrix_p,
                "time_h": time_h,
                "flight": _theoretical_leg(src, dst, seat_class, date_epoch),
                "real":   False,
            }

    return graph


def _dijkstra_on_graph(
    graph: Dict[tuple, dict], origin: str, destination: str, weight_key: str
) -> Optional[list]:
    """
    Dijkstra sobre el grafo de vuelos.
    Retorna lista de (src, dst, edge_data) en el camino óptimo, o None si inalcanzable.
    """
    airport_list = list(AIRPORTS.keys())
    INF = float("inf")
    dist: Dict[str, float] = {a: INF for a in airport_list}
    prev: Dict[str, Optional[tuple]] = {a: None for a in airport_list}
    dist[origin] = 0.0
    pq: List[tuple] = [(0.0, origin)]

    while pq:
        cost, u = heapq.heappop(pq)
        if cost > dist[u]:
            continue
        if u == destination:
            break
        for v in airport_list:
            edge = graph.get((u, v))
            if edge:
                new_cost = cost + edge[weight_key]
                if new_cost < dist[v]:
                    dist[v] = new_cost
                    prev[v] = (u, edge)
                    heapq.heappush(pq, (new_cost, v))

    if dist[destination] == INF:
        return None

    edges = []
    node = destination
    while prev[node] is not None:
        prev_node, edge = prev[node]
        edges.append((prev_node, node, edge))
        node = prev_node
    edges.reverse()
    return edges


def _format_leg(flight: dict, seat_class: str) -> dict:
    """Normaliza un vuelo de ms-flights al formato de tramo de ruta."""
    price_key = "first_class_price" if seat_class == "FIRST" else "economy_price"
    price = flight.get(price_key) or flight.get("economy_price") or 0
    dur_h = flight.get("duration_hours") or round(flight.get("duration_minutes", 0) / 60, 2)
    return {
        "flight_id":        flight.get("flight_id"),
        "flight_number":    flight.get("flight_number"),
        "origin":           flight.get("origin"),
        "destination":      flight.get("destination"),
        "departure_epoch":  flight.get("flight_date_epoch") or flight.get("departure_epoch"),
        "arrival_epoch":    flight.get("arrival_epoch"),
        "duration_h":       round(dur_h, 2),
        "duration_minutes": flight.get("duration_minutes", 0),
        "price":            price,
        "price_economy":    flight.get("economy_price") or flight.get("price_economy") or price,
        "price_first":      flight.get("first_class_price") or flight.get("price_first") or price,
        "economy_price":    flight.get("economy_price") or flight.get("price_economy") or price,
        "first_class_price": flight.get("first_class_price") or flight.get("price_first") or price,
        "aircraft_model":   flight.get("aircraft_model"),
        "aircraft_id":      flight.get("aircraft_id"),
        "available_first":  flight.get("available_first", 0),
        "available_economy": flight.get("available_economy", 0),
        "status":           flight.get("status", "SCHEDULED"),
    }


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
    Ruta óptima mediante Dijkstra sobre vuelos REALES de la BD.
    - Construye grafo desde ms-flights para date_epoch.
    - Fallback a matrices cuando no hay vuelo real ese día.
    - Funciona con cualquier dataset del mismo formato.
    CAP: AP — si ms-flights no responde, usa matrices estáticas.
    """
    o = origin.upper().strip()
    d = destination.upper().strip()

    if o not in AIRPORTS:
        raise HTTPException(400, {"error": "AEROPUERTO_INVALIDO", "message": f"Origen '{o}' no reconocido"})
    if d not in AIRPORTS:
        raise HTTPException(400, {"error": "AEROPUERTO_INVALIDO", "message": f"Destino '{d}' no reconocido"})
    if o == d:
        raise HTTPException(400, {"error": "MISMO_AEROPUERTO", "message": "Origen y destino son iguales"})

    weight_key = "price" if mode == "price" else "time_h"

    # ── Construir grafo desde vuelos reales + fallback matrices ───────────────
    graph = await _build_flight_graph(date_epoch, seat_class)

    # ── Dijkstra: mejor ruta (menor costo o tiempo) ───────────────────────────
    best_edges = _dijkstra_on_graph(graph, o, d, weight_key)

    if not best_edges:
        return {
            "origin": o, "destination": d, "date_epoch": date_epoch,
            "seat_class": seat_class, "routes": [],
            "message": "No hay ruta posible entre estos aeropuertos",
        }

    def _edges_to_route(edges: list) -> dict:
        legs = []
        for src, dst, edge in edges:
            f = edge["flight"]
            legs.append(f if f.get("theoretical") else _format_leg(f, seat_class))
        stops = [edges[0][0]] + [e[1] for e in edges]
        total_cost = sum(e[2]["price"] for e in edges)
        total_time = sum(e[2]["time_h"] for e in edges)
        if len(edges) > 1:
            total_time += (len(edges) - 1) * 2.0  # +2h por escala
        all_real = all(e[2]["real"] for e in edges)
        hub = stops[1] if len(stops) == 3 else (stops[1] if len(stops) > 3 else None)
        return {
            "type":            "DIRECT" if len(edges) == 1 else "CONNECTING",
            "stops":           stops,
            "legs":            legs,
            "total_cost":      round(total_cost, 2),
            "total_time_h":    round(total_time, 2),
            "layover_airport": hub,
            "layover_h":       (len(edges) - 1) * 2 if len(edges) > 1 else 0,
            "real_flights":    all_real,
            "algorithm":       "dijkstra_dynamic",
        }

    routes = [_edges_to_route(best_edges)]

    # ── Segunda opción: Dijkstra con peso alternativo ────────────────────────
    alt_key = "time_h" if mode == "price" else "price"
    alt_edges = _dijkstra_on_graph(graph, o, d, alt_key)
    if alt_edges:
        alt_route = _edges_to_route(alt_edges)
        if alt_route["stops"] != routes[0]["stops"]:
            routes.append(alt_route)

    # ── Tercera opción: con escala si la mejor fue directa ───────────────────
    if len(routes) < 3 and len(best_edges) == 1:
        all_nodes = list(AIRPORTS.keys())
        hub_options = []
        for hub in all_nodes:
            if hub == o or hub == d:
                continue
            e1 = graph.get((o, hub))
            e2 = graph.get((hub, d))
            if e1 and e2:
                tc = e1["price"] + e2["price"]
                tt = e1["time_h"] + e2["time_h"] + 2.0
                hub_options.append((tc, tt, hub, e1, e2))
        if hub_options:
            hub_options.sort(key=lambda x: x[0] if mode == "price" else x[1])
            tc, tt, hub, e1, e2 = hub_options[0]
            f1 = e1["flight"]
            f2 = e2["flight"]
            routes.append({
                "type": "CONNECTING",
                "stops": [o, hub, d],
                "legs": [
                    f1 if f1.get("theoretical") else _format_leg(f1, seat_class),
                    f2 if f2.get("theoretical") else _format_leg(f2, seat_class),
                ],
                "total_cost":      round(tc, 2),
                "total_time_h":    round(tt, 2),
                "layover_airport": hub,
                "layover_h":       2,
                "real_flights":    e1["real"] and e2["real"],
                "algorithm":       "dijkstra_dynamic",
            })

    return {
        "origin": o, "destination": d,
        "date_epoch": date_epoch, "seat_class": seat_class,
        "routes": routes[:3],
    }


# ─── GET /routes/graph-status ────────────────────────────────────────────────

@app.get("/routes/graph-status")
async def graph_status(date_epoch: Optional[int] = Query(None)):
    """
    Muestra qué rutas directas están disponibles en la BD para una fecha.
    Útil para el admin: al cambiar el dataset, hace clic en Recalcular.
    Compara rutas reales de ms-flights vs. rutas esperadas por las matrices.
    """
    if not date_epoch:
        date_epoch = int(time.time())

    from datetime import datetime, timezone
    dt = datetime.fromtimestamp(date_epoch, tz=timezone.utc)
    day_label = dt.strftime("%Y-%m-%d")

    # Pares que deberían existir según las matrices
    matrix_pairs = set(
        (src, dst)
        for src, dests in COST_ECONOMY.items()
        for dst, price in dests.items()
        if price is not None
    )

    # Consultar ms-flights en paralelo para todos los pares conocidos
    pair_list = sorted(matrix_pairs)
    tasks = [
        _get_flights_for_segment(src, dst, date_epoch, "ECONOMY")
        for src, dst in pair_list
    ]
    results = await asyncio.gather(*tasks)

    available = []
    unavailable = []
    for (src, dst), flights in zip(pair_list, results):
        real = [f for f in flights if not f.get("date_note")]
        eco_price = COST_ECONOMY.get(src, {}).get(dst)
        entry = {
            "from": src,
            "to": dst,
            "matrix_price_economy": eco_price,
            "matrix_time_h": TIME_MATRIX.get(src, {}).get(dst),
        }
        if real:
            best = min(real, key=lambda f: f.get("economy_price") or eco_price or 9999)
            entry.update({
                "flights_today": len(real),
                "best_price":    best.get("economy_price") or eco_price,
                "real":          True,
            })
            available.append(entry)
        else:
            entry.update({"flights_today": 0, "real": False})
            unavailable.append(entry)

    return {
        "date":              day_label,
        "date_epoch":        date_epoch,
        "matrix_routes":     len(matrix_pairs),
        "real_routes_today": len(available),
        "missing_today":     len(unavailable),
        "available":         sorted(available, key=lambda r: (r["from"], r["to"])),
        "unavailable":       sorted(unavailable, key=lambda r: (r["from"], r["to"])),
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
