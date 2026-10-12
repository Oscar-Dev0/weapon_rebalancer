"""Lectura de armas, componentes y munición desde ox_inventory (solo lectura).

ox_inventory es la fuente de identificación: nombre WEAPON_*, etiqueta, munición y
componentes. No define daño ni cadencia; esos valores salen de los weapons.meta.
El hash que usa ox_inventory es ``joaat(model or name)``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.joaat import joaat, signed, unsigned
from .lua_table import LuaExpr, LuaParseError, LuaTable, parse_lua_return_table


@dataclass
class OxWeapon:
    name: str
    label: str
    line: int
    model: str
    hash: int
    weight: Any = None
    durability: Any = None
    ammoname: str | None = None
    throwable: bool = False
    rarity: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'label': self.label,
            'line': self.line,
            'model': self.model,
            'hash': self.hash,
            'hash_signed': signed(self.hash),
            'weight': self.weight,
            'durability': self.durability,
            'ammoname': self.ammoname,
            'throwable': self.throwable,
            'rarity': self.rarity,
        }


@dataclass
class OxComponent:
    name: str
    label: str
    type: str | None
    hashes: list[int]
    line: int


@dataclass
class OxInventoryData:
    path: Path
    weapons: dict[str, OxWeapon] = field(default_factory=dict)
    components: dict[str, OxComponent] = field(default_factory=dict)
    ammo: dict[str, str] = field(default_factory=dict)
    duplicates: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            'path': str(self.path),
            'weapons': len(self.weapons),
            'components': len(self.components),
            'ammo': len(self.ammo),
            'duplicates': len(self.duplicates),
            'errors': self.errors,
        }


def _number(value: Any) -> Any:
    if isinstance(value, LuaExpr):
        return value.raw
    return value


def _component_hashes(entry: LuaTable) -> list[int]:
    client = entry.get('client')
    if not isinstance(client, LuaTable):
        return []
    component = client.get('component')
    values: list[Any] = []
    if isinstance(component, LuaTable):
        values = list(component.array)
    elif component is not None:
        values = [component]
    hashes: list[int] = []
    for value in values:
        if isinstance(value, int):
            hashes.append(unsigned(value))
        elif isinstance(value, str):
            hashes.append(joaat(value))
        elif isinstance(value, LuaExpr):
            raw = value.raw.strip()
            # `joaat('COMPONENT_X')` / `` `COMPONENT_X` ``
            for quote in ('"', "'", '`'):
                if raw.count(quote) >= 2:
                    hashes.append(joaat(raw.split(quote)[1]))
                    break
    return hashes


def load_ox_inventory(ox_dir: Path) -> OxInventoryData:
    path = Path(ox_dir) / 'data' / 'weapons.lua'
    data = OxInventoryData(path=path)
    if not path.is_file():
        data.errors.append(f'No existe {path}')
        return data
    text = path.read_text(encoding='utf-8', errors='replace')
    try:
        root = parse_lua_return_table(text)
    except LuaParseError as exc:
        data.errors.append(f'No se pudo leer weapons.lua: {exc}')
        return data

    for section in ('Weapons', 'Components', 'Ammo'):
        table = root.get(section)
        if not isinstance(table, LuaTable):
            if section == 'Weapons':
                data.errors.append('weapons.lua no tiene la sección Weapons.')
            continue
        for key, first_line, second_line in table.duplicates:
            data.duplicates.append({
                'section': section, 'name': str(key), 'first_line': first_line, 'last_line': second_line,
            })

    weapons = root.get('Weapons')
    if isinstance(weapons, LuaTable):
        for raw_name, entry in weapons.items.items():
            if not isinstance(entry, LuaTable):
                continue
            name = str(raw_name).upper()
            model = str(entry.get('model') or name)
            extra = {
                str(k): _number(v) for k, v in entry.items.items()
                if k not in {'label', 'weight', 'durability', 'ammoname', 'throwable', 'rarity', 'model', 'anim', 'client', 'server'}
                and not isinstance(v, LuaTable)
            }
            data.weapons[name] = OxWeapon(
                name=name,
                label=str(entry.get('label') or name),
                line=weapons.lines.get(raw_name, 0),
                model=model,
                hash=joaat(model),
                weight=_number(entry.get('weight')),
                durability=_number(entry.get('durability')),
                ammoname=str(entry.get('ammoname')) if entry.get('ammoname') is not None else None,
                throwable=bool(entry.get('throwable') is True),
                rarity=str(entry.get('rarity')) if entry.get('rarity') is not None else None,
                extra=extra,
            )

    components = root.get('Components')
    if isinstance(components, LuaTable):
        for raw_name, entry in components.items.items():
            if not isinstance(entry, LuaTable):
                continue
            data.components[str(raw_name)] = OxComponent(
                name=str(raw_name),
                label=str(entry.get('label') or raw_name),
                type=str(entry.get('type')) if entry.get('type') is not None else None,
                hashes=_component_hashes(entry),
                line=components.lines.get(raw_name, 0),
            )

    ammo = root.get('Ammo')
    if isinstance(ammo, LuaTable):
        for raw_name, entry in ammo.items.items():
            label = entry.get('label') if isinstance(entry, LuaTable) else None
            data.ammo[str(raw_name)] = str(label or raw_name)
    return data
