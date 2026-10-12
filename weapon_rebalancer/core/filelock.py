"""Bloqueo entre procesos (panel web y terminal) para operaciones que escriben.

Usa `fcntl.flock` en Linux/macOS y `msvcrt.locking` en Windows. El bloqueo se libera
solo si el proceso muere, así que nunca queda “trabado”.
"""
from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from typing import Iterator

from .errors import Conflict
from .paths import data_dir

_THREAD_LOCKS: dict[str, threading.RLock] = {}
_GUARD = threading.Lock()


def _thread_lock(name: str) -> threading.RLock:
    with _GUARD:
        return _THREAD_LOCKS.setdefault(name, threading.RLock())


def _try_lock(handle) -> bool:
    try:
        if os.name == 'nt':
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(handle) -> None:
    try:
        if os.name == 'nt':
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


@contextmanager
def file_lock(name: str, timeout: float = 15.0) -> Iterator[None]:
    """Exclusión mutua por nombre entre hilos y procesos. Reentrante dentro del mismo hilo."""
    lock = _thread_lock(name)
    with lock:
        holder = getattr(_LOCAL, name, 0)
        if holder:
            setattr(_LOCAL, name, holder + 1)
            try:
                yield
            finally:
                setattr(_LOCAL, name, getattr(_LOCAL, name) - 1)
            return
        path = data_dir('locks') / f'{name}.lock'
        with open(path, 'a+b') as handle:
            started = time.monotonic()
            while not _try_lock(handle):
                if time.monotonic() - started > timeout:
                    raise Conflict('Otra operación está escribiendo (panel web o terminal).',
                                   hint='Espera unos segundos y vuelve a intentarlo.')
                time.sleep(0.05)
            setattr(_LOCAL, name, 1)
            try:
                yield
            finally:
                setattr(_LOCAL, name, 0)
                _unlock(handle)


_LOCAL = threading.local()
