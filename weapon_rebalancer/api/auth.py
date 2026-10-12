"""Acceso al panel: token de entrada rotativo y de un solo uso, sesiones con caducidad y bloqueo por fallos.

Flujo:
1. La consola (y `wr.py token`) muestra `http://…/?token=<acceso>`. El token de acceso sirve **una vez**:
   al usarlo se crea una sesión y se genera otro. Además rota solo cada `rotate_minutes`.
2. La sesión vive en una cookie HttpOnly (`wr_session`). Cada llamada a /api lleva además la
   clave de la sesión en `X-WR-Token` (protección CSRF). Sesión y clave rotan cada `key_rotate_minutes`
   (la respuesta trae `X-WR-Token-Next`; la anterior sigue valiendo `GRACE_SECONDS`).
3. La sesión caduca tras `idle_minutes` sin uso o `max_hours` desde que se abrió.
4. `max_failures` credenciales incorrectas en `FAILURE_WINDOW` bloquean nuevas entradas desde esa IP
   durante `lockout_minutes` y rotan el token de acceso.

Sin sesión válida el servidor no entrega nada: ni la página, ni JS, CSS o documentación.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..core.jsonlog import log

FAILURE_WINDOW = 600.0
GRACE_SECONDS = 120.0


@dataclass
class Session:
    sid: str
    key: str
    ip: str
    created: float
    last_seen: float
    rotated: float
    previous_sid: str = ''
    previous_key: str = ''
    previous_until: float = 0.0


@dataclass
class AuthSettings:
    rotate_minutes: float = 30.0
    idle_minutes: float = 30.0
    max_hours: float = 8.0
    key_rotate_minutes: float = 10.0
    max_failures: int = 8
    lockout_minutes: float = 10.0


@dataclass
class _Failures:
    times: deque = field(default_factory=deque)
    locked_until: float = 0.0


class AuthManager:
    def __init__(self, settings: AuthSettings | None = None, *, base_url: str = '', token_file: Path | None = None,
                 on_rotate: Callable[[str], None] | None = None, clock: Callable[[], float] = time.time,
                 initial_token: str | None = None) -> None:
        self.settings = settings or AuthSettings()
        self.base_url = base_url
        self.token_file = token_file
        self.on_rotate = on_rotate
        self.clock = clock
        self._lock = threading.RLock()
        self._sessions: dict[str, Session] = {}
        self._failures: dict[str, _Failures] = {}
        self._access = ''
        self._access_expires = 0.0
        self._stop = threading.Event()
        self.rotate_access('arranque', token=initial_token)

    # ---- token de acceso -------------------------------------------------------------
    @property
    def access_url(self) -> str:
        return f'{self.base_url}/?token={self._access}'

    def access_token(self) -> str:
        with self._lock:
            if self.clock() >= self._access_expires:
                self.rotate_access('caducado')
            return self._access

    def rotate_access(self, reason: str, *, token: str | None = None) -> str:
        with self._lock:
            self._access = token or secrets.token_urlsafe(32)
            self._access_expires = self.clock() + self.settings.rotate_minutes * 60
            self._write_token_file()
        if reason != 'arranque':
            log('auth.access_rotated', reason=reason)
            if self.on_rotate:
                self.on_rotate(reason)
        return self._access

    def _write_token_file(self) -> None:
        if not self.token_file:
            return
        payload = {'url': self.access_url, 'expires_at': int(self._access_expires), 'pid': os.getpid(),
                   'note': 'Token de un solo uso del panel. Lo reescribe wr.py serve; no lo compartas.'}
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.token_file.with_suffix('.tmp')
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle)
        os.replace(tmp, self.token_file)

    def clear_token_file(self) -> None:
        if self.token_file and self.token_file.is_file():
            try:
                data = json.loads(self.token_file.read_text(encoding='utf-8'))
                if data.get('pid') == os.getpid():
                    self.token_file.unlink()
            except (OSError, ValueError):
                pass

    def start_rotation_thread(self) -> None:
        def loop() -> None:
            while not self._stop.wait(15):
                self.access_token()
                self.prune()
        threading.Thread(target=loop, name='wr-auth-rotation', daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        self.clear_token_file()

    # ---- bloqueo por fallos ----------------------------------------------------------
    def locked(self, ip: str) -> float:
        """Segundos de bloqueo restantes para esa IP (0 = no bloqueada)."""
        with self._lock:
            entry = self._failures.get(ip)
            if not entry:
                return 0.0
            return max(0.0, entry.locked_until - self.clock())

    def fail(self, ip: str, reason: str) -> None:
        with self._lock:
            now = self.clock()
            entry = self._failures.setdefault(ip, _Failures())
            entry.times.append(now)
            while entry.times and now - entry.times[0] > FAILURE_WINDOW:
                entry.times.popleft()
            log('auth.failure', level='warning', ip=ip, reason=reason, count=len(entry.times))
            if len(entry.times) >= self.settings.max_failures and entry.locked_until <= now:
                entry.locked_until = now + self.settings.lockout_minutes * 60
                entry.times.clear()
                log('auth.lockout', level='warning', ip=ip, minutes=self.settings.lockout_minutes)
                self.rotate_access(f'bloqueo de {ip} por intentos fallidos')

    # ---- sesiones --------------------------------------------------------------------
    def login(self, candidate: str, ip: str) -> Session | None:
        """Canjea el token de acceso por una sesión. El token queda gastado."""
        with self._lock:
            if self.locked(ip):
                return None
            if not candidate or not secrets.compare_digest(candidate, self.access_token()):
                self.fail(ip, 'token de acceso incorrecto o ya usado')
                return None
            now = self.clock()
            session = Session(secrets.token_urlsafe(32), secrets.token_urlsafe(32), ip, now, now, now)
            self._sessions[session.sid] = session
            log('auth.login', ip=ip)
            self.rotate_access('usado para iniciar sesión')
            return session

    def _expired(self, session: Session, now: float) -> bool:
        return (now - session.last_seen > self.settings.idle_minutes * 60
                or now - session.created > self.settings.max_hours * 3600)

    def session(self, sid: str | None, ip: str) -> Session | None:
        """Sesión de la cookie (también el identificador anterior durante la gracia)."""
        if not sid:
            return None
        with self._lock:
            now = self.clock()
            found = self._sessions.get(sid)
            if found is None:
                found = next((s for s in self._sessions.values()
                              if s.previous_sid and now < s.previous_until and secrets.compare_digest(s.previous_sid, sid)), None)
            if found is None or found.ip != ip:
                return None
            if self._expired(found, now):
                self._drop(found.sid)
                return None
            return found

    def check_key(self, session: Session, key: str, ip: str) -> bool:
        with self._lock:
            now = self.clock()
            ok = bool(key) and (secrets.compare_digest(key, session.key)
                                or (session.previous_key and now < session.previous_until
                                    and secrets.compare_digest(key, session.previous_key)))
            if not ok:
                self.fail(ip, 'clave de sesión incorrecta')
            return bool(ok)

    def touch(self, session: Session, *, rotate: bool = True) -> str | None:
        """Marca actividad y, si toca y `rotate`, rota identificador y clave. Devuelve la clave nueva (o None).

        Solo se rota en respuestas que pueden entregar la clave nueva al panel (API e index)."""
        with self._lock:
            now = self.clock()
            session.last_seen = now
            if not rotate or now - session.rotated < self.settings.key_rotate_minutes * 60:
                return None
            self._sessions.pop(session.sid, None)
            session.previous_sid, session.previous_key = session.sid, session.key
            session.previous_until = now + GRACE_SECONDS
            session.sid, session.key, session.rotated = secrets.token_urlsafe(32), secrets.token_urlsafe(32), now
            self._sessions[session.sid] = session
            return session.key

    def logout(self, session: Session) -> None:
        with self._lock:
            self._drop(session.sid)
            log('auth.logout', ip=session.ip)

    def _drop(self, sid: str) -> None:
        self._sessions.pop(sid, None)

    def prune(self) -> None:
        with self._lock:
            now = self.clock()
            for sid in [s.sid for s in self._sessions.values() if self._expired(s, now)]:
                self._drop(sid)

    def info(self, session: Session) -> dict:
        s = self.settings
        return {
            'expires_idle_at': int(session.last_seen + s.idle_minutes * 60),
            'expires_at': int(session.created + s.max_hours * 3600),
            'idle_minutes': s.idle_minutes, 'max_hours': s.max_hours,
            'key_rotate_minutes': s.key_rotate_minutes, 'access_rotate_minutes': s.rotate_minutes,
            'max_failures': s.max_failures, 'lockout_minutes': s.lockout_minutes,
            'active_sessions': len(self._sessions),
        }


def read_token_file(path: Path) -> dict | None:
    """Lee el token vigente que escribió `wr.py serve` (None si no hay panel corriendo)."""
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    pid = data.get('pid')
    # En Windows os.kill(pid, 0) TERMINA el proceso: allí no se comprueba.
    if isinstance(pid, int) and os.name != 'nt':
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return None
        except PermissionError:
            pass
    return data
