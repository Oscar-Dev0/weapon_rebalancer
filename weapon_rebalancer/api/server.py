"""Servidor web local del panel (solo librería estándar).

Seguridad:
- Escucha en 127.0.0.1 por defecto.
- Acceso con token de un solo uso que rota solo (ver api/auth.py). Sin sesión válida no se
  entrega nada: ni la página, ni JS, CSS o documentación.
- Sesión en cookie HttpOnly con caducidad; las llamadas /api exigen además la clave de la
  sesión en X-WR-Token (un sitio externo no puede enviarla: protege contra CSRF). Ambas rotan.
- Intentos fallidos repetidos bloquean nuevas entradas desde esa IP.
- Se valida la cabecera Host (evita ataques de DNS rebinding).
- Solo se sirven archivos de web/ y docs/.
"""
from __future__ import annotations

import json
import mimetypes
import re
import signal
import time
import traceback
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from ..catalog.params import registry_payload
from ..core.errors import AppError, NotFound, ValidationFailed
from ..core.jsonlog import log, tail
from ..core.paths import DOCS_DIR, WEB_DIR, data_dir, is_within, validate_profile_id
from .auth import AuthManager, AuthSettings, Session
from ..core.workspace import _defaults, update_workspace, validate_workspace
from ..services.app import App

MAX_BODY = 5 * 1024 * 1024
Route = tuple[str, re.Pattern[str], Callable[..., Any]]


class Api:
    def __init__(self, app: App) -> None:
        self.app = app
        self.routes: list[Route] = []
        r = self.add
        r('GET', r'/api/status', lambda q, b: app.status())
        r('GET', r'/api/workspace', lambda q, b: {'workspace': app.workspace().to_dict(), 'errors': validate_workspace(app.workspace())})
        r('PUT', r'/api/workspace', self.put_workspace)
        r('GET', r'/api/workspace/detect', lambda q, b: {'detected': _defaults().to_dict()})
        r('GET', r'/api/params', lambda q, b: registry_payload())
        r('GET', r'/api/catalog', self.get_catalog)
        r('GET', r'/api/catalog/weapons/(?P<name>[A-Za-z0-9_\-]+)', self.get_weapon)
        r('GET', r'/api/profiles', lambda q, b: {'profiles': app.repo.list(include_legacy=q.get('all') == '1'),
                                                 'active': app.workspace().active_profile, 'index_errors': app.repo.index_errors()})
        r('POST', r'/api/profiles/ops', lambda q, b: app.apply_ops(b))
        r('POST', r'/api/profiles/explain', lambda q, b: app.explain(str(b.get('weapon', '')), b, keys=b.get('keys')))
        r('POST', r'/api/weapons/rows', lambda q, b: app.weapon_rows(b))
        r('POST', r'/api/profiles', self.create_profile)
        r('POST', r'/api/profiles/validate', lambda q, b: app.validate_profile(self.require_obj(b, 'profile')))
        r('POST', r'/api/profiles/compare', lambda q, b: app.compare(self.require_obj(b, 'a'), self.require_obj(b, 'b'),
                                                                      weapons=b.get('weapons'), keys=b.get('keys')))
        r('POST', r'/api/profiles/import', self.import_profile)
        r('POST', r'/api/profiles/migrate-all', self.migrate_all)
        r('GET', r'/api/profiles/(?P<pid>[a-z0-9_\-]+)', self.get_profile)
        r('PUT', r'/api/profiles/(?P<pid>[a-z0-9_\-]+)', self.put_profile)
        r('DELETE', r'/api/profiles/(?P<pid>[a-z0-9_\-]+)', lambda q, b, pid: app.repo.delete(pid))
        r('POST', r'/api/profiles/(?P<pid>[a-z0-9_\-]+)/duplicate', self.duplicate_profile)
        r('POST', r'/api/profiles/(?P<pid>[a-z0-9_\-]+)/rename', self.rename_profile)
        r('POST', r'/api/profiles/(?P<pid>[a-z0-9_\-]+)/derive', lambda q, b, pid: app.repo.derive(pid, validate_profile_id(str(b.get('new_id', ''))), b.get('name')))
        r('GET', r'/api/profiles/(?P<pid>[a-z0-9_\-]+)/affected', lambda q, b, pid: {'weapons': app.affected({'profile_id': pid})})
        r('POST', r'/api/profiles/(?P<pid>[a-z0-9_\-]+)/activate', self.activate_profile)
        r('GET', r'/api/profiles/(?P<pid>[a-z0-9_\-]+)/history', lambda q, b, pid: {'history': app.repo.history(pid)})
        r('GET', r'/api/profiles/(?P<pid>[a-z0-9_\-]+)/history/(?P<file>[A-Za-z0-9_.\-]+)',
          lambda q, b, pid, file: {'profile': app.repo.revision_content(pid, file)})
        r('POST', r'/api/profiles/(?P<pid>[a-z0-9_\-]+)/restore', lambda q, b, pid: app.repo.restore(pid, str(b.get('file', ''))))
        r('GET', r'/api/profiles/(?P<pid>[a-z0-9_\-]+)/export', self.export_profile)
        r('POST', r'/api/profiles/(?P<pid>[a-z0-9_\-]+)/migrate', lambda q, b, pid: app.repo.migrate_file(pid, dry_run=bool(b.get('dry_run'))))
        r('POST', r'/api/profiles/(?P<pid>[a-z0-9_\-]+)/revert-migration', lambda q, b, pid: app.repo.revert_migration(pid))
        r('POST', r'/api/preview', self.post_preview)
        r('POST', r'/api/simulate', lambda q, b: app.simulate(b))
        r('GET', r'/api/diagnostics', lambda q, b: app.diagnostics(refresh_runtime=q.get('refresh_runtime') == '1',
                                                                  include_runtime=q.get('runtime', '1') == '1'))
        r('POST', r'/api/generator/plan', lambda q, b: app.plan(b))
        r('GET', r'/api/generator/plan/(?P<plan>[0-9a-f]{64})/diff', lambda q, b, plan: app.plan_diff(plan, q.get('path', '')))
        r('POST', r'/api/generator/apply', lambda q, b: app.apply(b))
        r('GET', r'/api/generator/transactions', lambda q, b: {'transactions': app.transactions()})
        r('POST', r'/api/generator/rollback', lambda q, b: app.rollback(b))
        r('POST', r'/api/generator/guard', lambda q, b: app.guard(b))
        r('GET', r'/api/logs', lambda q, b: {'entries': tail(q.get('stream', 'changes') if q.get('stream') in {'app', 'changes'} else 'changes', 200)})

    def add(self, method: str, pattern: str, handler: Callable[..., Any]) -> None:
        self.routes.append((method, re.compile(f'^{pattern}$'), handler))

    def dispatch(self, method: str, path: str, query: dict[str, str], body: Any) -> Any:
        allowed = False
        for route_method, pattern, handler in self.routes:
            match = pattern.match(path)
            if not match:
                continue
            allowed = True
            if route_method != method:
                continue
            return handler(query, body, **match.groupdict())
        if allowed:
            raise AppError('Método no permitido para esta ruta.')
        raise NotFound(f'Ruta de API desconocida: {path}')

    @staticmethod
    def require_obj(body: Any, key: str) -> dict[str, Any]:
        value = body.get(key) if isinstance(body, dict) else None
        if not isinstance(value, dict):
            raise ValidationFailed(f'Falta el objeto “{key}”.')
        return value

    # ---- handlers ---------------------------------------------------------------
    def put_workspace(self, query: dict[str, str], body: Any) -> Any:
        if not isinstance(body, dict):
            raise ValidationFailed('Cuerpo inválido.')
        ws = update_workspace(body)
        self.app.catalog.invalidate()
        log('workspace.update', fields=sorted(body))
        return {'workspace': ws.to_dict(), 'errors': []}

    def get_catalog(self, query: dict[str, str], body: Any) -> Any:
        catalog = self.app.catalog.get(force=query.get('refresh') == '1')
        rows = []
        for weapon in catalog.weapons.values():
            rows.append({k: weapon[k] for k in (
                'name', 'label', 'hash', 'group', 'category', 'custom', 'internal', 'in_ox', 'in_meta',
                'definition_count', 'resources', 'current', 'original', 'rpm', 'rpm_original',
                'modified_fields', 'severity', 'qbx_recoil', 'has_backup')} | {'issue_count': len(weapon['issues'])})
        return {'summary': catalog.summary(), 'weapons': rows, 'global_issues': catalog.global_issues}

    def get_weapon(self, query: dict[str, str], body: Any, name: str) -> Any:
        detail = self.app.catalog.weapon_detail(name)
        if detail is None:
            raise NotFound(f'No existe {name} en el catálogo.')
        return detail

    def get_profile(self, query: dict[str, str], body: Any, pid: str) -> Any:
        _raw, sha = self.app.repo.read_raw(pid)
        profile = self.app.repo.load(pid)
        resolved = self.app.resolved(profile)
        summary = self.app.repo.summary(pid)
        return {
            'id': pid, 'sha': sha, 'profile': profile, 'resolved': resolved, 'base': self.app.base_resolved(profile), 'summary': summary,
            'tier': summary['tier'], 'editable': summary['editable'], 'children': self.app.repo.children(pid),
            'validation': self.app.validate_profile(profile), 'legacy': summary['legacy'],
        }

    def put_profile(self, query: dict[str, str], body: Any, pid: str) -> Any:
        profile = self.require_obj(body, 'profile')
        return self.app.save_profile(pid, profile, sha=body.get('sha'), note=str(body.get('note', '')),
                                     allow_invalid=bool(body.get('allow_invalid')))

    def create_profile(self, query: dict[str, str], body: Any) -> Any:
        pid = validate_profile_id(str(body.get('id', '')))
        name = str(body.get('name') or pid)[:120]
        return self.app.repo.create(pid, name, str(body.get('description', ''))[:2000],
                                    extends=body.get('extends') or None, source=body.get('source') or None)

    def duplicate_profile(self, query: dict[str, str], body: Any, pid: str) -> Any:
        return self.app.repo.duplicate(pid, validate_profile_id(str(body.get('new_id', ''))), body.get('name'))

    def rename_profile(self, query: dict[str, str], body: Any, pid: str) -> Any:
        new_id = validate_profile_id(str(body.get('new_id') or pid))
        result = self.app.repo.rename(pid, new_id, body.get('name'))
        if self.app.workspace().active_profile == pid and new_id != pid:
            update_workspace({'active_profile': new_id})
        return result

    def activate_profile(self, query: dict[str, str], body: Any, pid: str) -> Any:
        return self.app.activate(pid)

    def export_profile(self, query: dict[str, str], body: Any, pid: str) -> Any:
        return {'profile': self.app.repo.export(pid, resolved=query.get('resolved') == '1', legacy=query.get('legacy') == '1')}

    def import_profile(self, query: dict[str, str], body: Any) -> Any:
        pid = validate_profile_id(str(body.get('id', '')))
        content = body.get('content')
        if not isinstance(content, str) or len(content) > 2 * 1024 * 1024:
            raise ValidationFailed('Contenido inválido o demasiado grande (máx. 2 MB).')
        return self.app.repo.import_profile(pid, content, overwrite=bool(body.get('overwrite')))

    def migrate_all(self, query: dict[str, str], body: Any) -> Any:
        dry = bool(body.get('dry_run', True)) if isinstance(body, dict) else True
        return {'results': [self.app.repo.migrate_file(pid, dry_run=dry) for pid in self.app.repo.ids()], 'dry_run': dry}

    def post_preview(self, query: dict[str, str], body: Any) -> Any:
        profile_id, profile = self.app.profile_input(body if isinstance(body, dict) else {})
        data = self.app.preview_profile(profile, profile_id)
        only = body.get('weapons') if isinstance(body, dict) else None
        if isinstance(only, list) and only:
            wanted = {str(w).upper() for w in only}
            data = {**data, 'weapons': {k: v for k, v in data['weapons'].items() if k in wanted}}
        return data


class Handler(BaseHTTPRequestHandler):
    server_version = 'WeaponRebalancer'
    sys_version = ''
    api: Api
    auth: AuthManager
    allowed_hosts: set[str]

    def log_message(self, fmt: str, *args: Any) -> None:  # silencia el log por request en consola
        return

    # ---- utilidades ---------------------------------------------------------------
    def _headers(self, status: int, content_type: str, length: int, extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(length))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy',
                         "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                         "connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def _json(self, status: int, payload: Any, extra: dict[str, str] | None = None) -> None:
        data = json.dumps(payload, ensure_ascii=False, default=str).encode('utf-8')
        self._headers(status, 'application/json; charset=utf-8', len(data), extra)
        self.wfile.write(data)

    def _text(self, status: int, text: str, content_type: str = 'text/plain; charset=utf-8', extra: dict[str, str] | None = None) -> None:
        data = text.encode('utf-8')
        self._headers(status, content_type, len(data), extra)
        self.wfile.write(data)

    def _host_ok(self) -> bool:
        return (self.headers.get('Host') or '').lower() in self.allowed_hosts

    def _cookie_session(self) -> str | None:
        raw = self.headers.get('Cookie')
        if not raw:
            return None
        cookie = SimpleCookie()
        try:
            cookie.load(raw)
        except Exception:  # noqa: BLE001
            return None
        morsel = cookie.get('wr_session')
        return morsel.value if morsel else None

    def _session_cookie(self, session: Session | None) -> dict[str, str]:
        if session is None:
            return {'Set-Cookie': 'wr_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'}
        max_age = int(self.auth.settings.max_hours * 3600)
        return {'Set-Cookie': f'wr_session={session.sid}; HttpOnly; SameSite=Strict; Path=/; Max-Age={max_age}'}

    def _deny(self, ip: str, api: bool) -> None:
        """Sin sesión no se entrega nada: misma respuesta para cualquier ruta (exista o no)."""
        locked = self.auth.locked(ip)
        status = HTTPStatus.FORBIDDEN if locked else HTTPStatus.UNAUTHORIZED
        message = (f'Acceso bloqueado temporalmente por intentos fallidos ({int(locked // 60) + 1} min).' if locked
                   else 'Acceso denegado.')
        if api:
            self._json(status, {'error': 'locked' if locked else 'unauthorized', 'message': message})
            return
        self._text(status, '<!doctype html><meta charset="utf-8"><title>Acceso denegado</title>'
                           '<body style="background:#0b0d17;color:#e7e9f6;font-family:system-ui;padding:40px">'
                           f'<p>{message}</p></body>', 'text/html; charset=utf-8')

    def _login(self, token: str, ip: str, current: Session | None) -> None:
        if current is None:
            current = self.auth.login(token, ip)
            if current is None:
                self._deny(ip, api=False)
                return
        # Redirige sin el token en la URL (no queda en el historial del navegador).
        self._text(HTTPStatus.SEE_OTHER, '', extra={'Location': '/', **self._session_cookie(current)})

    # ---- métodos HTTP ---------------------------------------------------------------
    def do_GET(self) -> None:
        self._handle('GET')

    def do_POST(self) -> None:
        self._handle('POST')

    def do_PUT(self) -> None:
        self._handle('PUT')

    def do_DELETE(self) -> None:
        self._handle('DELETE')

    def _handle(self, method: str) -> None:
        if not self._host_ok():
            self._text(HTTPStatus.FORBIDDEN, 'Host no permitido.')
            return
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        ip = self.client_address[0]
        session = self.auth.session(self._cookie_session(), ip)
        if method == 'GET' and path in {'/', '/index.html'} and 'token' in query:
            self._login(query['token'], ip, session)
            return
        if session is None:
            self._deny(ip, api=path.startswith('/api/'))
            return
        if path.startswith('/api/'):
            self._handle_api(method, path, query, session, ip)
            return
        if method != 'GET':
            self._text(HTTPStatus.METHOD_NOT_ALLOWED, 'Método no permitido.')
            return
        if path in {'/', '/index.html'}:
            self._serve_index(session)
            return
        self.auth.touch(session, rotate=False)
        if path.startswith('/docs'):
            relative = path[len('/docs'):].lstrip('/') or 'index.html'
            self._serve_file(DOCS_DIR, relative)
            return
        self._serve_file(WEB_DIR, path.lstrip('/'))

    def _handle_api(self, method: str, path: str, query: dict[str, str], session: Session, ip: str) -> None:
        if not self.auth.check_key(session, self.headers.get('X-WR-Token', ''), ip):
            self._json(HTTPStatus.UNAUTHORIZED, {'error': 'unauthorized', 'message': 'Acceso denegado.'})
            return
        extra: dict[str, str] = {}
        new_key = self.auth.touch(session)
        if new_key:
            extra = {'X-WR-Token-Next': new_key, **self._session_cookie(session)}
        if path == '/api/session' and method == 'GET':
            self._json(HTTPStatus.OK, self.auth.info(session), extra)
            return
        if path == '/api/session/logout' and method == 'POST':
            self.auth.logout(session)
            self._json(HTTPStatus.OK, {'ok': True}, self._session_cookie(None))
            return
        body: Any = {}
        if method in {'POST', 'PUT', 'DELETE'}:
            length = int(self.headers.get('Content-Length') or 0)
            if length > MAX_BODY:
                self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {'error': 'too_large', 'message': 'La petición supera 5 MB.'})
                return
            if length:
                if 'application/json' not in (self.headers.get('Content-Type') or ''):
                    self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {'error': 'json', 'message': 'Se esperaba JSON.'})
                    return
                try:
                    body = json.loads(self.rfile.read(length).decode('utf-8'))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._json(HTTPStatus.BAD_REQUEST, {'error': 'json', 'message': 'JSON inválido.'})
                    return
        started = time.perf_counter()
        try:
            result = self.api.dispatch(method, path, query, body if isinstance(body, dict) else {})
            self._json(HTTPStatus.OK, result, extra)
        except AppError as exc:
            self._json(exc.status, exc.to_dict(), extra)
        except Exception as exc:  # noqa: BLE001
            log('api.error', level='error', path=path, method=method, error=str(exc), trace=traceback.format_exc()[-2000:])
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {'error': 'internal', 'message': f'Error interno: {exc}'}, extra)
        finally:
            elapsed = int((time.perf_counter() - started) * 1000)
            if elapsed > 1500:
                log('api.slow', path=path, method=method, ms=elapsed)

    def _serve_index(self, session: Session) -> None:
        extra = self._session_cookie(session) if self.auth.touch(session) else {}
        html = (WEB_DIR / 'index.html').read_text(encoding='utf-8').replace('__WR_TOKEN__', session.key)
        self._text(HTTPStatus.OK, html, 'text/html; charset=utf-8', extra)

    def _serve_file(self, root: Path, relative: str) -> None:
        target = (root / relative)
        if not is_within(target, root) or not target.is_file():
            self._text(HTTPStatus.NOT_FOUND, 'No encontrado.')
            return
        content_type = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
        if content_type.startswith('text/') or content_type in {'application/javascript', 'application/json'}:
            content_type += '; charset=utf-8'
        data = target.read_bytes()
        self._headers(HTTPStatus.OK, content_type, len(data))
        self.wfile.write(data)


TOKEN_FILE = 'panel_access_{port}.json'  # uno por puerto: varios paneles no se pisan


def serve(host: str = '127.0.0.1', port: int = 8765, *, open_hint: bool = True, settings: AuthSettings | None = None) -> None:
    mimetypes.add_type('application/javascript', '.js')
    mimetypes.add_type('text/markdown', '.md')
    app = App()
    allowed = {f'{h}:{port}' for h in ('127.0.0.1', 'localhost', '[::1]')}
    if host not in {'127.0.0.1', 'localhost', '::1'}:
        allowed.add(f'{host}:{port}')
    base_url = f'http://{"127.0.0.1" if host in {"0.0.0.0", "::"} else host}:{port}'
    auth = AuthManager(settings, base_url=base_url, token_file=data_dir() / TOKEN_FILE.format(port=port),
                       on_rotate=lambda reason: print(f'  Nuevo enlace ({reason}): {auth.access_url}', flush=True))
    handler = type('WRHandler', (Handler,), {'api': Api(app), 'auth': auth, 'allowed_hosts': allowed})
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.daemon_threads = True
    s = auth.settings
    log('server.start', host=host, port=port)
    print('Weapon Rebalancer — panel web', flush=True)
    print(f'  URL:   {auth.access_url}', flush=True)
    print(f'  El enlace sirve una sola vez y cambia cada {s.rotate_minutes:g} min. Enlace vigente: python3 wr.py token', flush=True)
    print(f'  La sesión caduca tras {s.idle_minutes:g} min sin uso o {s.max_hours:g} h; '
          f'{s.max_failures} intentos fallidos bloquean {s.lockout_minutes:g} min.', flush=True)
    if host not in {'127.0.0.1', 'localhost', '::1'}:
        print('  AVISO: escuchando fuera de localhost. Cualquiera con el enlace puede usar el panel.')
    print('  Ctrl+C para detener.', flush=True)
    auth.start_rotation_thread()

    def _terminate(*_args: Any) -> None:
        raise KeyboardInterrupt

    try:
        signal.signal(signal.SIGTERM, _terminate)  # `kill` también borra el enlace guardado
    except ValueError:  # fuera del hilo principal (pruebas)
        pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nDetenido.')
    finally:
        auth.stop()
        httpd.server_close()
