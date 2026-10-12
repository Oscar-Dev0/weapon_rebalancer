"""Recoil vertical de cámara por script: qbx_smallresources/qbx_recoils.

Ese recurso sube la cámara (`SetGameplayCamRelativePitch`) mientras el jugador
dispara, con una cantidad por arma definida en `qbx_recoils/config.lua` como
``[hash] = valor``. Es el único recoil de cámara vertical que existe en esta
instalación: CWeaponInfo no tiene un tag equivalente.

La escritura reemplaza solo las líneas de las armas indicadas y conserva el resto
del archivo (comentarios, orden y entradas desactivadas).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..core.joaat import joaat, signed

_ENTRY_RE = re.compile(r'^(?P<indent>\s*)\[(?P<hash>-?\d+)\]\s*=\s*(?P<value>-?[\d.]+)\s*,?(?P<rest>.*)$')
_COMMENTED_RE = re.compile(r'^\s*--\s*\[(?P<hash>-?\d+)\]\s*=\s*(?P<value>-?[\d.]+)')


@dataclass
class QbxRecoils:
    path: Path
    values: dict[int, float] = field(default_factory=dict)       # hash con signo -> valor activo
    disabled: dict[int, float] = field(default_factory=dict)     # entradas comentadas
    lines: dict[int, int] = field(default_factory=dict)
    error: str | None = None

    def value_for(self, weapon: str) -> float | None:
        return self.values.get(signed(joaat(weapon)))

    def summary(self) -> dict[str, object]:
        return {'path': str(self.path), 'active': len(self.values), 'disabled': len(self.disabled), 'error': self.error}


def find_qbx_recoils(resources: Path) -> Path | None:
    # Profundidad limitada: recorrer todo resources/ (incluido [streaming]) es lento.
    for pattern in ('*/qbx_recoils/config.lua', '*/*/qbx_recoils/config.lua', '*/*/*/qbx_recoils/config.lua'):
        for candidate in sorted(resources.glob(pattern)):
            return candidate
    return None


def load_qbx_recoils(path: Path) -> QbxRecoils:
    data = QbxRecoils(path=path)
    try:
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as exc:
        data.error = str(exc)
        return data
    for number, line in enumerate(text.splitlines(), start=1):
        commented = _COMMENTED_RE.match(line)
        if commented:
            data.disabled[int(commented.group('hash'))] = float(commented.group('value'))
            continue
        match = _ENTRY_RE.match(line)
        if match:
            key = signed(int(match.group('hash')))
            data.values[key] = float(match.group('value'))
            data.lines[key] = number
    return data


def render_qbx_recoils(path: Path, changes: dict[str, float | None]) -> tuple[str, list[str]]:
    """Devuelve el nuevo contenido aplicando `{WEAPON_X: valor | None}` (None = quitar).

    Las entradas existentes se editan en su línea; las nuevas se agregan antes del
    cierre de la tabla con un comentario del nombre del arma.
    """
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()
    notes: list[str] = []
    wanted = {signed(joaat(name)): (name, value) for name, value in changes.items()}
    handled: set[int] = set()
    output: list[str] = []
    for line in lines:
        match = _ENTRY_RE.match(line)
        if match:
            key = signed(int(match.group('hash')))
            if key in wanted:
                name, value = wanted[key]
                handled.add(key)
                if value is None:
                    output.append(f'{match.group("indent")}-- [{key}] = {match.group("value")},{match.group("rest")}')
                    notes.append(f'{name}: entrada desactivada')
                    continue
                output.append(f'{match.group("indent")}[{key}] = {value:g},{match.group("rest")}')
                notes.append(f'{name}: {match.group("value")} → {value:g}')
                continue
        output.append(line)
    pending = [(key, name, value) for key, (name, value) in wanted.items() if key not in handled and value is not None]
    if pending:
        close_index = max(i for i, line in enumerate(output) if line.strip().startswith('}'))
        block = ['    -- weapon_rebalancer']
        for key, name, value in sorted(pending, key=lambda item: item[1]):
            block.append(f"    [{key}] = {value:g},\t\t--['{name.lower()}']")
            notes.append(f'{name}: nuevo {value:g}')
        output[close_index:close_index] = block
    return '\n'.join(output) + ('\n' if text.endswith('\n') else ''), notes
