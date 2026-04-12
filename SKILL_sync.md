# SKILL — Sincronización Distribuida
# Usar cuando: implementar Lamport, Vector Clocks, o propagación entre nodos

## LamportClock — implementación thread-safe
```python
import threading
import time

class LamportClock:
    def __init__(self, node_id: int):
        self.clock = 0
        self.node_id = node_id
        self._lock = threading.Lock()

    def tick(self) -> int:
        with self._lock:
            self.clock += 1
            return self.clock

    def update(self, received_ts: int) -> int:
        with self._lock:
            self.clock = max(self.clock, received_ts) + 1
            return self.clock

    def stamp(self) -> dict:
        with self._lock:
            return {"ts": self.clock, "node_id": self.node_id, "epoch": int(time.time())}
```

## VectorClock — implementación thread-safe
```python
import json
import threading

class VectorClock:
    def __init__(self, node_id: int, n_nodes: int = 3):
        self.vector = [0] * n_nodes
        self.node_id = node_id  # 0, 1, o 2 (índice)
        self._lock = threading.Lock()

    def tick(self) -> list:
        with self._lock:
            self.vector[self.node_id] += 1
            return self.vector.copy()

    def merge(self, other_vector: list) -> list:
        with self._lock:
            self.vector = [max(a, b) for a, b in zip(self.vector, other_vector)]
            self.vector[self.node_id] += 1
            return self.vector.copy()

    def happens_before(self, other: list) -> bool:
        with self._lock:
            return (all(a <= b for a, b in zip(self.vector, other)) and
                    any(a < b for a, b in zip(self.vector, other)))

    def is_concurrent(self, other: list) -> bool:
        with self._lock:
            not_before = not self.happens_before(other)
            not_after = not all(b <= a for a, b in zip(self.vector, other))
            return not_before and not_after

    def to_json(self) -> str:
        with self._lock:
            return json.dumps(self.vector)

    @classmethod
    def from_json(cls, json_str: str, node_id: int) -> 'VectorClock':
        vc = cls(node_id)
        vc.vector = json.loads(json_str)
        return vc
```

## Resolución de conflictos
```python
def resolve_conflict(local_record, remote_record) -> dict:
    """
    Retorna el registro que debe ganar.
    Prioridad: 1) causalidad clara → 2) mayor epoch → 3) menor node_id
    """
    local_vc = json.loads(local_record['vector_clock'])
    remote_vc = json.loads(remote_record['vector_clock'])
    vc = VectorClock(local_record['node_id'] - 1)
    vc.vector = local_vc

    if vc.happens_before(remote_vc):
        return remote_record  # remoto es posterior causalmente
    
    remote_vc_obj = VectorClock(remote_record['node_id'] - 1)
    remote_vc_obj.vector = remote_vc
    if remote_vc_obj.happens_before(local_vc):
        return local_record  # local es posterior causalmente

    # Son concurrentes → desempate por epoch
    if remote_record['last_update_epoch'] > local_record['last_update_epoch']:
        return remote_record
    if local_record['last_update_epoch'] > remote_record['last_update_epoch']:
        return local_record

    # Último desempate: menor node_id gana (DB1 > DB2 > DB3)
    return min(local_record, remote_record, key=lambda r: r['node_id'])
```

## Propagación de evento a los otros nodos
```python
import httpx
import asyncio

async def propagate_event(event_type: str, payload: dict, source_node: int):
    """
    Propaga un evento a los otros 2 nodos.
    Máximo delay: 10 segundos.
    """
    target_urls = {
        1: "http://ms-sync-node1:8004",
        2: "http://ms-sync-node2:8004",
        3: "http://ms-sync-node3:8004",
    }
    targets = [url for node_id, url in target_urls.items() if node_id != source_node]

    async def send_to_node(url: str):
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                await client.post(f"{url}/sync/receive", json={
                    "event_type": event_type,
                    "payload": payload,
                    "source_node": source_node,
                    "lamport_ts": payload.get("lamport_ts"),
                    "vector_clock": payload.get("vector_clock"),
                    "sent_epoch": int(time.time()),
                })
            except Exception as e:
                # Log pero no fallar — sistema AP
                logger.warning(f"Propagación a {url} falló: {e}")

    await asyncio.gather(*[send_to_node(url) for url in targets])
```

## SEAT LOCK — flujo de bloqueo
```python
async def lock_seat(seat_id: str, session_token: str, node_id: int):
    """
    1. Marca el asiento como LOCKED en el nodo local
    2. Propaga a los otros 2 nodos en <2s
    3. Si en 5 min no hay confirmación → auto-unlock
    """
    import time
    locked_until = int(time.time()) + 300  # 5 minutos

    lamport_ts = lamport_clock.tick()
    vector = vector_clock.tick()

    # 1. Actualizar local
    await update_seat_status(seat_id, 'LOCKED', {
        'locked_by': session_token,
        'locked_until_epoch': locked_until,
        'lamport_ts': lamport_ts,
        'vector_clock': json.dumps(vector),
        'last_update_epoch': int(time.time()),
    })

    # 2. Propagar (no esperar respuesta para no bloquear UI)
    asyncio.create_task(propagate_event('SEAT_LOCK', {
        'seat_id': seat_id,
        'session_token': session_token,
        'locked_until_epoch': locked_until,
        'lamport_ts': lamport_ts,
        'vector_clock': json.dumps(vector),
    }, source_node=node_id))

    return {'locked': True, 'expires_epoch': locked_until}
```

## REFUND — consistencia eventual 15 minutos
```python
import asyncio

async def schedule_refund_propagation(seat_id: str, delay_minutes: int = 15):
    """
    Simula la latencia bancaria.
    El asiento queda como REFUNDED localmente inmediatamente,
    pero se propaga a los otros nodos después de 15 min.
    """
    await asyncio.sleep(delay_minutes * 60)
    await propagate_event('SEAT_AVAILABLE', {
        'seat_id': seat_id,
        'lamport_ts': lamport_clock.tick(),
        'vector_clock': json.dumps(vector_clock.tick()),
    }, source_node=NODE_ID)
```

## sync_log — registrar todo evento
```python
async def log_sync_event(event_type, source_node, target_node, payload,
                          vc_sent, vc_recv=None, conflict=False,
                          resolution=None, latency_ms=0):
    await db.execute("""
        INSERT INTO sync_log
        (log_id, event_type, source_node, target_node, payload,
         vector_clock_sent, vector_clock_recv, conflict_detected,
         conflict_resolved, resolution_method, latency_ms, created_epoch)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [str(uuid7()), event_type, source_node, target_node,
          json.dumps(payload), json.dumps(vc_sent), json.dumps(vc_recv),
          conflict, conflict and resolution is not None,
          resolution, latency_ms, int(time.time())])
```
