"""
ms-routes — Puerto 8003
Algoritmos de rutas: Dijkstra (más barato) y TSP.
Regla CLAUDE.md: priorizar más barata primero, luego más rápida.
"""
import os
import time
from typing import List, Optional

import networkx as nx
from fastapi import FastAPI, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db1, get_db2, mongo_db
from models import RouteResult, RouteSegment, RouteSearchParams

app = FastAPI(
    title="ms-routes",
    description="Microservicio de rutas — Dijkstra y TSP",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Matrices estáticas para el grafo ────────────────────────────────────────

COST_MATRIX = {
    "ATL": {"TYO":1400,"LAX":400,"FRA":800,"SIN":1500,"MAD":800,"DFW":200,"SAO":900},
    "PEK": {"DXB":700,"TYO":500,"LON":900,"PAR":950,"SIN":600,"MAD":950,"AMS":900,"CAN":200,"SAO":1700},
    "DXB": {"PEK":700,"TYO":750,"LON":650,"LAX":1300,"PAR":700,"FRA":600,"IST":400,"SIN":600,"AMS":650,"DFW":1200,"CAN":650,"SAO":1400},
    "TYO": {"ATL":1400,"PEK":500,"DXB":750,"LON":1000,"LAX":900,"PAR":1050,"IST":900,"SIN":700,"MAD":1100,"CAN":550},
    "LON": {"ATL":700,"DXB":650,"TYO":1000,"LAX":800,"PAR":150,"FRA":200,"IST":400,"MAD":200,"AMS":150,"DFW":750,"CAN":950,"SAO":1100},
    "LAX": {"ATL":400,"PEK":1100,"DXB":1300,"TYO":900,"PAR":850,"FRA":900,"IST":1100,"SIN":1400,"AMS":850,"DFW":300,"CAN":1150},
    "PAR": {"ATL":750,"DXB":700,"TYO":1050,"LAX":850,"FRA":150,"IST":450,"MAD":200,"AMS":180,"CAN":950,"SAO":1050},
    "FRA": {"PEK":850,"DXB":600,"TYO":950,"LON":200,"LAX":900,"PAR":150,"IST":350,"CAN":850,"SAO":900},
    "IST": {"DXB":400,"TYO":900,"FRA":350,"SIN":800,"MAD":500,"AMS":450,"DFW":1000,"CAN":800,"SAO":1200},
    "SIN": {"PEK":600,"DXB":700,"TYO":900,"PAR":950,"IST":800,"MAD":1000,"CAN":1400},
    "MAD": {"DXB":750,"PAR":200,"FRA":250,"IST":500,"SIN":1000,"AMS":200,"DFW":850,"CAN":950,"SAO":1000},
    "AMS": {"ATL":780,"PEK":900,"DXB":650,"TYO":1000,"LON":150,"LAX":850,"PAR":200,"FRA":200,"IST":450,"MAD":200,"DFW":800,"CAN":900,"SAO":1050},
    "DFW": {"ATL":200,"DXB":1200,"LAX":300,"FRA":800,"IST":1000,"MAD":850,"AMS":800,"CAN":1200,"SAO":950},
    "CAN": {"PEK":200,"DXB":650,"TYO":550,"LON":950,"LAX":1150,"PAR":950,"IST":800,"SIN":500,"MAD":950,"AMS":900,"DFW":1200,"SAO":1700},
    "SAO": {"ATL":900,"PEK":1700,"DXB":1400,"TYO":1800,"LON":1100,"LAX":1000,"PAR":1050,"FRA":1100,"IST":1200,"SIN":1800,"MAD":1000,"AMS":1050,"DFW":950,"CAN":1700},
}

TIME_MATRIX = {
    "ATL": {"PEK":15,"DXB":14,"TYO":16,"LON":8,"LAX":5,"PAR":9,"FRA":9,"IST":11,"SIN":18,"MAD":8,"AMS":9,"DFW":2,"CAN":16,"SAO":9},
    "PEK": {"DXB":8,"TYO":3,"LON":10,"LAX":12,"PAR":11,"FRA":10,"IST":9,"SIN":6,"MAD":12,"AMS":10,"DFW":14,"CAN":3,"SAO":22},
    "DXB": {"PEK":8,"TYO":10,"LON":7,"LAX":16,"PAR":7,"FRA":7,"IST":4,"SIN":7,"MAD":8,"AMS":7,"DFW":15,"CAN":8,"SAO":15},
    "TYO": {"ATL":16,"PEK":3,"DXB":10,"LON":12,"LAX":11,"PAR":13,"FRA":12,"IST":11,"SIN":7,"MAD":14,"AMS":12,"DFW":13,"CAN":4},
    "LON": {"ATL":8,"DXB":7,"TYO":12,"LAX":11,"PAR":1,"FRA":1,"IST":4,"SIN":13,"MAD":2,"AMS":1,"DFW":10,"CAN":11,"SAO":12},
    "LAX": {"ATL":5,"PEK":12,"DXB":16,"TYO":11,"LON":11,"PAR":11,"FRA":11,"IST":13,"SIN":17,"MAD":11,"AMS":11,"DFW":3,"CAN":14},
    "PAR": {"ATL":9,"DXB":7,"TYO":13,"LON":1,"LAX":11,"FRA":1,"IST":3,"SIN":13,"MAD":2,"AMS":1,"DFW":10,"CAN":11,"SAO":12},
    "FRA": {"ATL":9,"PEK":10,"DXB":7,"TYO":12,"LON":1,"LAX":11,"PAR":1,"IST":3,"SIN":12,"MAD":2,"AMS":1,"DFW":10,"CAN":10,"SAO":12},
    "IST": {"ATL":11,"PEK":9,"DXB":4,"TYO":11,"LON":4,"LAX":13,"PAR":3,"FRA":3,"SIN":10,"MAD":4,"AMS":3,"DFW":12,"CAN":9,"SAO":13},
    "SIN": {"PEK":6,"DXB":7,"TYO":7,"LON":13,"LAX":17,"PAR":13,"FRA":12,"IST":10,"MAD":14,"AMS":13,"DFW":17,"CAN":4},
    "MAD": {"ATL":8,"DXB":8,"TYO":14,"LON":2,"LAX":11,"PAR":2,"FRA":2,"IST":4,"SIN":14,"AMS":2,"DFW":10,"CAN":12,"SAO":10},
    "AMS": {"ATL":9,"PEK":10,"DXB":7,"TYO":12,"LON":1,"LAX":11,"PAR":1,"FRA":1,"IST":3,"SIN":13,"MAD":2,"DFW":10,"CAN":10,"SAO":12},
    "DFW": {"ATL":2,"DXB":15,"TYO":13,"LON":10,"LAX":3,"PAR":10,"FRA":10,"IST":12,"SIN":17,"MAD":10,"AMS":10,"CAN":15,"SAO":10},
    "CAN": {"PEK":3,"DXB":8,"TYO":4,"LON":11,"LAX":14,"PAR":11,"FRA":10,"IST":9,"SIN":4,"MAD":12,"AMS":10,"DFW":15,"SAO":23},
    "SAO": {"ATL":9,"PEK":22,"DXB":15,"TYO":24,"LON":12,"LAX":12,"PAR":12,"FRA":12,"IST":13,"SIN":25,"MAD":10,"AMS":12,"DFW":10,"CAN":23},
}


def build_graph(weight: str = "cost") -> nx.DiGraph:
    """Construye grafo dirigido con pesos de costo o tiempo."""
    G = nx.DiGraph()
    matrix = COST_MATRIX if weight == "cost" else TIME_MATRIX
    for origin, destinations in matrix.items():
        for dest, w in destinations.items():
            G.add_edge(origin, dest, weight=w)
    return G


@app.get("/health")
async def health():
    return {"service": "ms-routes", "status": "ok", "timestamp": int(time.time())}


@app.get("/routes/dijkstra")
async def dijkstra_route(
    origin: str = Query(...),
    destination: str = Query(...),
    weight: str = Query("cost", description="cost | time"),
):
    """
    Ruta más barata (weight=cost) o más rápida (weight=time) usando Dijkstra.
    Prioridad CLAUDE.md: costo primero, tiempo segundo.
    """
    o = origin.upper()
    d = destination.upper()
    G = build_graph(weight)

    try:
        path = nx.dijkstra_path(G, o, d, weight="weight")
        cost = nx.dijkstra_path_length(G, o, d, weight="weight")
    except nx.NetworkXNoPath:
        return {"error": "No hay ruta disponible", "origin": o, "destination": d}
    except nx.NodeNotFound as e:
        return {"error": str(e)}

    # Calcular costo y tiempo total
    total_cost = sum(COST_MATRIX.get(path[i], {}).get(path[i+1], 0) for i in range(len(path)-1))
    total_time = sum(TIME_MATRIX.get(path[i], {}).get(path[i+1], 0) for i in range(len(path)-1))

    segments = []
    for i in range(len(path)-1):
        segments.append({
            "origin": path[i],
            "destination": path[i+1],
            "price_economy": COST_MATRIX.get(path[i], {}).get(path[i+1], 0),
            "duration_hours": TIME_MATRIX.get(path[i], {}).get(path[i+1], 0),
        })

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
    """Lista todos los aeropuertos disponibles con sus regiones."""
    airports = {
        "ATL": {"name": "Atlanta Hartsfield", "city": "Atlanta", "country": "US", "region": "America"},
        "LAX": {"name": "Los Angeles Intl", "city": "Los Angeles", "country": "US", "region": "America"},
        "DFW": {"name": "Dallas/Fort Worth", "city": "Dallas", "country": "US", "region": "America"},
        "SAO": {"name": "São Paulo Guarulhos", "city": "São Paulo", "country": "BR", "region": "America"},
        "LON": {"name": "London Heathrow", "city": "London", "country": "GB", "region": "Europe"},
        "PAR": {"name": "Paris Charles de Gaulle", "city": "Paris", "country": "FR", "region": "Europe"},
        "FRA": {"name": "Frankfurt Main", "city": "Frankfurt", "country": "DE", "region": "Europe"},
        "IST": {"name": "Istanbul Airport", "city": "Istanbul", "country": "TR", "region": "Europe"},
        "MAD": {"name": "Madrid Barajas", "city": "Madrid", "country": "ES", "region": "Europe"},
        "AMS": {"name": "Amsterdam Schiphol", "city": "Amsterdam", "country": "NL", "region": "Europe"},
        "DXB": {"name": "Dubai Intl", "city": "Dubai", "country": "AE", "region": "Middle East"},
        "PEK": {"name": "Beijing Capital", "city": "Beijing", "country": "CN", "region": "Asia"},
        "TYO": {"name": "Tokyo Haneda", "city": "Tokyo", "country": "JP", "region": "Asia"},
        "SIN": {"name": "Singapore Changi", "city": "Singapore", "country": "SG", "region": "Asia"},
        "CAN": {"name": "Guangzhou Baiyun", "city": "Guangzhou", "country": "CN", "region": "Asia"},
    }
    return airports


@app.get("/routes/cost-matrix")
async def get_cost_matrix():
    return {"cost_matrix": COST_MATRIX, "time_matrix": TIME_MATRIX}


@app.post("/routes/tsp")
async def tsp_route(airports: List[str]):
    """
    Orden óptimo para visitar todos los aeropuertos (TSP aproximado con networkx).
    Útil para itinerarios multi-destino.
    """
    nodes = [a.upper() for a in airports]
    if len(nodes) < 2:
        return {"error": "Se necesitan al menos 2 aeropuertos"}

    G = build_graph("cost")
    # TSP con christofides aproximado (requiere grafo completo)
    # Creamos subgrafo completo con las ciudades pedidas
    subG = nx.Graph()
    for i, a in enumerate(nodes):
        for b in nodes[i+1:]:
            cost_ab = COST_MATRIX.get(a, {}).get(b, 9999)
            cost_ba = COST_MATRIX.get(b, {}).get(a, 9999)
            subG.add_edge(a, b, weight=min(cost_ab, cost_ba))

    try:
        # greedy TSP
        path = nx.approximation.greedy_tsp(subG, weight="weight", source=nodes[0])
        total = sum(COST_MATRIX.get(path[i], {}).get(path[i+1], 0) for i in range(len(path)-1))
    except Exception as e:
        return {"error": str(e)}

    return {
        "algorithm": "tsp_greedy",
        "path": path,
        "total_cost_usd": total,
        "stops": len(path) - 2,
    }
