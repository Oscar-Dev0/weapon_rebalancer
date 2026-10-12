"""Acceso al panel: enlace de un solo uso que rota, sesiones con caducidad, rotación de clave y bloqueo."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from weapon_rebalancer.api.auth import GRACE_SECONDS, AuthManager, AuthSettings, read_token_file
from weapon_rebalancer.api.server import Api, Handler
from weapon_rebalancer.services.app import App


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


class AuthTests(unittest.TestCase):
    def make(self, **settings) -> tuple[AuthManager, Clock]:
        clock = Clock()
        return AuthManager(AuthSettings(**settings), clock=clock), clock

    def test_access_token_rotates_with_time(self) -> None:
        auth, clock = self.make(rotate_minutes=30)
        first = auth.access_token()
        clock.now += 29 * 60
        self.assertEqual(auth.access_token(), first)
        clock.now += 2 * 60
        self.assertNotEqual(auth.access_token(), first)
        self.assertIsNone(auth.login(first, '127.0.0.1'))

    def test_login_is_single_use(self) -> None:
        auth, _ = self.make()
        token = auth.access_token()
        self.assertIsNotNone(auth.login(token, '127.0.0.1'))
        self.assertIsNone(auth.login(token, '127.0.0.1'))

    def test_session_expires_when_idle_or_too_old(self) -> None:
        auth, clock = self.make(idle_minutes=30, max_hours=2, key_rotate_minutes=1000)
        session = auth.login(auth.access_token(), '127.0.0.1')
        clock.now += 31 * 60
        self.assertIsNone(auth.session(session.sid, '127.0.0.1'))
        session = auth.login(auth.access_token(), '127.0.0.1')
        for _ in range(9):  # activo cada 15 min, pero más de 2 h en total
            clock.now += 15 * 60
            found = auth.session(session.sid, '127.0.0.1')
            if found is None:
                break
            auth.touch(found)
        self.assertIsNone(auth.session(session.sid, '127.0.0.1'))

    def test_session_is_bound_to_ip(self) -> None:
        auth, _ = self.make()
        session = auth.login(auth.access_token(), '127.0.0.1')
        self.assertIsNone(auth.session(session.sid, '10.0.0.5'))

    def test_key_rotation_with_grace(self) -> None:
        auth, clock = self.make(key_rotate_minutes=10, idle_minutes=60)
        session = auth.login(auth.access_token(), '127.0.0.1')
        old_sid, old_key = session.sid, session.key
        clock.now += 11 * 60
        new_key = auth.touch(session)
        self.assertTrue(new_key)
        self.assertNotEqual(new_key, old_key)
        # Durante la gracia valen la cookie y la clave anteriores (peticiones en vuelo).
        self.assertIs(auth.session(old_sid, '127.0.0.1'), session)
        self.assertTrue(auth.check_key(session, old_key, '127.0.0.1'))
        clock.now += GRACE_SECONDS + 1
        self.assertIsNone(auth.session(old_sid, '127.0.0.1'))
        self.assertFalse(auth.check_key(session, old_key, '127.0.0.1'))
        self.assertTrue(auth.check_key(session, new_key, '127.0.0.1'))

    def test_failures_lock_out_and_rotate_access(self) -> None:
        auth, clock = self.make(max_failures=3, lockout_minutes=10)
        token = auth.access_token()
        for _ in range(3):
            self.assertIsNone(auth.login('mal', '127.0.0.1'))
        self.assertGreater(auth.locked('127.0.0.1'), 0)
        self.assertNotEqual(auth.access_token(), token)
        # Bloqueado: ni el enlace correcto deja entrar.
        self.assertIsNone(auth.login(auth.access_token(), '127.0.0.1'))
        clock.now += 11 * 60
        self.assertEqual(auth.locked('127.0.0.1'), 0)
        self.assertIsNotNone(auth.login(auth.access_token(), '127.0.0.1'))

    def test_logout(self) -> None:
        auth, _ = self.make()
        session = auth.login(auth.access_token(), '127.0.0.1')
        auth.logout(session)
        self.assertIsNone(auth.session(session.sid, '127.0.0.1'))

    def test_token_file_is_private_and_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'panel_access.json'
            auth = AuthManager(base_url='http://127.0.0.1:1', token_file=path)
            data = read_token_file(path)
            self.assertEqual(data['url'], auth.access_url)
            self.assertEqual(path.stat().st_mode & 0o077, 0)
            auth.login(auth.access_token(), '127.0.0.1')
            self.assertEqual(json.loads(path.read_text())['url'], auth.access_url)
            auth.stop()
            self.assertFalse(path.exists())


class HttpRotationTests(unittest.TestCase):
    def test_key_and_cookie_rotate_over_http(self) -> None:
        clock = Clock()
        auth = AuthManager(AuthSettings(key_rotate_minutes=10, idle_minutes=60), clock=clock)
        handler = type('H', (Handler,), {'api': Api(App()), 'auth': auth, 'allowed_hosts': set()})
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        port = httpd.server_address[1]
        handler.allowed_hosts = {f'127.0.0.1:{port}'}
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{port}'

        def call(path, cookie, key=None):
            req = urllib.request.Request(base + path)
            req.add_header('Cookie', cookie)
            if key:
                req.add_header('X-WR-Token', key)
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    return r.status, dict(r.headers), r.read().decode()
            except urllib.error.HTTPError as exc:
                return exc.code, dict(exc.headers), exc.read().decode()
        try:
            session = auth.login(auth.access_token(), '127.0.0.1')
            cookie, key = f'wr_session={session.sid}', session.key
            status, headers, _ = call('/api/session', cookie, key)
            self.assertEqual(status, 200)
            self.assertNotIn('X-WR-Token-Next', headers)
            clock.now += 11 * 60
            status, headers, _ = call('/api/session', cookie, key)
            self.assertEqual(status, 200)
            new_key = headers['X-WR-Token-Next']
            new_cookie = headers['Set-Cookie'].split(';')[0]
            self.assertNotEqual(new_key, key)
            self.assertEqual(call('/api/session', new_cookie, new_key)[0], 200)
            self.assertEqual(call('/api/session', cookie, key)[0], 200)  # gracia
            clock.now += GRACE_SECONDS + 1
            self.assertEqual(call('/api/session', cookie, key)[0], 401)
            self.assertEqual(call('/js/main.js', cookie)[0], 401)
            self.assertEqual(call('/api/session', new_cookie, new_key)[0], 200)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == '__main__':
    unittest.main()
