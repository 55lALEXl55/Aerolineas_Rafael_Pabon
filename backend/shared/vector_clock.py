"""
vector_clock.py — Reloj vectorial thread-safe para 3 nodos
Nodos: 0=América, 1=Europa, 2=Asia  (índices, node_id - 1)
"""
import json
import threading
from typing import List


class VectorClock:
    def __init__(self, node_index: int, size: int = 3, initial: List[int] = None):
        """
        node_index: índice de este nodo (0-based). Para node_id=1 → 0, etc.
        size: número total de nodos.
        """
        if not (0 <= node_index < size):
            raise ValueError(f"node_index={node_index} fuera de rango [0,{size-1}]")
        self._node_index = node_index
        self._size = size
        self._clock: List[int] = initial[:] if initial else [0] * size
        self._lock = threading.Lock()

    # ─── Operaciones básicas ─────────────────────────────────────────────────

    def tick(self) -> List[int]:
        """Incrementa el componente local y retorna una copia del vector."""
        with self._lock:
            self._clock[self._node_index] += 1
            return self._clock[:]

    def merge(self, received: List[int]) -> List[int]:
        """
        Merge al recibir un mensaje: clock[i] = max(local[i], received[i]) + 1 en local.
        Incrementa primero el componente propio, luego toma máximos.
        """
        with self._lock:
            self._clock[self._node_index] += 1
            for i in range(self._size):
                if i != self._node_index:
                    self._clock[i] = max(self._clock[i], received[i])
            return self._clock[:]

    # ─── Comparaciones causales ──────────────────────────────────────────────

    @staticmethod
    def happens_before(vc_a: List[int], vc_b: List[int]) -> bool:
        """
        Retorna True si vc_a → vc_b (a ocurrió antes que b).
        Condición: vc_a[i] <= vc_b[i] para todo i,
                   y vc_a[j] < vc_b[j] para algún j.
        """
        if len(vc_a) != len(vc_b):
            raise ValueError("Vectores de distinto tamaño")
        leq = all(a <= b for a, b in zip(vc_a, vc_b))
        lt  = any(a < b  for a, b in zip(vc_a, vc_b))
        return leq and lt

    @staticmethod
    def is_concurrent(vc_a: List[int], vc_b: List[int]) -> bool:
        """
        Retorna True si vc_a || vc_b (concurrentes, sin relación causal).
        """
        a_before_b = VectorClock.happens_before(vc_a, vc_b)
        b_before_a = VectorClock.happens_before(vc_b, vc_a)
        return not a_before_b and not b_before_a

    # ─── Serialización ───────────────────────────────────────────────────────

    @property
    def value(self) -> List[int]:
        with self._lock:
            return self._clock[:]

    def to_string(self) -> str:
        """Serializa como '[n1,n2,n3]' para almacenar en BD."""
        return json.dumps(self.value, separators=(",", ":"))

    @classmethod
    def from_string(cls, node_index: int, vc_str: str) -> "VectorClock":
        """Crea un VectorClock desde la representación '[n1,n2,n3]'."""
        data = json.loads(vc_str)
        return cls(node_index=node_index, size=len(data), initial=data)

    # ─── Resolución de conflictos ─────────────────────────────────────────────

    @staticmethod
    def resolve_conflict(
        vc_a: List[int], epoch_a: int, node_id_a: int,
        vc_b: List[int], epoch_b: int, node_id_b: int,
    ) -> str:
        """
        Política CLAUDE.md: causalidad > epoch > menor node_id.
        Retorna 'a' o 'b' indicando cuál prevalece.
        """
        if VectorClock.happens_before(vc_a, vc_b):
            return "b"
        if VectorClock.happens_before(vc_b, vc_a):
            return "a"
        # Concurrentes → desempate por epoch
        if epoch_a != epoch_b:
            return "a" if epoch_a > epoch_b else "b"
        # Mismo epoch → menor node_id gana
        return "a" if node_id_a <= node_id_b else "b"

    def __repr__(self) -> str:
        return f"VectorClock(node={self._node_index}, value={self.value})"
