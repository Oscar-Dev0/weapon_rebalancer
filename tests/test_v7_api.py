from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from weapon_rebalancer.api.auth import AuthManager
from weapon_rebalancer.api.server import Api, Handler
from weapon_rebalancer.services.app import App


class ApiSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.auth = AuthManager(initial_token='acceso-de-prueba')
        handler = type('H', (Handler,), {'api': Api(App()), 'auth': cls.auth, 'allowed_hosts': set()})
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        port = cls.httpd.server_address[1]
        handler.allowed_hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        cls.base = f'http://127.0.0.1:{port}'
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.cookie, cls.token = cls.login()

    @classmethod
    def login(cls) -> tuple[str, str]:
        """Canjea el enlace de acceso vigente por una sesión: (cookie, clave de la API)."""
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        opener = urllib.request.build_opener(NoRedirect)
        try:
            opener.open(f'{cls.base}/?token={cls.auth.access_token()}', timeout=10)
        except urllib.error.HTTPError as exc:
            assert exc.code == 303, exc.code
            cookie = exc.headers['Set-Cookie'].split(';')[0]
        req = urllib.request.Request(cls.base + '/')
        req.add_header('Cookie', cookie)
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode('utf-8')
        key = body.split('name="wr-token" content="')[1].split('"')[0]
        return cookie, key

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def request(self, path: str, *, token: str | None = None, host: str | None = None, method: str = 'GET', body=None,
                cookie: bool = True):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if cookie:
            req.add_header('Cookie', self.cookie)
        if token:
            req.add_header('X-WR-Token', token)
        if host:
            req.add_header('Host', host)
        if data is not None:
            req.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.status, response.read().decode('utf-8'), dict(response.headers)
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode('utf-8'), dict(exc.headers)

    def test_api_requires_token(self) -> None:
        status, body, _ = self.request('/api/params')
        self.assertEqual(status, 401)
        status, body, _ = self.request('/api/params', token='otro')
        self.assertEqual(status, 401)
        # La clave sin la cookie de sesión tampoco sirve.
        status, body, _ = self.request('/api/params', token=self.token, cookie=False)
        self.assertEqual(status, 401)
        status, body, headers = self.request('/api/params', token=self.token)
        self.assertEqual(status, 200)
        self.assertIn('params', json.loads(body))
        self.assertEqual(headers.get('X-Content-Type-Options'), 'nosniff')

    def test_host_header_is_checked(self) -> None:
        status, _, _ = self.request('/api/params', token=self.token, host='evil.example:80')
        self.assertEqual(status, 403)

    def test_nothing_is_served_without_session(self) -> None:
        for path in ('/', '/index.html', '/js/main.js', '/css/app.css', '/docs/', '/docs/index.html', '/no-existe', '/api/status'):
            status, body, _ = self.request(path, cookie=False)
            self.assertEqual(status, 401, path)
            self.assertNotIn('import', body)
            self.assertNotIn('Weapon Rebalancer', body)
        status, body, _ = self.request('/js/main.js')
        self.assertEqual(status, 200)

    def test_access_link_is_single_use(self) -> None:
        used = self.auth.access_token()
        cookie, _key = self.login()
        self.assertTrue(cookie.startswith('wr_session='))
        self.assertNotEqual(self.auth.access_token(), used)
        status, _, _ = self.request(f'/?token={used}', cookie=False)
        self.assertEqual(status, 401)

    def test_static_traversal_blocked(self) -> None:
        for path in ('/../wr.py', '/docs/../../wr.py', '/%2e%2e/wr.py', '/css/../../wr.py'):
            status, _, _ = self.request(path)
            self.assertEqual(status, 404, path)

    def test_unknown_route_and_bad_json(self) -> None:
        status, _, _ = self.request('/api/nada', token=self.token)
        self.assertEqual(status, 404)
        req = urllib.request.Request(self.base + '/api/profiles/validate', data=b'{no json', method='POST')
        req.add_header('X-WR-Token', self.token)
        req.add_header('Cookie', self.cookie)
        req.add_header('Content-Type', 'application/json')
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 400)

    def test_validate_endpoint(self) -> None:
        status, body, _ = self.request('/api/profiles/validate', token=self.token, method='POST',
                                       body={'profile': {'modules': {'damage': 'mal'}}})
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertFalse(result['valid'])


if __name__ == '__main__':
    unittest.main()
