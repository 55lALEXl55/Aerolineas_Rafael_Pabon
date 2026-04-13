# PROGRESS.md — Aerolíneas Rafael Pabón v1.0
> Generado el: 2026-04-12 | Estado: **COMPLETO**

---

## Resumen ejecutivo

| Componente | Estado |
|---|---|
| Infraestructura Docker (9 servicios) | ✅ 100% |
| Bases de datos (DB1 SQL Server, DB2 SQL Server, DB3 MongoDB) | ✅ 100% |
| Seed 60 000 vuelos distribuidos | ✅ 100% |
| ms-flights (búsqueda, asientos, Lamport/Vector) | ✅ 100% |
| ms-bookings (lock→reserve→purchase→refund) | ✅ 100% |
| ms-routes (Dijkstra puro + TSP 2-opt) | ✅ 100% |
| ms-sync (propagación, relojes distribuidos) | ✅ 100% |
| ms-tickets (PDF boarding pass + Apple Wallet) | ✅ 100% |
| ms-dashboard (9 endpoints KPI) | ✅ 100% |
| Frontend React (6 páginas, i18n 5 idiomas) | ✅ 100% |
| Nginx API Gateway | ✅ 100% |
| **Total global** | **✅ 100%** |

---

## Levantar el proyecto desde cero

```bash
# Requisitos previos
# - Docker Desktop corriendo (mínimo 4 GB RAM para SQL Server)
# - Puertos libres: 80, 1433, 1434, 27017, 8001-8006

# 1. Clonar el repositorio
git clone <repo-url> && cd aerolineas-rafael-pabon

# 2. Levantar todos los contenedores
make up
# equivale a: docker-compose up --build -d

# 3. Esperar ~45s para que SQL Server y MongoDB inicialicen
# Verificar que los servicios están sanos:
make health

# 4. Cargar el dataset de 60 000 vuelos
make seed
# equivale a: docker exec -i sqlserver1 ... && python database/seed/load_dataset.py

# 5. Abrir el navegador
# Frontend: http://localhost
# API docs ms-flights:  http://localhost:8001/docs
# API docs ms-bookings: http://localhost:8002/docs
```

### Comandos de mantenimiento

```bash
make up       # Levantar todo
make down     # Detener todo
make logs     # Ver logs de todos los servicios
make seed     # Recargar los datos
make reset    # Limpiar todo (volúmenes incluidos)
make status   # Estado de contenedores
make health   # Verificar que todos los endpoints /health responden
```

---

## Todos los endpoints disponibles

### Nginx API Gateway — http://localhost

| Prefijo nginx | Microservicio | Puerto |
|---|---|---|
| `/api/flights/` | ms-flights | 8001 |
| `/api/bookings/` | ms-bookings | 8002 |
| `/api/routes/` | ms-routes | 8003 |
| `/api/sync/` | ms-sync | 8004 |
| `/api/tickets/` | ms-tickets | 8005 |
| `/api/dashboard/` | ms-dashboard | 8006 |

---

### ms-flights (puerto 8001)

| Método | URL | Descripción |
|---|---|---|
| GET | `/api/flights/search?origin=ATL&destination=FRA&date_epoch=1776029407&seat_class=ECONOMY` | Búsqueda de vuelos directos |
| GET | `/api/flights/{flight_id}` | Detalle completo del vuelo |
| GET | `/api/flights/{flight_id}/seats` | Lista de asientos con estados |
| GET | `/api/flights/{flight_id}/stats` | Estadísticas + lista de pasajeros |
| PUT | `/api/flights/{flight_id}/status` | Actualizar estado del vuelo |
| GET | `/api/flights/seats/query?flight_id=X&status=AVAILABLE` | Consulta avanzada de asientos |
| GET | `/api/flights?origin=ATL&limit=50` | Listado general de vuelos |
| GET | `/api/flights/aircraft` | Lista de aeronaves |

---

### ms-bookings (puerto 8002)

| Método | URL | Body | Descripción |
|---|---|---|---|
| POST | `/api/bookings/lock` | `{seat_id, flight_id, session_token}` | Bloquear asiento 5 min |
| POST | `/api/bookings/reserve` | `{seat_id, flight_id, session_token, passport, full_name}` | Reservar asiento 24h |
| POST | `/api/bookings/purchase` | `{seat_id, flight_id, session_token, passport, full_name}` | Comprar (SOLD) |
| POST | `/api/bookings/cancel-ticket` | `{ticket_id}` | Cancelar reserva RESERVED |
| POST | `/api/bookings/refund-ticket` | `{ticket_id}` | Reembolso con 15 min delay |
| GET  | `/api/bookings/passenger/{passport}` | — | Historial del pasajero |

---

### ms-routes (puerto 8003)

| Método | URL | Descripción |
|---|---|---|
| GET | `/api/routes/shortest?origin=ATL&destination=LON&date_epoch=X&mode=price` | Dijkstra: ruta óptima precio/tiempo |
| GET | `/api/routes/tsp?airports=ATL,FRA,LON,PEK&date_epoch=X` | TSP nearest-neighbor + 2-opt |
| GET | `/api/routes/available?origin=ATL&date_epoch=X` | Destinos alcanzables desde origen |
| GET | `/api/routes/all-airports` | Lista de 15 aeropuertos con coordenadas |
| GET | `/api/routes/cost-matrix` | Matriz de costos entre aeropuertos |

---

### ms-sync (puerto 8004)

| Método | URL | Descripción |
|---|---|---|
| GET  | `/api/sync/status` | Estado de los 3 nodos + servicios |
| GET  | `/api/sync/clock` | Estado del reloj Lamport + Vector |
| POST | `/api/sync/clock/tick` | Incrementar reloj Lamport |
| POST | `/api/sync/events` | Recibir evento de propagación |
| GET  | `/api/sync/log?limit=50` | Log de últimos eventos de sincronización |
| GET  | `/api/sync/stats` | Métricas: conflictos, latencias |

---

### ms-tickets (puerto 8005)

| Método | URL | Descripción |
|---|---|---|
| GET  | `/api/tickets/{ticket_id}` | Detalle del ticket |
| GET  | `/api/tickets/{ticket_id}/pdf` | Boarding pass PDF (descarga) |
| GET  | `/api/tickets/{ticket_id}/wallet` | Apple Wallet `.pkpass` |
| GET  | `/api/tickets/passenger/{passport}` | Tickets de un pasajero |
| GET  | `/api/tickets/flight/{flight_id}` | Todos los tickets de un vuelo |
| POST | `/api/tickets/{ticket_id}/refund` | Iniciar reembolso |
| POST | `/api/tickets/generate-demo` | PDF de demostración (datos aleatorios) |

---

### ms-dashboard (puerto 8006)

| Método | URL | Descripción |
|---|---|---|
| GET | `/api/dashboard/overview` | KPIs globales: revenue, vuelos, asientos (3 nodos) |
| GET | `/api/dashboard/revenue-by-route` | Top rutas por ingreso |
| GET | `/api/dashboard/top-flights` | Top vuelos por % ocupación |
| GET | `/api/dashboard/fleet-status` | 50 aeronaves con especificaciones |
| GET | `/api/dashboard/flights-by-status` | Distribución por estado |
| GET | `/api/dashboard/sync/status` | Proxy → ms-sync: estado de nodos |
| GET | `/api/dashboard/sync/log` | Proxy → ms-sync: log de eventos |
| GET | `/api/dashboard/purchases-by-city` | Compras agrupadas por ciudad |
| GET | `/api/dashboard/reservations-expiring?hours=2` | Reservas próximas a expirar |
| GET | `/api/dashboard/aircraft/{model}` | Ficha técnica del avión |

---

## Pruebas end-to-end

```bash
# 1. Buscar vuelos ATL→FRA (los hay directos en el seed)
curl "http://localhost/api/flights/search?origin=ATL&destination=FRA&date_epoch=1776029407&seat_class=ECONOMY"

# 2. Ver asientos del vuelo 2326
curl "http://localhost/api/flights/2326/seats"

# 3. Bloquear un asiento
curl -X POST http://localhost/api/bookings/lock \
  -H "Content-Type: application/json" \
  -d '{"seat_id": 678347, "flight_id": 2326, "session_token": "test-123"}'

# 4. Reservar
curl -X POST http://localhost/api/bookings/reserve \
  -H "Content-Type: application/json" \
  -d '{"seat_id": 678347, "flight_id": 2326, "session_token": "test-123", "passport": "TEST001", "full_name": "Juan Test"}'

# 5. Comprar
curl -X POST http://localhost/api/bookings/purchase \
  -H "Content-Type: application/json" \
  -d '{"seat_id": 678347, "flight_id": 2326, "session_token": "test-123", "passport": "TEST001", "full_name": "Juan Test"}'

# 6. Descargar PDF del ticket (reemplaza TICKET_ID)
curl "http://localhost/api/tickets/1/pdf" -o boarding.pdf

# 7. Dashboard gerencial
curl "http://localhost/api/dashboard/overview"

# 8. Estado de sincronización
curl "http://localhost/api/sync/status"
```

**Nota:** Para pruebas en fechas reales usar epoch del día actual:
```bash
python3 -c "import time; print(int(time.mktime(time.strptime('2026-04-12', '%Y-%m-%d'))))"
# 1775966400
```

---

## Arquitectura resumida

```
Browser ──► Nginx :80
              │
              ├── /api/flights/   ──► ms-flights  :8001 ──► DB1 (SQL Server :1433) América
              ├── /api/bookings/  ──► ms-bookings :8002 ──► DB1 + DB2 + DB3
              ├── /api/routes/    ──► ms-routes   :8003 ──► DB1 + DB2 + DB3 (Dijkstra)
              ├── /api/sync/      ──► ms-sync     :8004 ──► DB1 + DB2 + DB3 (sync log)
              ├── /api/tickets/   ──► ms-tickets  :8005 ──► DB1 + DB2 + DB3
              ├── /api/dashboard/ ──► ms-dashboard:8006 ──► DB1 + DB2 + DB3 (agregado)
              └── /               ──► React build (servido desde nginx)

Bases de datos:
  DB1 SQL Server :1433 — América (ATL, LAX, DFW, SAO)           IDs 1-99 999
  DB2 SQL Server :1434 — Europa + Medio Oriente (LON,PAR,...)   IDs 100 000-499 999
  DB3 MongoDB    :27017 — Asia + Oceanía (PEK, TYO, SIN, CAN)   IDs 500 000+
```

---

## Decisiones técnicas

### CAP = AP (Disponibilidad + Tolerancia a Particiones)

Se eligió AP sobre CP. Cada microservicio sigue funcionando aunque un nodo esté caído:
- `ms-bookings` bloquea y reserva aunque ms-sync no esté disponible (fire-and-forget)
- `ms-flights` sirve búsquedas de la BD disponible aunque otra esté caída
- `ms-routes` retorna ruta teórica si no puede verificar disponibilidad en ms-flights

### Lamport Clocks

Cada operación de escritura incrementa el reloj Lamport local y lo persiste en la columna `lamport_ts BIGINT`. Al recibir un evento, se aplica `max(local, recibido) + 1`. Garantiza orden parcial causal.

### Vector Clocks `[n1, n2, n3]`

Tres posiciones, una por nodo. Se persiste como `vector_clock VARCHAR '[n1,n2,n3]'`.
- `tick()`: incrementa la posición del nodo local
- `merge()`: `max(v_i, w_i)` para cada posición
- `happens_before()`: `∀i: v_i ≤ w_i && ∃j: v_j < w_j`
- `is_concurrent()`: ninguno happens-before el otro

### Resolución de conflictos

`causalidad > epoch reciente > menor node_id`

### Sincronización

- `ms-sync` tiene un APScheduler que cada 10s procesa la cola de `sync_log` y propaga cambios a los nodos destino
- No se implementaron Change Streams de MongoDB (se usa polling), pero la semántica eventual es idéntica al diseño

### Estados de asientos

```
AVAILABLE → (lock) → LOCKED → (reserve) → RESERVED → (purchase) → SOLD
RESERVED → (cancel) → AVAILABLE
SOLD → (refund, 15min delay) → REFUNDED → AVAILABLE
```

Cron jobs:
- Cada 1 min: libera asientos LOCKED expirados (>5 min)
- Cada 5 min: libera reservas RESERVED expiradas (>24 h)

### Sin fechas en BD

Todas las fechas se almacenan como `BIGINT` epoch Unix. El frontend usa `day.js` exclusivamente para mostrar fechas. Nunca se manipulan fechas en el frontend.

### Routing de datos por aeropuerto

```python
DB1_AIRPORTS = {"ATL", "LAX", "DFW", "SAO"}
DB2_AIRPORTS = {"LON", "PAR", "FRA", "IST", "MAD", "AMS", "DXB"}
DB3_AIRPORTS = {"PEK", "TYO", "SIN", "CAN"}  # → MongoDB
```

Cada operación de vuelo/reserva consulta la BD correspondiente al aeropuerto de origen.

### Flota de aviones

| Modelo | IDs | Asientos |
|---|---|---|
| Airbus A380-800 | 1-6 | 10 primera + 439 eco = 449 |
| Boeing 777-300ER | 7-24 | 10 primera + 300 eco = 310 |
| Airbus A350-900 | 25-35 | 12 primera + 250 eco = 262 |
| Boeing 787-9 | 36-50 | 8 primera + 220 eco = 228 |

---

## Variables de entorno (.env)

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `DB1_PASSWORD` | `Rafael_Pabon_2024!` | SA password SQL Server DB1 |
| `DB2_PASSWORD` | `Rafael_Pabon_2024!` | SA password SQL Server DB2 |
| `DB3_USER` | `admin` | Usuario MongoDB |
| `DB3_PASSWORD` | `Rafael_Pabon_2024!` | Password MongoDB |
| `DB3_NAME` | `aerolineas` | Base de datos MongoDB |
| `NODE_ID_AMERICA` | `1` | Node ID para ms-flights/bookings |

---

## Notas de producción

1. Cambiar todas las passwords en `.env` antes de desplegar
2. El endpoint `/api/dashboard/overview` puede tardar 45-60s con 60 000 vuelos (timeout nginx = 120s)
3. SQL Server requiere al menos 2 GB de RAM por instancia (4 GB total solo para las BDs)
4. El seed script (`make seed`) tarda ~10-15 min para 60 000 vuelos
