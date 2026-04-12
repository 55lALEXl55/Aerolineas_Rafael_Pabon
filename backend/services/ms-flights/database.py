"""
database.py — Conexiones a las 3 BDs para ms-flights
"""
import os
from contextlib import asynccontextmanager

import motor.motor_asyncio
import pyodbc
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# ─── SQL Server DB1 (América) ────────────────────────────────────────────────
DB1_URL = (
    f"mssql+pyodbc://{os.getenv('DB1_USER','sa')}:{os.getenv('DB1_PASSWORD','Rafael_Pabon_2024!')}"
    f"@{os.getenv('DB1_HOST','sqlserver1')}:{os.getenv('DB1_PORT','1433')}"
    f"/{os.getenv('DB1_NAME','aerolineas_db1')}"
    f"?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
)

# ─── SQL Server DB2 (Europa) ─────────────────────────────────────────────────
DB2_URL = (
    f"mssql+pyodbc://{os.getenv('DB2_USER','sa')}:{os.getenv('DB2_PASSWORD','Rafael_Pabon_2024!')}"
    f"@{os.getenv('DB2_HOST','sqlserver2')}:{os.getenv('DB2_PORT','1433')}"
    f"/{os.getenv('DB2_NAME','aerolineas_db2')}"
    f"?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
)

engine1 = create_engine(DB1_URL, pool_pre_ping=True, pool_size=5)
engine2 = create_engine(DB2_URL, pool_pre_ping=True, pool_size=5)
Session1 = sessionmaker(bind=engine1)
Session2 = sessionmaker(bind=engine2)

# ─── MongoDB DB3 (Asia) ──────────────────────────────────────────────────────
MONGO_URI = (
    f"mongodb://{os.getenv('DB3_USER','admin')}:{os.getenv('DB3_PASSWORD','Rafael_Pabon_2024!')}"
    f"@{os.getenv('DB3_HOST','mongodb')}:{os.getenv('DB3_PORT','27017')}/?authSource=admin"
)
_mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
mongo_db = _mongo_client[os.getenv("DB3_NAME", "aerolineas_db3")]


def get_db1() -> Session:
    db = Session1()
    try:
        yield db
    finally:
        db.close()


def get_db2() -> Session:
    db = Session2()
    try:
        yield db
    finally:
        db.close()
