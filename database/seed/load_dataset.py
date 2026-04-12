"""
load_dataset.py — Seed de 60,000 vuelos para Aerolíneas Rafael Pabón
Uso: python database/seed/load_dataset.py [--csv PATH] [--reset]
"""
import argparse
import csv
import json
import os
import random
import sys
import time
from calendar import timegm
from datetime import datetime, timezone

import pyodbc
import pymongo
from tqdm import tqdm

# ─── Config ──────────────────────────────────────────────────────────────────

CSV_DEFAULT = os.path.join(os.path.dirname(__file__), "flights_dataset.csv")

DB1_CONN = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={os.getenv('DB1_HOST','localhost')},{os.getenv('DB1_PORT','1433')};"
    f"DATABASE={os.getenv('DB1_NAME','aerolineas_db1')};"
    f"UID={os.getenv('DB1_USER','sa')};"
    f"PWD={os.getenv('DB1_PASSWORD','Rafael_Pabon_2024!')};"
    f"TrustServerCertificate=yes;"
)
DB2_CONN = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={os.getenv('DB2_HOST','localhost')},{os.getenv('DB2_PORT','1434')};"
    f"DATABASE={os.getenv('DB2_NAME','aerolineas_db2')};"
    f"UID={os.getenv('DB2_USER','sa')};"
    f"PWD={os.getenv('DB2_PASSWORD','Rafael_Pabon_2024!')};"
    f"TrustServerCertificate=yes;"
)
MONGO_URI = (
    f"mongodb://{os.getenv('DB3_USER','admin')}:{os.getenv('DB3_PASSWORD','Rafael_Pabon_2024!')}"
    f"@{os.getenv('DB3_HOST','localhost')}:{os.getenv('DB3_PORT','27017')}/"
    f"?authSource=admin"
)
MONGO_DB = os.getenv("DB3_NAME", "aerolineas_db3")

# ─── Mapas de aeropuertos ─────────────────────────────────────────────────────

NODE_MAP = {
    "ATL": 1, "LAX": 1, "DFW": 1, "SAO": 1,
    "LON": 2, "PAR": 2, "FRA": 2, "IST": 2, "MAD": 2, "AMS": 2, "DXB": 2,
    "PEK": 3, "TYO": 3, "SIN": 3, "CAN": 3,
}

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

# ─── Config de flota ──────────────────────────────────────────────────────────

AIRCRAFT_CONFIG = {
    # aircraft_id → (seats_first, seats_economy)
    **{i: (10, 439) for i in range(1, 7)},      # A380-800
    **{i: (10, 300) for i in range(7, 25)},     # B777-300ER
    **{i: (12, 250) for i in range(25, 36)},    # A350-900
    **{i: (8,  220) for i in range(36, 51)},    # B787-9
}

SEAT_LETTERS = {
    "A380-800":    list("ABCDEFGHJK"),   # 10 cols
    "B777-300ER":  list("ABCDEFGHJ"),    # 9 cols (sin I)
    "A350-900":    list("ABCDEFGHJ"),    # 9 cols
    "B787-9":      list("ABCDEFGH"),     # 8 cols
}

AIRCRAFT_MODEL = {
    **{i: "A380-800"   for i in range(1, 7)},
    **{i: "B777-300ER" for i in range(7, 25)},
    **{i: "A350-900"   for i in range(25, 36)},
    **{i: "B787-9"     for i in range(36, 51)},
}

FIRST_ROWS = {
    "A380-800":   2,   # filas 1-2 → 10 asientos primera
    "B777-300ER": 2,   # filas 1-2 → 10 primera (no exacto pero funcional)
    "A350-900":   2,   # filas 1-2 → 12 primera
    "B787-9":     1,   # fila 1    → 8 primera
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def to_epoch(date_str: str, time_str: str) -> int:
    """Convierte 'YYYY-MM-DD' + 'HH:MM' a epoch unix (UTC)."""
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        return int(timegm(dt.timetuple()))
    except Exception:
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
            return int(timegm(dt.timetuple()))
        except Exception:
            return int(time.time())


def get_price(origin: str, destination: str) -> float:
    """Precio turista desde COST_MATRIX; fallback 500."""
    o = origin.strip().upper()
    d = destination.strip().upper()
    return float(COST_MATRIX.get(o, {}).get(d, 500))


def get_duration(origin: str, destination: str) -> int:
    """Duración en minutos desde TIME_MATRIX; fallback 480."""
    o = origin.strip().upper()
    d = destination.strip().upper()
    hours = TIME_MATRIX.get(o, {}).get(d, 8)
    return hours * 60


def generate_seats(flight_id: int, aircraft_id: int, price_economy: float,
                   price_first: float, rng: random.Random):
    """
    Genera lista de asientos para un vuelo.
    Devuelve lista de dicts con todos los campos.
    Distribuye estados: 73% SOLD, 3% RESERVED, 24% AVAILABLE (seed=42).
    """
    model = AIRCRAFT_MODEL[aircraft_id]
    config = AIRCRAFT_CONFIG[aircraft_id]
    n_first, n_economy = config
    letters = SEAT_LETTERS[model]
    first_rows = FIRST_ROWS[model]

    seats = []
    now_epoch = int(time.time())

    # Primera clase: primeras filas
    for row in range(1, first_rows + 1):
        for col in letters:
            if len(seats) >= n_first + n_economy:
                break
            roll = rng.random()
            if roll < 0.73:
                status = "SOLD"
            elif roll < 0.76:
                status = "RESERVED"
            else:
                status = "AVAILABLE"
            seats.append({
                "flight_id":         flight_id,
                "seat_number":       f"{row}{col}",
                "seat_class":        "FIRST",
                "status":            status,
                "locked_until":      None,
                "price":             round(price_first, 2),
                "node_id":           NODE_MAP.get(str(flight_id), 1),
                "lamport_ts":        0,
                "vector_clock":      "[0,0,0]",
                "last_update_epoch": now_epoch,
            })
            if len(seats) == n_first:
                break
        if len(seats) == n_first:
            break

    # Económica: resto de filas
    total = n_first + n_economy
    row = first_rows + 1
    while len(seats) < total:
        for col in letters:
            if len(seats) >= total:
                break
            roll = rng.random()
            if roll < 0.73:
                status = "SOLD"
            elif roll < 0.76:
                status = "RESERVED"
            else:
                status = "AVAILABLE"
            seats.append({
                "flight_id":         flight_id,
                "seat_number":       f"{row}{col}",
                "seat_class":        "ECONOMY",
                "status":            status,
                "locked_until":      None,
                "price":             round(price_economy, 2),
                "node_id":           NODE_MAP.get(str(flight_id), 1),
                "lamport_ts":        0,
                "vector_clock":      "[0,0,0]",
                "last_update_epoch": now_epoch,
            })
        row += 1

    return seats


# ─── Conexiones ───────────────────────────────────────────────────────────────

def get_sql_conn(conn_str: str):
    for attempt in range(10):
        try:
            return pyodbc.connect(conn_str, timeout=5)
        except Exception as e:
            print(f"  Reintentando conexión SQL ({attempt+1}/10)… {e}")
            time.sleep(5)
    raise RuntimeError("No se pudo conectar a SQL Server.")


def get_mongo_db():
    for attempt in range(10):
        try:
            client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            return client[MONGO_DB]
        except Exception as e:
            print(f"  Reintentando conexión Mongo ({attempt+1}/10)… {e}")
            time.sleep(5)
    raise RuntimeError("No se pudo conectar a MongoDB.")


# ─── Insert helpers ───────────────────────────────────────────────────────────

INSERT_FLIGHT_SQL = """
INSERT INTO dbo.flights
  (flight_number, aircraft_id, origin, destination,
   departure_epoch, arrival_epoch, duration_minutes,
   price_economy, price_first, status,
   available_economy, available_first,
   node_id, lamport_ts, vector_clock, last_update_epoch)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

INSERT_SEAT_SQL = """
INSERT INTO dbo.seats
  (flight_id, seat_number, seat_class, status, locked_until, price,
   node_id, lamport_ts, vector_clock, last_update_epoch)
VALUES (?,?,?,?,?,?,?,?,?,?)
"""


def insert_flight_sql(cursor, row_data: dict) -> int:
    cursor.execute(INSERT_FLIGHT_SQL, (
        row_data["flight_number"],
        row_data["aircraft_id"],
        row_data["origin"],
        row_data["destination"],
        row_data["departure_epoch"],
        row_data["arrival_epoch"],
        row_data["duration_minutes"],
        row_data["price_economy"],
        row_data["price_first"],
        row_data["status"],
        row_data["available_economy"],
        row_data["available_first"],
        row_data["node_id"],
        0, "[0,0,0]",
        int(time.time()),
    ))
    cursor.execute("SELECT @@IDENTITY")
    return int(cursor.fetchone()[0])


def insert_seats_sql(cursor, seats: list[dict]):
    for s in seats:
        cursor.execute(INSERT_SEAT_SQL, (
            s["flight_id"], s["seat_number"], s["seat_class"],
            s["status"], s["locked_until"], s["price"],
            s["node_id"], 0, "[0,0,0]", s["last_update_epoch"],
        ))


def mongo_next_id(mdb, counter_name: str) -> int:
    result = mdb.counters.find_one_and_update(
        {"_id": counter_name},
        {"$inc": {"seq": 1}},
        return_document=True,
    )
    return result["seq"]


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=CSV_DEFAULT)
    parser.add_argument("--reset", action="store_true",
                        help="Truncar tablas antes de insertar")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"[ERROR] CSV no encontrado: {args.csv}")
        print("Coloca el archivo en database/seed/flights_dataset.csv")
        sys.exit(1)

    rng = random.Random(42)

    print("Conectando a bases de datos…")
    conn1 = get_sql_conn(DB1_CONN)
    conn2 = get_sql_conn(DB2_CONN)
    mdb   = get_mongo_db()
    cur1  = conn1.cursor()
    cur2  = conn2.cursor()
    print("  Conectado a DB1 (SQL Server — América)")
    print("  Conectado a DB2 (SQL Server — Europa)")
    print("  Conectado a DB3 (MongoDB — Asia)")

    if args.reset:
        print("Truncando tablas…")
        for cur in [cur1, cur2]:
            cur.execute("DELETE FROM dbo.seats")
            cur.execute("DELETE FROM dbo.tickets")
            cur.execute("DELETE FROM dbo.flights")
            cur.connection.commit()
        mdb.seats.delete_many({})
        mdb.tickets.delete_many({})
        mdb.flights.delete_many({})
        mdb.counters.update_many({}, {"$set": {"seq": 500000}})
        print("  Tablas truncadas.")

    # Leer CSV
    with open(args.csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Procesando {len(rows):,} vuelos…")

    skipped = 0
    n1 = n2 = n3 = 0
    now = int(time.time())

    for row in tqdm(rows, unit="vuelo", ncols=80):
        origin      = row.get("origin", row.get("Origin", "")).strip().upper()
        destination = row.get("destination", row.get("Destination", "")).strip().upper()
        flight_num  = row.get("flight_number", row.get("FlightNumber",
                      row.get("flight_no", f"RP{rng.randint(1000,9999)}"))).strip()
        date_str    = row.get("flight_date", row.get("Date", "")).strip()
        time_str    = row.get("flight_time", row.get("Time", "00:00")).strip()
        aircraft_id = int(row.get("aircraft_id", rng.randint(1, 50)))

        node_id = NODE_MAP.get(origin)
        if node_id is None:
            skipped += 1
            continue

        price_eco  = get_price(origin, destination)
        price_first = round(price_eco * 1.35, 2)
        duration   = get_duration(origin, destination)
        dep_epoch  = to_epoch(date_str, time_str) if date_str else now + rng.randint(3600, 86400*30)
        arr_epoch  = dep_epoch + duration * 60

        cfg = AIRCRAFT_CONFIG[aircraft_id]
        n_first, n_eco = cfg

        flight_data = {
            "flight_number":    flight_num,
            "aircraft_id":      aircraft_id,
            "origin":           origin,
            "destination":      destination,
            "departure_epoch":  dep_epoch,
            "arrival_epoch":    arr_epoch,
            "duration_minutes": duration,
            "price_economy":    price_eco,
            "price_first":      price_first,
            "status":           "SCHEDULED",
            "available_economy": n_eco,
            "available_first":   n_first,
            "node_id":           node_id,
        }

        # ─── Insertar en la BD correspondiente ────────────────────────────────
        if node_id == 1:
            flight_id = insert_flight_sql(cur1, flight_data)
            seats = generate_seats(flight_id, aircraft_id, price_eco, price_first, rng)
            insert_seats_sql(cur1, seats)
            # Actualizar conteo disponibles según estados generados
            avail_eco   = sum(1 for s in seats if s["seat_class"] == "ECONOMY"   and s["status"] == "AVAILABLE")
            avail_first = sum(1 for s in seats if s["seat_class"] == "FIRST"     and s["status"] == "AVAILABLE")
            cur1.execute(
                "UPDATE dbo.flights SET available_economy=?, available_first=? WHERE flight_id=?",
                avail_eco, avail_first, flight_id
            )
            n1 += 1
            if n1 % 500 == 0:
                conn1.commit()

        elif node_id == 2:
            flight_id = insert_flight_sql(cur2, flight_data)
            seats = generate_seats(flight_id, aircraft_id, price_eco, price_first, rng)
            insert_seats_sql(cur2, seats)
            avail_eco   = sum(1 for s in seats if s["seat_class"] == "ECONOMY"   and s["status"] == "AVAILABLE")
            avail_first = sum(1 for s in seats if s["seat_class"] == "FIRST"     and s["status"] == "AVAILABLE")
            cur2.execute(
                "UPDATE dbo.flights SET available_economy=?, available_first=? WHERE flight_id=?",
                avail_eco, avail_first, flight_id
            )
            n2 += 1
            if n2 % 500 == 0:
                conn2.commit()

        else:  # node 3 — MongoDB
            flight_id = mongo_next_id(mdb, "flight_id")
            flight_doc = {**flight_data, "flight_id": flight_id}
            mdb.flights.insert_one(flight_doc)
            seats = generate_seats(flight_id, aircraft_id, price_eco, price_first, rng)
            # Asignar seat_id a cada asiento
            seat_docs = []
            for s in seats:
                s["seat_id"] = mongo_next_id(mdb, "seat_id")
                seat_docs.append(s)
            if seat_docs:
                mdb.seats.insert_many(seat_docs)
            avail_eco   = sum(1 for s in seat_docs if s["seat_class"] == "ECONOMY" and s["status"] == "AVAILABLE")
            avail_first = sum(1 for s in seat_docs if s["seat_class"] == "FIRST"   and s["status"] == "AVAILABLE")
            mdb.flights.update_one(
                {"flight_id": flight_id},
                {"$set": {"available_economy": avail_eco, "available_first": avail_first}}
            )
            n3 += 1

    # Commit final
    conn1.commit()
    conn2.commit()
    cur1.close()
    cur2.close()
    conn1.close()
    conn2.close()

    print(f"\n{'─'*50}")
    print(f"  DB1 (América)  : {n1:>8,} vuelos insertados")
    print(f"  DB2 (Europa)   : {n2:>8,} vuelos insertados")
    print(f"  DB3 (Asia)     : {n3:>8,} vuelos insertados")
    print(f"  Omitidos       : {skipped:>8,} (origen desconocido)")
    print(f"  TOTAL          : {n1+n2+n3:>8,} vuelos")
    print(f"{'─'*50}")
    print("Seed completado.")


if __name__ == "__main__":
    main()
