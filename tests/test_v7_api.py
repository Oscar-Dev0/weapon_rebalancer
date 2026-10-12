from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from weapon_rebalancer.api.server import Api, Handler
from weapon_rebalancer.services.app import App


class ApiSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.token = 'token-de-prueba'
        handler = type('H', (Handler,), {'api': Api(App()), 'token': cls.token, 'allowed_hosts': set()})
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        port = cls.httpd.server_address[1]
        handler.allowed_hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        cls.base = f'http://127.0.0.1:{port}'
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def request(self, path: str, *, token: str | None = None, host: str | None = None, method: str = 'GET', body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
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
        status, body, headers = self.request('/api/params', token=self.token)
        self.assertEqual(status, 200)
        self.assertIn('params', json.loads(body))
        self.assertEqual(headers.get('X-Content-Type-Options'), 'nosniff')

    def test_host_header_is_checked(self) -> None:
        status, _, _ = self.request('/api/params', token=self.token, host='evil.example:80')
        self.assertEqual(status, 403)

    def test_index_needs_session(self) -> None:
        status, _, _ = self.request('/')
        self.assertEqual(status, 401)
        status, body, headers = self.request(f'/?token={self.token}')
        self.assertEqual(status, 200)
        self.assertIn(self.token, body)
        self.assertIn('HttpOnly', headers.get('Set-Cookie', ''))

    def test_static_traversal_blocked(self) -> None:
        for path in ('/../wr.py', '/docs/../../wr.py', '/%2e%2e/wr.py', '/css/../../wr.py'):
            status, _, _ = self.request(path)
            self.assertEqual(status, 404, path)

    def test_unknown_route_and_bad_json(self) -> None:
        status, _, _ = self.request('/api/nada', token=self.token)
        self.assertEqual(status, 404)
        req = urllib.request.Request(self.base + '/api/profiles/validate', data=b'{no json', method='POST')
        req.add_header('X-WR-Token', self.token)
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
