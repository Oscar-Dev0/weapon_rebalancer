from __future__ import annotations

import re
from pathlib import Path

from .errors import Forbidden, ValidationFailed

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / 'weapon_rebalancer'
PROFILES_DIR = PROJECT_ROOT / 'profiles'
DATA_DIR = PROJECT_ROOT / 'data'
WEB_DIR = PROJECT_ROOT / 'web'
DOCS_DIR = PROJECT_ROOT / 'docs'
EXTRAS_DIR = PROJECT_ROOT / 'extras'

PROFILE_ID_RE = re.compile(r'^[a-z0-9][a-z0-9_\-]{0,63}$')


def data_dir(*parts: str) -> Path:
    path = DATA_DIR.joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_profile_id(profile_id: str) -> str:
    value = str(profile_id or '').strip()
    if not PROFILE_ID_RE.match(value):
        raise ValidationFailed(
            f'Identificador de perfil inválido: {value!r}.',
            hint='Usa minúsculas, números, guion o guion bajo (máx. 64). Ejemplo: pvp_competitivo',
        )
    return value


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


class PathGuard:
    """Autoriza escrituras solo dentro de raíces explícitas.

    Se resuelven enlaces simbólicos antes de comparar, de modo que `..` o un symlink
    no permiten escapar del destino autorizado.
    """

    def __init__(self, roots: list[Path], label: str) -> None:
        self.roots = [Path(root).resolve() for root in roots]
        self.label = label

    def check(self, path: Path) -> Path:
        resolved = Path(path).resolve()
        for root in self.roots:
            try:
                resolved.relative_to(root)
                return resolved
            except ValueError:
                continue
        raise Forbidden(
            f'Ruta fuera de los destinos autorizados ({self.label}): {resolved}',
            hint='Revisa Configuración → Rutas. Solo se escribe dentro del pack de armas configurado y de data/.',
        )
