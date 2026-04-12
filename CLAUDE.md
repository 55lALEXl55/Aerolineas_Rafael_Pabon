# Aerolíneas Rafael Pabón — CLAUDE.md

## Contexto del proyecto
Sistema distribuido de reservas aéreas para práctica universitaria SID1T7 - UNIVALLE Bolivia.
Docente: Ricardo Mendoza.

## Arquitectura
Monorepo con microservicios Python/FastAPI + React frontend + 3 BDs distribuidas.

```
aerolineas-rafael-pabon/
├── backend/
│   ├── services/
│   │   ├── ms-flights/     # puerto 8001
│   │   ├── ms-bookings/    # puerto 8002
│   │   ├── ms-routes/      # puerto 8003
│   │   ├── ms-sync/        # puerto 8004
│   │   ├── ms-tickets/     # puerto 8005
│   │   └── ms-dashboard/   # puerto 8006
│   └── shared/             # lamport_clock.py, vector_clock.py
├── frontend/               # React 18 + Vite + TailwindCSS
├── database/
│   ├── sqlserver/          # init_db1.sql, init_db2.sql
│   ├── mongodb/            # init_db3.js
│   └── seed/               # load_dataset.py
├── nginx/
├── docker-compose.yml
├── .env
└── Makefile
```

## Bases de datos
- DB1: SQL Server puerto 1433 → América (ATL, LAX, DFW, SAO) → IDs 1-99,999
- DB2: SQL Server puerto 1434 → Europa+MO (LON,PAR,FRA,IST,MAD,AMS,DXB) → IDs 100,000-499,999
- DB3: MongoDB puerto 27017 → Asia+Oceanía (PEK,TYO,SIN,CAN) → IDs 500,000+

## Reglas absolutas — NUNCA violar
1. NUNCA usar datetime en la BD. SIEMPRE BIGINT epoch unix.
2. NUNCA manipular fechas en el frontend. Solo enmascarar epoch con day.js.
3. NUNCA hacer dropdown de 60,000 vuelos. Usar fuzzy search (Fuse.js).
4. NUNCA sincronización espejo. Usar Transactional Replication + Change Streams.
5. El CAP elegido es AP (Disponibilidad + Tolerancia a Particiones).
6. Cada registro lleva: node_id INT, lamport_ts BIGINT, vector_clock VARCHAR '[0,0,0]', last_update_epoch BIGINT.

## Reglas de negocio críticas
- Reserva expira en 24h sin pago → cron job la libera automáticamente
- Al seleccionar asiento → estado LOCKED propagado a 3 nodos en <2s (máx 5 min)
- Refund: 15 min de delay de propagación (consistencia eventual modelada)
- Delay máximo entre nodos: 10 segundos
- Rutas: siempre priorizar más barata primero, luego más rápida
- No hay login. Solo rol pasajero.
- No se pueden cancelar vuelos.
- Rafael Pabón nunca se atrasa ni cambia precios.

## Flota de aviones
- IDs 1-6:   Airbus A380-800      → 10 primera + 439 turista = 449 asientos, 4 motores
- IDs 7-24:  Boeing 777-300ER     → 10 primera + 300 turista = 310 asientos, 2 motores
- IDs 25-35: Airbus A350-900      → 12 primera + 250 turista = 262 asientos, 2 motores
- IDs 36-50: Boeing 787-9 Dream.  →  8 primera + 220 turista = 228 asientos, 2 motores

## Estados de asiento
AVAILABLE → LOCKED → RESERVED (24h) → SOLD
RESERVED → REFUNDED → AVAILABLE (delay 15min)
Colores UI: Azul=AVAILABLE, Amarillo=RESERVED, Verde=SOLD, Rojo=REFUNDED, Gris=LOCKED

## Sincronización
- Lamport: clock = max(local, recibido) + 1
- Vector: [n1, n2, n3] — detecta causalidad y concurrencia
- Conflicto: causalidad > epoch > menor node_id

## Stack tecnológico
Backend: Python 3.12, FastAPI, SQLAlchemy, Motor (async MongoDB), APScheduler
Frontend: React 18, Vite, TailwindCSS, Zustand, Recharts, Leaflet, react-i18next, Fuse.js, day.js
Infra: Docker Compose, Nginx, SQL Server 2022, MongoDB 7

## Idiomas soportados
ES (default), EN, ZH (中文), PT (Português), AR (العربية)

## Evaluación
- 30 pts: Algoritmos Dijkstra/TSP
- 30 pts: UX/UI + Multiidioma (PUNTO FUERTE)
- 20 pts: Dashboard gerencial
- 10 pts: Sincronización 3 BDs
- 10 pts: PDF + Wallet

## Lo más importante
El aspecto VISUAL y la ARQUITECTURA son el punto fuerte.
Mostrar TODAS las operaciones en sus respectivas vistas.
Panel de consultas avanzadas desde la UI (no desde consola).
