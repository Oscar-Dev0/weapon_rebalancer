from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .config import Settings
from .fields import FIELDS
from .meta_utils import insert_field_if_missing, read_text, replace_field, write_text
from .profiles import category_defaults
from .tuning import apply_modular_profiles
from .report import FileChange, RebalanceReport
from .scanner import (
    WeaponBlock,
    discover_fxmanifest_data_files,
    discover_meta_paths,
    extract_weapon_blocks,
    find_package_configs,
)


class RebalanceEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self) -> RebalanceReport:
        report = RebalanceReport(
            dry_run=self.settings.dry_run,
            preset=self.settings.active_preset,
            root=str(self.settings.root),
            only_weapons=sorted(self.settings.only_weapons),
        )

        paths = discover_meta_paths(self.settings.root, self.settings.scan, self.settings.skip_basenames)
        package_configs = find_package_configs(self.settings.root, self.settings.scan)
        report.package_configs_found = [str(p.path) for p in package_configs]
        report.fxmanifest_data_files = discover_fxmanifest_data_files(self.settings.root)
        report.files_scanned = len(paths)

        for path in paths:
            changes = self.process_file(path, package_configs)
            for change in changes:
                report.add(change)
            report.weapon_blocks_found += len(changes)

        report.finalize_file_count()

        if self.settings.write_json_report:
            try:
                report.save_json(self.settings.report_path)
            except Exception as exc:  # noqa: BLE001
                report.warnings.append(f'No se pudo guardar reporte JSON: {exc}')

        return report

    def process_file(self, path: Path, package_configs: list[Any]) -> list[FileChange]:
        content = read_text(path)
        blocks = extract_weapon_blocks(path, content, self.settings.scan, package_configs)

        if not blocks:
            return []

        updated_content = content
        # Ajuste por offsets cuando reemplazamos bloques de distinto tamaño.
        offset = 0
        changes: list[FileChange] = []

        for block in blocks:
            live_block = WeaponBlock(
                path=block.path,
                start=block.start + offset,
                end=block.end + offset,
                text=updated_content[block.start + offset:block.end + offset],
                weapon=block.weapon,
                group=block.group,
                config_stack=block.config_stack,
                source=block.source,
            )
            change, new_block_text = self.process_block(live_block)

            # En --only no queremos llenar el print/reporte con cada arma que NO era objetivo.
            # Solo registramos armas objetivo, skips reales o cambios reales.
            if not (self.settings.only_weapons and change.skipped and change.reason == 'not_in_only_weapons'):
                changes.append(change)

            if new_block_text != live_block.text:
                updated_content = updated_content[:live_block.start] + new_block_text + updated_content[live_block.end:]
                offset += len(new_block_text) - len(live_block.text)

        if updated_content != content:
            write_text(path, updated_content, dry_run=self.settings.dry_run, backup=self.settings.create_backup)

        return changes

    def process_block(self, block: WeaponBlock) -> tuple[FileChange, str]:
        weapon = block.weapon.upper()
        group = block.group.upper()
        change = FileChange(
            path=str(block.path),
            weapon=weapon,
            group=group,
            package_configs=[str(c.path) for c in block.config_stack],
            block_source=block.source,
        )

        # Las armas marcadas como inofensivas tienen prioridad absoluta.
        # Se procesan aunque el grupo sea UNKNOWN, estén fuera de --only/--weapontype,
        # aparezcan en ignore_weapons o no exista un perfil base para su grupo.
        # El objetivo es buscar cualquier META que las defina y limpiar daño previo.
        is_harmless = weapon in self.settings.harmless_weapons

        if not is_harmless:
            if self.settings.only_weapons and weapon not in self.settings.only_weapons:
                change.skipped = True
                change.reason = 'not_in_only_weapons'
                return change, block.text

            if self.settings.weapon_types and not self.weapon_matches_types(weapon, group):
                change.skipped = True
                change.reason = 'not_in_weapon_type'
                return change, block.text

            if weapon in self.settings.ignore_weapons:
                change.skipped = True
                change.reason = 'ignored_weapon'
                return change, block.text

            if self.package_ignores_weapon(block, weapon):
                change.skipped = True
                change.reason = 'ignored_by_package_config'
                return change, block.text

        profile = self.build_profile(weapon, group, block)
        if profile is None:
            if is_harmless:
                profile = {}
            else:
                change.skipped = True
                change.reason = f'no_profile_for_group_{group}'
                return change, block.text

        self.settings.current_group = group
        profile = self.apply_weapon_range_multiplier(weapon, group, profile)
        profile = apply_modular_profiles(profile, self.settings)
        if self.settings.headshot_profile != 'original':
            profile = self.apply_headshot_policy(weapon, profile, block)
        profile = self.calculate_falloff_min(group, profile)
        profile = self.apply_harmless_policy(weapon, profile)
        profile = self.clamp_profile(profile, change)

        updated = block.text
        for key, value in profile.items():
            if key not in FIELDS:
                change.missing_fields.append(f'unsupported:{key}')
                continue
            new_content, replaced = replace_field(updated, key, self.format_value(value))
            if replaced:
                if new_content != updated:
                    change.changed_fields.append(key)
                updated = new_content
            else:
                # Muchos packs custom no traen NetworkHeadShotPlayerDamageModifier.
                # Si el usuario habilita headshot completo, lo creamos dentro del bloque
                # para que el daño de cabeza también aplique en red.
                if self.should_create_missing_headshot_tag(key):
                    inserted_content, inserted = insert_field_if_missing(updated, key, self.format_value(value))
                    if inserted:
                        updated = inserted_content
                        change.changed_fields.append(f'{key}:inserted')
                    else:
                        change.missing_fields.append(key)
                else:
                    change.missing_fields.append(key)

        if is_harmless:
            change.reason = 'harmless_weapon_damage_forced_to_zero'

        return change, updated

    def apply_harmless_policy(self, weapon: str, profile: dict[str, Any]) -> dict[str, Any]:
        """Fuerza daño cero en armas recreativas, incluso bajo perfiles letales."""
        if weapon not in self.settings.harmless_weapons:
            return profile

        result = deepcopy(profile)
        result.update({
            'damage': 0.0,
            'hit_limbs': 0.0,
            'network_hit_limbs': 0.0,
            'lightly_armoured': 0.0,
            'vehicle_damage_modifier': 0.0,
            'headshot_player': 0.0,
            'network_headshot': 0.0,
            'headshot_ai': 0.0,
            'min_headshot_player': 0.0,
            'max_headshot_player': 0.0,
            'min_headshot_ai': 0.0,
            'max_headshot_ai': 0.0,
            'falloff_modifier': 0.0,
        })
        return result

    def should_create_missing_headshot_tag(self, key: str) -> bool:
        if key not in {
            'headshot_player',
            'network_headshot',
            'headshot_ai',
            'min_headshot_player',
            'max_headshot_player',
            'min_headshot_ai',
            'max_headshot_ai',
        }:
            return False
        return bool(getattr(self.settings.headshot, 'create_missing_tags', True))


    def build_profile(self, weapon: str, group: str, block: WeaponBlock) -> dict[str, Any] | None:
        external = self.settings.external_group_profiles.get(group)
        base = deepcopy(external) if external is not None else category_defaults(group, self.settings.active_preset)
        explicit = self.settings.explicit_overrides.get(weapon)

        if base is None and explicit is None:
            # intenta overrides por config de carpeta antes de abandonar
            package_profile = self.package_profile(block, weapon, group)
            return package_profile or None

        profile: dict[str, Any] = {}
        if base:
            profile.update(deepcopy(base))
        # configs por carpeta se aplican entre base y overrides globales/per-arma
        package_profile = self.package_profile(block, weapon, group)
        if package_profile:
            profile.update(package_profile)
        if explicit:
            profile.update(deepcopy(explicit))
        return profile

    def weapon_matches_types(self, weapon: str, group: str) -> bool:
        """Comprueba filtros de --weapontype por grupo o familia de nombre."""
        aliases = {
            'PISTOL': 'GROUP_PISTOL',
            'HANDGUN': 'GROUP_PISTOL',
            'SMG': 'GROUP_SMG',
            'RIFLE': 'GROUP_RIFLE',
            'AR': 'GROUP_RIFLE',
            'MG': 'GROUP_MG',
            'SHOTGUN': 'GROUP_SHOTGUN',
            'SNIPER': 'GROUP_SNIPER',
            'MELEE': 'GROUP_MELEE',
        }
        family_aliases = {
            'REVOLVER': ('REVOLVER', 'DOUBLEACTION'),
        }

        weapon = weapon.upper()
        group = group.upper()
        for requested in self.settings.weapon_types:
            key = requested.upper().removeprefix('GROUP_')
            canonical_group = aliases.get(key, f'GROUP_{key}')
            if group == canonical_group:
                return True
            needles = family_aliases.get(key, (key,))
            if any(needle in weapon for needle in needles):
                return True
        return False

    def apply_weapon_range_multiplier(self, weapon: str, group: str, profile: dict[str, Any]) -> dict[str, Any]:
        """Aumenta solo el alcance por arma exacta o familia, conservando el perfil del grupo."""
        multiplier = self.settings.weapon_range_multipliers.get(weapon)

        if multiplier is None:
            matches = [
                value
                for needle, value in self.settings.weapon_family_range_multipliers.items()
                if needle in weapon
            ]
            multiplier = max(matches, default=1.0)

        if multiplier <= 0.0 or multiplier == 1.0:
            return profile

        for key in ('weapon_range', 'falloff_max'):
            value = profile.get(key)
            if isinstance(value, (int, float)):
                profile[key] = float(value) * multiplier

        # Mantiene las distancias de headshot alineadas cuando ya existen en el perfil.
        weapon_range = profile.get('weapon_range')
        if isinstance(weapon_range, (int, float)):
            for key in ('max_headshot_player', 'max_headshot_ai'):
                if key in profile:
                    profile[key] = float(weapon_range)

        return profile

    def package_profile(self, block: WeaponBlock, weapon: str, group: str) -> dict[str, Any]:
        profile: dict[str, Any] = {}
        for pc in block.config_stack:
            data = pc.data
            groups = data.get('groups')
            if isinstance(groups, dict) and isinstance(groups.get(group), dict):
                profile.update(deepcopy(groups[group]))
            weapons = data.get('weapons')
            if isinstance(weapons, dict) and isinstance(weapons.get(weapon), dict):
                profile.update(deepcopy(weapons[weapon]))
            defaults = data.get('defaults')
            if isinstance(defaults, dict):
                profile.update(deepcopy(defaults))
        return profile

    def package_ignores_weapon(self, block: WeaponBlock, weapon: str) -> bool:
        for pc in block.config_stack:
            ignored = pc.data.get('ignore_weapons')
            if isinstance(ignored, list) and weapon in {str(w).upper() for w in ignored}:
                return True
        return False

    def apply_headshot_policy(self, weapon: str, profile: dict[str, Any], block: WeaponBlock | None = None) -> dict[str, Any]:
        """Política final de headshot y one tap.

        Modos:
        - disabled: cabeza sin multiplicador extra.
        - normal: cabeza pega más, pero no fuerza one tap.
        - onetap: cabeza letal tipo vanilla usando multiplicador alto.
        """
        h = self.settings.headshot
        disabled = False
        enabled = bool(h.enabled)
        one_tap = bool(getattr(h, 'one_tap', False))

        one_tap_weapons = {str(w).upper() for w in getattr(h, 'one_tap_weapons', set())}
        no_one_tap_weapons = {str(w).upper() for w in getattr(h, 'no_one_tap_weapons', set())}

        if not h.enabled and weapon not in h.allowed_weapons:
            disabled = True
        if weapon in h.disabled_weapons:
            disabled = True
            enabled = False
            one_tap = False
        if not h.enabled and weapon in h.allowed_weapons:
            disabled = False
            enabled = True

        if weapon in one_tap_weapons:
            enabled = True
            disabled = False
            one_tap = True
        if weapon in no_one_tap_weapons:
            one_tap = False

        # Evita que bates/dagas/hachas queden one tap si activas one tap global.
        if getattr(h, 'disable_one_tap_for_melee', True) and block is not None and block.group.upper() == 'GROUP_MELEE':
            one_tap = False

        # Config local por carpeta: weapon_rebalance.json.
        if block is not None:
            for pc in block.config_stack:
                head = pc.data.get('headshot')
                if not isinstance(head, dict):
                    continue

                local_disabled = {str(w).upper() for w in head.get('disabled_weapons', []) if isinstance(w, str)}
                local_allowed = {str(w).upper() for w in head.get('allowed_weapons', []) if isinstance(w, str)}
                local_one_tap = {str(w).upper() for w in head.get('one_tap_weapons', []) if isinstance(w, str)}
                local_no_one_tap = {str(w).upper() for w in head.get('no_one_tap_weapons', []) if isinstance(w, str)}

                if head.get('enabled') is False:
                    disabled = True
                    enabled = False
                    one_tap = False

                if head.get('enabled') is True:
                    disabled = False
                    enabled = True

                if head.get('one_tap') is True:
                    disabled = False
                    enabled = True
                    one_tap = True

                if head.get('one_tap') is False:
                    one_tap = False

                if weapon in local_disabled:
                    disabled = True
                    enabled = False
                    one_tap = False

                if weapon in local_allowed:
                    disabled = False
                    enabled = True

                if weapon in local_one_tap:
                    disabled = False
                    enabled = True
                    one_tap = True

                if weapon in local_no_one_tap:
                    one_tap = False

        if disabled:
            profile['headshot_player'] = 0.0
            profile['network_headshot'] = 0.0
            profile['min_headshot_player'] = 0.0
            profile['max_headshot_player'] = h.disabled_max_distance
            if h.disable_ai_headshot:
                profile['headshot_ai'] = 0.0
                profile['min_headshot_ai'] = 0.0
                profile['max_headshot_ai'] = h.disabled_max_distance
            return profile

        if enabled and h.force_enabled_values:
            max_distance = h.enabled_default_max_distance
            if max_distance is None:
                try:
                    max_distance = float(profile.get('weapon_range', 100.0))
                except Exception:  # noqa: BLE001
                    max_distance = 100.0

            if one_tap:
                # One tap debe funcionar dentro de TODO el radio configurado.
                # No basta con poner multiplicador alto: si MaxHeadShotDistancePlayer o
                # DamageFallOffRangeMax quedan cortos, a distancia parece que no hace headshot.
                max_distance = self.resolve_one_tap_distance(profile, h)
                player_modifier = h.one_tap_player_modifier
                network_modifier = h.one_tap_network_modifier
                ai_modifier = h.one_tap_ai_modifier

                if getattr(h, 'one_tap_sync_distance_with_weapon_range', True):
                    profile['weapon_range'] = max(float(profile.get('weapon_range', max_distance)), float(max_distance))

                if getattr(h, 'one_tap_force_no_falloff', True):
                    # Para one tap a distancia NO queremos que el daño vaya bajando antes del rango.
                    # En GTA/FiveM la caída empieza en DamageFallOffRangeMin y termina en Max.
                    # Por eso se deja el inicio casi al final del rango y el modifier en 1.0.
                    profile['falloff_min'] = max(0.0, float(max_distance) - 0.001)
                    profile['falloff_max'] = max_distance
                    profile['falloff_modifier'] = 1.0

                if getattr(h, 'one_tap_sync_lock_on_range', False):
                    profile['lock_on_range'] = max_distance
            else:
                player_modifier = h.enabled_player_modifier
                network_modifier = h.enabled_network_modifier
                ai_modifier = h.enabled_ai_modifier

            profile['headshot_player'] = player_modifier
            profile['network_headshot'] = network_modifier
            profile['headshot_ai'] = ai_modifier
            profile['min_headshot_player'] = 0.0
            profile['max_headshot_player'] = max_distance
            profile['min_headshot_ai'] = 0.0
            profile['max_headshot_ai'] = max_distance

        return profile

    @staticmethod
    def resolve_one_tap_distance(profile: dict[str, Any], headshot_config: Any) -> float:
        configured = getattr(headshot_config, 'one_tap_default_distance', None)
        if configured is not None:
            try:
                return float(configured)
            except Exception:  # noqa: BLE001
                pass

        # Prioridad: weapon_range. Si no existe, usa falloff_max. Último fallback: 100.
        for key in ('weapon_range', 'falloff_max', 'max_headshot_player'):
            try:
                value = float(profile.get(key, 0.0))
            except Exception:  # noqa: BLE001
                value = 0.0
            if value > 0.0:
                return value
        return 100.0

    def calculate_falloff_min(self, group: str, profile: dict[str, Any]) -> dict[str, Any]:
        if 'falloff_min' in profile or 'falloff_max' not in profile:
            return profile
        ratios = {
            'GROUP_PISTOL': 0.45,
            'GROUP_SMG': 0.42,
            'GROUP_RIFLE': 0.52,
            'GROUP_MG': 0.48,
            'GROUP_SHOTGUN': 0.30,
            'GROUP_SNIPER': 0.65,
            'GROUP_MELEE': 0.0,
        }
        ratio = ratios.get(group, 0.45)
        try:
            profile['falloff_min'] = round(float(profile['falloff_max']) * ratio, 3)
        except Exception:  # noqa: BLE001
            pass
        return profile

    def clamp_profile(self, profile: dict[str, Any], change: FileChange) -> dict[str, Any]:
        for key, bounds in self.settings.safe_bounds.items():
            if key not in profile:
                continue
            value = profile[key]
            if isinstance(value, str):
                continue
            try:
                number = float(value)
            except Exception:  # noqa: BLE001
                continue
            low, high = bounds
            clamped = min(max(number, low), high)
            if clamped != number:
                change.clamped_fields[key] = (number, clamped)
                profile[key] = clamped
        return profile

    @staticmethod
    def format_value(value: Any) -> str:
        if isinstance(value, float):
            return f'{value:.6f}'
        return str(value)
