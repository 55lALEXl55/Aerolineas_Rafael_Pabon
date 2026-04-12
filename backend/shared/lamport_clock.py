"""
lamport_clock.py — Reloj de Lamport thread-safe
Regla: clock = max(local, recibido) + 1
"""
import threading


class LamportClock:
    def __init__(self, initial: int = 0):
        self._clock = initial
        self._lock = threading.Lock()

    def tick(self) -> int:
        """Incrementa el reloj local y retorna el nuevo valor."""
        with self._lock:
            self._clock += 1
            return self._clock

    def update(self, received: int) -> int:
        """
        Actualiza el reloj al recibir un mensaje con timestamp `received`.
        clock = max(local, received) + 1
        """
        with self._lock:
            self._clock = max(self._clock, received) + 1
            return self._clock

    @property
    def value(self) -> int:
        with self._lock:
            return self._clock

    def __repr__(self) -> str:
        return f"LamportClock(value={self.value})"
