# SKILL — Backend FastAPI Microservicio
# Usar cuando: crear o modificar cualquier microservicio Python/FastAPI

## Patrón de estructura de cada microservicio
```
ms-nombre/
├── main.py           # FastAPI app, CORS, lifespan, health check
├── models.py         # Pydantic schemas (request/response)
├── database.py       # conexión a BD (SQLAlchemy o Motor)
├── routes/
│   ├── __init__.py
│   └── nombre.py     # endpoints agrupados por recurso
├── services/
│   └── nombre.py     # lógica de negocio separada de los endpoints
├── requirements.txt
└── Dockerfile
```

## main.py — plantilla obligatoria
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import time

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: inicializar BD, Lamport clock, etc.
    yield
    # shutdown: cerrar conexiones

app = FastAPI(
    title="ms-nombre",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "ms-nombre", "ts": int(time.time())}
```

## Fechas — regla crítica
```python
import time

# CORRECTO — siempre epoch BIGINT
created_epoch: int = int(time.time())
expires_epoch: int = int(time.time()) + 86400  # +24h

# INCORRECTO — NUNCA hacer esto
from datetime import datetime
created_at = datetime.now()  # PROHIBIDO
```

## Lamport + Vector en cada operación
```python
# Al crear/modificar cualquier registro:
lamport_ts = lamport_clock.tick()
vector_clock = json.dumps(vector_clk.tick())
last_update_epoch = int(time.time())
```

## Respuesta de error estándar
```python
from fastapi import HTTPException

raise HTTPException(
    status_code=404,
    detail={"error": "FLIGHT_NOT_FOUND", "message": "Vuelo no encontrado", "epoch": int(time.time())}
)
```

## Paginación estándar
```python
@app.get("/items")
async def list_items(page: int = 1, size: int = 20, ...):
    offset = (page - 1) * size
    # query con OFFSET/LIMIT
    return {
        "data": items,
        "page": page,
        "size": size,
        "total": total_count,
        "pages": ceil(total_count / size)
    }
```

## Variables de entorno requeridas (.env)
```
NODE_ID=1
DB1_URL=mssql+pyodbc://sa:Password123!@sqlserver1:1433/rafael_pabon?driver=ODBC+Driver+18+for+SQL+Server
DB2_URL=mssql+pyodbc://sa:Password123!@sqlserver2:1434/rafael_pabon?driver=ODBC+Driver+18+for+SQL+Server
DB3_URL=mongodb://mongodb:27017/rafael_pabon
MS_FLIGHTS_URL=http://ms-flights:8001
MS_BOOKINGS_URL=http://ms-bookings:8002
MS_ROUTES_URL=http://ms-routes:8003
MS_SYNC_URL=http://ms-sync:8004
MS_TICKETS_URL=http://ms-tickets:8005
MS_DASHBOARD_URL=http://ms-dashboard:8006
REFUND_DELAY_MINUTES=15
LOCK_TIMEOUT_MINUTES=5
RESERVATION_TIMEOUT_HOURS=24
SYNC_MAX_DELAY_SECONDS=10
```
