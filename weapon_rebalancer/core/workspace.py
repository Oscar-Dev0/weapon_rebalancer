from __future__ import annotations

import os
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .errors import ValidationFailed
from .fsutil import atomic_write_json, read_json
from .paths import DATA_DIR, PROJECT_ROOT, is_within

WORKSPACE_FILE = DATA_DIR / 'workspace.json'
WORKSPACE_SCHEMA = 1
_LOCK = threading.Lock()


@dataclass
class ServerOptions:
    host: str = '127.0.0.1'
    port: int = 8765
    # Acceso al panel (api/auth.py). Se leen al arrancar `wr.py serve`.
    token_rotate_minutes: float = 30.0
    session_idle_minutes: float = 30.0
    session_max_hours: float = 8.0
    session_key_rotate_minutes: float = 10.0
    max_failures: int = 8
    lockout_minutes: float = 10.0


# Límites de los ajustes de acceso: (mínimo, máximo).
SERVER_LIMITS: dict[str, tuple[float, float]] = {
    'token_rotate_minutes': (1, 1440), 'session_idle_minutes': (1, 720), 'session_max_hours': (0.1, 72),
    'session_key_rotate_minutes': (1, 120), 'max_failures': (3, 100), 'lockout_minutes': (1, 1440),
}


@dataclass
class Workspace:
    """Rutas y preferencias del programa. Se guarda en data/workspace.json."""

    schema: int = WORKSPACE_SCHEMA
    server_root: str = ''
    pack_roots: list[str] = field(default_factory=list)
    ox_inventory_dir: str = ''
    runtime_audit_root: str = ''
    reference_roots: list[str] = field(default_factory=list)
    active_profile: str = 'flow_custom'
    # Permite editar perfiles del nivel “server” (flow_custom). Siempre con respaldo en el historial.
    server_profiles_editable: bool = True
    guard_destination: str = ''
    qbx_recoils_file: str = ''
    # Servidores a los que se pasan las armas con `wr.py sync <nombre>` (nombre -> carpeta del servidor).
    sync_targets: dict[str, str] = field(default_factory=dict)
    server: ServerOptions = field(default_factory=ServerOptions)

    # ---- rutas resueltas -------------------------------------------------
    @property
    def server_path(self) -> Path:
        return Path(self.server_root)

    @property
    def resources_path(self) -> Path:
        return self.server_path / 'resources'

    @property
    def pack_paths(self) -> list[Path]:
        return [Path(p) for p in self.pack_roots]

    @property
    def ox_path(self) -> Path | None:
        return Path(self.ox_inventory_dir) if self.ox_inventory_dir else None

    @property
    def qbx_recoils_path(self) -> Path | None:
        return Path(self.qbx_recoils_file) if self.qbx_recoils_file else None

    @property
    def runtime_path(self) -> Path:
        return Path(self.runtime_audit_root) if self.runtime_audit_root else self.resources_path

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_server_root(start: Path = PROJECT_ROOT) -> Path | None:
    """Sube desde el proyecto hasta encontrar una carpeta con resources/."""
    current = start.resolve()
    for _ in range(6):
        if (current / 'resources').is_dir():
            return current
        if current.parent == current:
            break
        current = current.parent
    return None


def detect_ox_inventory(resources: Path) -> Path | None:
    """Busca ox_inventory con data/weapons.lua dentro de resources (máx. 3 niveles)."""
    if not resources.is_dir():
        return None
    candidates: list[Path] = []
    for depth_glob in ('ox_inventory', '*/ox_inventory', '*/*/ox_inventory'):
        for candidate in resources.glob(depth_glob):
            if (candidate / 'data' / 'weapons.lua').is_file():
                candidates.append(candidate)
    return sorted(candidates, key=lambda p: len(p.parts))[0] if candidates else None


def detect_pack_roots(resources: Path) -> list[Path]:
    """Carpeta(s) de packs de armas: [PackArmas] o similares con weapons.meta."""
    if not resources.is_dir():
        return []
    named = [p for p in resources.glob('*/*') if p.is_dir() and 'packarmas' in p.name.lower()]
    named += [p for p in resources.glob('*') if p.is_dir() and 'packarmas' in p.name.lower()]
    return sorted(set(named))


def _defaults() -> Workspace:
    ws = Workspace()
    server = detect_server_root()
    if server is not None:
        ws.server_root = str(server)
        resources = server / 'resources'
        ws.pack_roots = [str(p) for p in detect_pack_roots(resources)]
        ox = detect_ox_inventory(resources)
        ws.ox_inventory_dir = str(ox) if ox else ''
        from ..adapters.qbx_recoils import find_qbx_recoils

        recoils = find_qbx_recoils(resources)
        ws.qbx_recoils_file = str(recoils) if recoils else ''
    return ws


def _from_dict(data: dict[str, Any]) -> Workspace:
    ws = _defaults()
    for key in ('server_root', 'ox_inventory_dir', 'runtime_audit_root', 'active_profile', 'guard_destination', 'qbx_recoils_file'):
        if isinstance(data.get(key), str):
            setattr(ws, key, data[key])
    for key in ('pack_roots', 'reference_roots'):
        if isinstance(data.get(key), list):
            setattr(ws, key, [str(v) for v in data[key] if str(v).strip()])
    if isinstance(data.get('sync_targets'), dict):
        ws.sync_targets = {str(k): str(v) for k, v in data['sync_targets'].items()
                           if str(k).strip() and str(v).strip()}
    if isinstance(data.get('server_profiles_editable'), bool):
        ws.server_profiles_editable = data['server_profiles_editable']
    server = data.get('server')
    if isinstance(server, dict):
        ws.server = ServerOptions(
            host=str(server.get('host', ws.server.host)),
            port=int(server.get('port', ws.server.port)),
        )
        for key, (low, high) in SERVER_LIMITS.items():
            value = server.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                kind = int if key == 'max_failures' else float
                setattr(ws.server, key, kind(min(max(value, low), high)))
    return ws


def load_workspace() -> Workspace:
    env_root = os.environ.get('WR_SERVER_ROOT')
    data = read_json(WORKSPACE_FILE, default=None)
    ws = _from_dict(data) if isinstance(data, dict) else _defaults()
    if env_root:
        ws.server_root = env_root
    return ws


def validate_workspace(ws: Workspace) -> list[str]:
    """Devuelve errores bloqueantes. Las rutas deben existir y quedar dentro del servidor."""
    errors: list[str] = []
    server = ws.server_path
    if not ws.server_root or not server.is_dir():
        errors.append(f'La carpeta del servidor no existe: {ws.server_root or "(vacía)"}')
        return errors
    if not (server / 'resources').is_dir():
        errors.append(f'{server} no contiene una carpeta resources/.')
    if not ws.pack_roots:
        errors.append('Configura al menos una carpeta de pack de armas.')
    for root in ws.pack_paths:
        if not root.is_dir():
            errors.append(f'El pack no existe: {root}')
        elif not is_within(root, server):
            errors.append(f'El pack debe estar dentro del servidor: {root}')
    if ws.ox_inventory_dir:
        ox = Path(ws.ox_inventory_dir)
        if not (ox / 'data' / 'weapons.lua').is_file():
            errors.append(f'No se encontró data/weapons.lua en {ox}')
        elif not is_within(ox, server):
            errors.append(f'ox_inventory debe estar dentro del servidor: {ox}')
    if ws.qbx_recoils_file:
        qbx = Path(ws.qbx_recoils_file)
        if not qbx.is_file():
            errors.append(f'No existe el config de qbx_recoils: {qbx}')
        elif not is_within(qbx, server):
            errors.append(f'qbx_recoils debe estar dentro del servidor: {qbx}')
    if ws.runtime_audit_root and not Path(ws.runtime_audit_root).is_dir():
        errors.append(f'La carpeta de auditoría runtime no existe: {ws.runtime_audit_root}')
    for root in ws.reference_roots:
        if not Path(root).is_dir():
            errors.append(f'La carpeta de referencia no existe: {root}')
    for name, target in ws.sync_targets.items():
        if not (Path(target) / 'resources').is_dir():
            errors.append(f'El servidor destino “{name}” no tiene carpeta resources/: {target}')
        elif Path(target).resolve() == server.resolve():
            errors.append(f'El servidor destino “{name}” es el mismo servidor de la herramienta.')
    if ws.guard_destination and not is_within(Path(ws.guard_destination), ws.resources_path):
        errors.append('El destino del guard debe estar dentro de resources/.')
    if not (1024 <= ws.server.port <= 65535):
        errors.append('El puerto debe estar entre 1024 y 65535.')
    return errors


def save_workspace(ws: Workspace) -> Workspace:
    errors = validate_workspace(ws)
    if errors:
        raise ValidationFailed('La configuración no es válida.', details=errors)
    from .filelock import file_lock

    with _LOCK, file_lock('workspace'):
        atomic_write_json(WORKSPACE_FILE, ws.to_dict())
    return ws


def update_workspace(changes: dict[str, Any]) -> Workspace:
    current = load_workspace().to_dict()
    for key, value in changes.items():
        if key in current and key != 'schema':
            current[key] = value
    return save_workspace(_from_dict(current))
