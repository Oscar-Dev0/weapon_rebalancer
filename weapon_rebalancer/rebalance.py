from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .config import Settings
from .baseline import apply_baseline_repair, build_reference_index
from .component_audit import scan_component_damage_modifiers, scan_projectile_weapons
from .fields import FIELDS
from .headshot import apply_policy as apply_headshot_profile, audit_block as audit_headshot_block, resolve_headshot_policy
from .meta_utils import (
    insert_field_if_missing,
    read_field_value,
    read_text,
    replace_dynamic_field,
    replace_field,
    update_weapon_flags,
    write_text,
)
from .profiles import category_defaults
from .pack_audit import build_pack_audit
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
        self._active_headshot_policy: dict[str, Any] = {}
        self._restore_warnings: set[str] = set()
        self._reference_values: dict[str, dict[str, float]] = {}

    def run(self) -> RebalanceReport:
        report = RebalanceReport(
            dry_run=self.settings.dry_run,
            preset=self.settings.active_preset,
            root=str(self.settings.root),
            only_weapons=sorted(self.settings.only_weapons),
        )

        paths = discover_meta_paths(self.settings.root, self.settings.scan, self.settings.skip_basenames)
        reference_roots = [Path(v) for v in self.settings.baseline_repair.get('reference_roots', [])]
        self._reference_values = build_reference_index(reference_roots, self.settings.scan)
        report.reference_weapons_loaded = len(self._reference_values)
        if reference_roots and not self._reference_values:
            report.warnings.append('No se cargó ninguna arma desde --reference-root; revisa que la ruta contenga weapons.meta válidos.')
        package_configs = find_package_configs(self.settings.root, self.settings.scan)
        report.package_configs_found = [str(p.path) for p in package_configs]
        report.fxmanifest_data_files = discover_fxmanifest_data_files(self.settings.root)
        report.files_scanned = len(paths)
        report.component_damage_modifiers = scan_component_damage_modifiers(self.settings.root)
        report.projectile_weapons = scan_projectile_weapons(self.settings.root, self.settings.scan, self.settings.skip_basenames)
        if report.component_damage_modifiers:
            report.warnings.append(
                f'{len(report.component_damage_modifiers)} archivos de componentes contienen modificadores de daño distintos de 1.0; revisa el reporte porque pueden alterar el resultado final.'
            )
        if report.projectile_weapons:
            report.warnings.append(
                f'{len(report.projectile_weapons)} armas usan FireType=PROJECTILE; su resultado puede depender de AmmoInfo/explosión y no solo de CWeaponInfo.Damage.'
            )

        pack_audit = build_pack_audit(paths, self.settings.scan, package_configs, self.settings.root)
        if self.settings.validation_options.get('warn_duplicates', True):
            report.duplicate_weapons = pack_audit['duplicate_weapons']
        if self.settings.validation_options.get('warn_unregistered_meta', True):
            report.unregistered_meta_files = pack_audit['unregistered_meta_files']
        if report.duplicate_weapons:
            report.warnings.append(
                f'{len(report.duplicate_weapons)} armas tienen múltiples definiciones; la última cargada puede sobrescribir el one-tap.'
            )
        if report.unregistered_meta_files:
            report.warnings.append(
                f'{len(report.unregistered_meta_files)} META no tienen un WEAPONINFO_FILE visible en su manifest más cercano.'
            )

        for path in paths:
            changes = self.process_file(path, package_configs)
            for change in changes:
                report.add(change)
            report.weapon_blocks_found += len(changes)

        report.finalize_file_count()
        report.warnings.extend(sorted(self._restore_warnings))

        if report.onetap_audit_total:
            report.warnings.append(
                'La auditoría META no puede comprobar SetPedSuffersCriticalHits(false), cancelación de weaponDamageEvent '
                'ni restauración de vida/armadura. Ejecuta --audit-runtime sobre toda la carpeta resources.'
            )

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

        backup_blocks_by_weapon: dict[str, list[WeaponBlock]] = {}
        if self.settings.restore_from_backup:
            backup_path = Path(str(path) + self.settings.restore_backup_suffix)
            if backup_path.exists():
                backup_content = read_text(backup_path)
                for backup_block in extract_weapon_blocks(backup_path, backup_content, self.settings.scan, package_configs):
                    backup_blocks_by_weapon.setdefault(backup_block.weapon.upper(), []).append(backup_block)
            else:
                self._restore_warnings.add(
                    f'Restauración: no existe {backup_path}; {path} usa su contenido actual como base.'
                )

        updated_content = content
        # Ajuste por offsets cuando reemplazamos bloques de distinto tamaño.
        offset = 0
        changes: list[FileChange] = []

        for block in blocks:
            current_start = block.start + offset
            current_end = block.end + offset
            current_text = updated_content[current_start:current_end]
            processing_text = current_text
            processing_weapon = block.weapon
            processing_group = block.group
            processing_source = block.source
            restored_from_backup = False

            candidates = backup_blocks_by_weapon.get(block.weapon.upper(), [])
            if candidates:
                backup_block = candidates.pop(0)
                processing_text = backup_block.text
                processing_weapon = backup_block.weapon
                processing_group = backup_block.group
                processing_source = f'{block.source}+backup_restore'
                restored_from_backup = processing_text != current_text
            elif self.settings.restore_from_backup and backup_blocks_by_weapon:
                self._restore_warnings.add(
                    f'Restauración: {block.weapon.upper()} no aparece en el backup de {path}; usa su bloque actual.'
                )

            processing_block = WeaponBlock(
                path=block.path,
                start=current_start,
                end=current_end,
                text=processing_text,
                weapon=processing_weapon,
                group=processing_group,
                config_stack=block.config_stack,
                source=processing_source,
            )
            change, new_block_text = self.process_block(processing_block)
            if change.skipped:
                # Los filtros --only/--weapontype/--ignore y configs locales siguen siendo soberanos.
                # Restaurar desde backup no debe tocar un bloque que el usuario pidió omitir.
                new_block_text = current_text
                restored_from_backup = False
            elif restored_from_backup:
                change.changed_fields.insert(0, 'restored_from_backup')

            # En --only no queremos llenar el print/reporte con cada arma que NO era objetivo.
            # Solo registramos armas objetivo, skips reales o cambios reales.
            if not (self.settings.only_weapons and change.skipped and change.reason == 'not_in_only_weapons'):
                changes.append(change)

            if new_block_text != current_text:
                updated_content = updated_content[:current_start] + new_block_text + updated_content[current_end:]
                offset += len(new_block_text) - len(current_text)

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

        baseline_config = deepcopy(self.settings.baseline_repair)
        if weapon in self._reference_values:
            official_values = dict(baseline_config.get('official_values', {}))
            official_values[weapon] = self._reference_values[weapon]
            baseline_config['official_values'] = official_values

        baseline = apply_baseline_repair(
            weapon=weapon,
            group=group,
            block=block,
            profile=profile,
            is_official=weapon in self.settings.official_weapons,
            is_custom=self.is_custom_weapon(weapon, group),
            config=baseline_config,
        )
        profile = baseline.profile
        change.changed_fields.extend(baseline.notes)

        profile = self.apply_custom_weapon_multipliers(weapon, group, block, profile)
        profile = self.apply_family_rules(weapon, group, block, profile)
        policy = resolve_headshot_policy(self.settings, weapon, group, block)
        self._active_headshot_policy = policy
        policy_metrics: dict[str, Any] = {}
        if self.settings.headshot_profile != 'original':
            profile, policy_metrics = apply_headshot_profile(
                profile,
                block.text,
                policy,
                disable_ai_headshot=self.settings.headshot.disable_ai_headshot,
                disabled_max_distance=self.settings.headshot.disabled_max_distance,
            )
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
                if self.should_create_missing_policy_tag(key):
                    inserted_content, inserted = insert_field_if_missing(updated, key, self.format_value(value))
                    if inserted:
                        updated = inserted_content
                        change.changed_fields.append(f'{key}:inserted')
                    else:
                        change.missing_fields.append(key)
                else:
                    change.missing_fields.append(key)

        # Overrides XML exactos: permiten modificar cualquier hoja escalar del META,
        # incluso tags custom que todavía no estén en el catálogo de FIELDS.
        for tag, spec in self.collect_meta_overrides(weapon, group, block).items():
            new_content, changed, found, error = replace_dynamic_field(updated, str(tag), spec)
            if error:
                change.missing_fields.append(f'meta_error:{error}')
                continue
            if changed:
                updated = new_content
                change.changed_fields.append(f'meta:{tag}')
            elif not found:
                change.missing_fields.append(f'meta:{tag}')

        one_tap_active = (not is_harmless) and policy.get('mode') == 'onetap' and self.settings.headshot_profile != 'original'
        flag_ops = self.collect_flag_ops(weapon, group, block, policy=policy, one_tap_active=one_tap_active)
        if flag_ops.get('add') or flag_ops.get('remove'):
            new_content, changed, found = update_weapon_flags(
                updated,
                add=flag_ops.get('add', []),
                remove=flag_ops.get('remove', []),
                create_if_missing=bool(flag_ops.get('create_if_missing', False)),
            )
            if changed:
                updated = new_content
                change.changed_fields.append('weapon_flags')
            elif not found:
                change.missing_fields.append('weapon_flags')

        if one_tap_active:
            audit = audit_headshot_block(updated, policy, expected=True)
            change.onetap_expected = True
            change.onetap_ready = bool(audit['ready'])
            change.onetap_issues = list(audit['issues'])
            change.onetap_metrics = {**policy_metrics, **dict(audit['metrics'])}
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
            'penetration': 0.0,
        })
        return result

    def should_create_missing_policy_tag(self, key: str) -> bool:
        """Decide qué campos calculados se pueden insertar en metas custom incompletos."""
        policy = self._active_headshot_policy or {}
        if key in {
            'headshot_player',
            'network_headshot',
            'headshot_ai',
            'min_headshot_player',
            'max_headshot_player',
            'min_headshot_ai',
            'max_headshot_ai',
        }:
            return bool(policy.get('create_missing_tags', getattr(self.settings.headshot, 'create_missing_tags', True)))

        if key == 'lightly_armoured':
            return bool(policy.get('create_missing_armour_tag', getattr(self.settings.headshot, 'create_missing_lightly_armoured_tag', True)))

        if key == 'penetration':
            return bool(policy.get('create_missing_penetration_tag', getattr(self.settings.headshot, 'create_missing_penetration_tag', True)))

        if key == 'network_player_damage_modifier':
            return bool(policy.get(
                'create_missing_network_player_modifier_tag',
                getattr(self.settings.headshot, 'create_missing_network_player_modifier_tag', True),
            ))

        if self.settings.baseline_repair.get('enabled', False) and key in {
            'damage',
            'network_player_damage_modifier',
            'network_ped_damage_modifier',
            'hit_limbs',
            'network_hit_limbs',
            'lightly_armoured',
            'weapon_range',
            'falloff_min',
            'falloff_max',
            'falloff_modifier',
            'headshot_player',
            'network_headshot',
            'headshot_ai',
            'min_headshot_player',
            'max_headshot_player',
            'min_headshot_ai',
            'max_headshot_ai',
        }:
            return True

        if key == 'damage':
            return bool(policy.get('mode') == 'onetap' and policy.get('auto_minimum_base_damage', True))

        return False



    def build_profile(self, weapon: str, group: str, block: WeaponBlock) -> dict[str, Any] | None:
        global_external = self.settings.external_group_profiles.get('__GLOBAL__', {})
        external = self.settings.external_group_profiles.get(group)
        base = deepcopy(external) if external is not None else category_defaults(group, self.settings.active_preset)
        explicit = self.settings.explicit_overrides.get(weapon)

        if base is None and explicit is None and not global_external:
            package_profile = self.package_profile(block, weapon, group)
            if package_profile:
                return package_profile
            if self.has_extended_overrides(weapon, group, block):
                return {}
            return None

        profile: dict[str, Any] = {}
        if global_external:
            profile.update(deepcopy(global_external))
        if base:
            profile.update(deepcopy(base))
        # configs por carpeta se aplican entre base y overrides globales/per-arma
        package_profile = self.package_profile(block, weapon, group)
        if package_profile:
            profile.update(package_profile)
        if explicit:
            profile.update(deepcopy(explicit))
        return profile

    def has_extended_overrides(self, weapon: str, group: str, block: WeaponBlock) -> bool:
        if self.settings.restore_from_backup:
            return True
        if self.is_custom_weapon(weapon, group):
            return True
        if any(self.family_rule_matches(rule, weapon, group) for rule in self.settings.family_rules):
            return True
        if self.settings.global_meta_overrides or self.settings.global_flag_ops.get('add') or self.settings.global_flag_ops.get('remove'):
            return True
        if group in self.settings.group_meta_overrides or group in self.settings.group_flag_ops:
            return True
        if weapon in self.settings.weapon_meta_overrides or weapon in self.settings.weapon_flag_ops:
            return True
        if group in self.settings.group_headshot_overrides or weapon in self.settings.weapon_headshot_overrides:
            return True
        for pc in block.config_stack:
            if isinstance(pc.data.get('meta'), dict) or isinstance(pc.data.get('weapon_flags'), dict):
                return True
        return False

    def is_custom_weapon(self, weapon: str, group: str) -> bool:
        if not self.settings.classify_custom_weapons:
            return False
        if weapon.upper() in self.settings.official_weapons:
            return False
        allowed_groups = self.settings.custom_weapon_groups
        return not allowed_groups or group.upper() in allowed_groups

    def family_rule_matches(self, rule: dict[str, Any], weapon: str, group: str) -> bool:
        groups = rule.get('groups', set())
        if groups and group.upper() not in groups:
            return False
        if not any(needle in weapon.upper() for needle in rule.get('contains', [])):
            return False
        is_custom = self.is_custom_weapon(weapon, group)
        is_official = weapon.upper() in self.settings.official_weapons
        if rule.get('custom_only') and not is_custom:
            return False
        if rule.get('official_only') and not is_official:
            return False
        return True

    @staticmethod
    def _numeric_field_base(block: WeaponBlock, profile: dict[str, Any], key: str) -> float | None:
        value = profile.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            value = read_field_value(block.text, key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return None

    def apply_custom_weapon_multipliers(
        self,
        weapon: str,
        group: str,
        block: WeaponBlock,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.is_custom_weapon(weapon, group):
            return profile

        multipliers = dict(self.settings.custom_field_multipliers)
        multipliers.update(self.settings.custom_group_field_multipliers.get(group, {}))
        if not multipliers:
            return profile

        result = deepcopy(profile)
        for key, multiplier in multipliers.items():
            base = self._numeric_field_base(block, result, key)
            if base is not None:
                result[key] = base * float(multiplier)
        return result

    def apply_family_rules(
        self,
        weapon: str,
        group: str,
        block: WeaponBlock,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        result = deepcopy(profile)
        for rule in self.settings.family_rules:
            if not self.family_rule_matches(rule, weapon, group):
                continue
            for key, multiplier in rule.get('field_multipliers', {}).items():
                base = self._numeric_field_base(block, result, key)
                if base is not None:
                    result[key] = base * float(multiplier)
            result.update(deepcopy(rule.get('fields', {})))
        return result

    def collect_meta_overrides(self, weapon: str, group: str, block: WeaponBlock) -> dict[str, Any]:
        result: dict[str, Any] = {}
        result.update(deepcopy(self.settings.global_meta_overrides))
        result.update(deepcopy(self.settings.group_meta_overrides.get(group, {})))
        result.update(deepcopy(self.settings.weapon_meta_overrides.get(weapon, {})))
        for pc in block.config_stack:
            global_meta = pc.data.get('meta')
            if isinstance(global_meta, dict):
                result.update(deepcopy(global_meta))
            groups = pc.data.get('groups')
            if isinstance(groups, dict) and isinstance(groups.get(group), dict):
                local = groups[group].get('meta')
                if isinstance(local, dict):
                    result.update(deepcopy(local))
            weapons = pc.data.get('weapons')
            if isinstance(weapons, dict) and isinstance(weapons.get(weapon), dict):
                local = weapons[weapon].get('meta')
                if isinstance(local, dict):
                    result.update(deepcopy(local))
        return result

    @staticmethod
    def merge_flag_ops(*ops: dict[str, Any]) -> dict[str, Any]:
        add: list[str] = []
        remove: list[str] = []
        create = False
        for op in ops:
            if not isinstance(op, dict):
                continue
            add.extend(str(v) for v in op.get('add', []) if str(v).strip())
            remove.extend(str(v) for v in op.get('remove', []) if str(v).strip())
            create = create or bool(op.get('create_if_missing', False))
        return {
            'add': list(dict.fromkeys(add)),
            'remove': list(dict.fromkeys(remove)),
            'create_if_missing': create,
        }

    def collect_flag_ops(
        self,
        weapon: str,
        group: str,
        block: WeaponBlock,
        *,
        policy: dict[str, Any],
        one_tap_active: bool,
    ) -> dict[str, Any]:
        ops = [
            self.settings.global_flag_ops,
            self.settings.group_flag_ops.get(group, {}),
            self.settings.weapon_flag_ops.get(weapon, {}),
        ]
        for pc in block.config_stack:
            ops.append(pc.data.get('weapon_flags', {}))
            groups = pc.data.get('groups')
            if isinstance(groups, dict) and isinstance(groups.get(group), dict):
                ops.append(groups[group].get('weapon_flags', {}))
            weapons = pc.data.get('weapons')
            if isinstance(weapons, dict) and isinstance(weapons.get(weapon), dict):
                ops.append(weapons[weapon].get('weapon_flags', {}))

        merged = self.merge_flag_ops(*ops)
        if one_tap_active and policy.get('bypass_helmets', True):
            if policy.get('add_ignore_helmets_flag', True):
                merged['add'].append('IgnoreHelmets')
            if policy.get('add_armour_penetrating_flag', True):
                merged['add'].append('ArmourPenetrating')
            if policy.get('remove_nonlethal_flags', True) and group != 'GROUP_MELEE':
                merged['remove'].extend(str(v) for v in policy.get('blocking_flags', ('NonLethal', 'NonViolent')))
            merged['add'] = list(dict.fromkeys(merged['add']))
            merged['remove'] = list(dict.fromkeys(merged['remove']))
            merged['create_if_missing'] = bool(
                merged['create_if_missing'] or policy.get('create_missing_weapon_flags_tag', True)
            )
        return merged

    def is_one_tap_active_for_weapon(self, weapon: str, group: str, block: WeaponBlock) -> bool:
        if self.settings.headshot_profile == 'original':
            return False
        return resolve_headshot_policy(self.settings, weapon, group, block).get('mode') == 'onetap'

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
                values = groups[group].get('fields', groups[group])
                if isinstance(values, dict):
                    profile.update({k: deepcopy(v) for k, v in values.items() if k not in {'meta', 'weapon_flags', 'fields', 'headshot'}})
            weapons = data.get('weapons')
            if isinstance(weapons, dict) and isinstance(weapons.get(weapon), dict):
                values = weapons[weapon].get('fields', weapons[weapon])
                if isinstance(values, dict):
                    profile.update({k: deepcopy(v) for k, v in values.items() if k not in {'meta', 'weapon_flags', 'fields', 'headshot'}})
            defaults = data.get('defaults')
            if isinstance(defaults, dict):
                values = defaults.get('fields', defaults)
                if isinstance(values, dict):
                    profile.update({k: deepcopy(v) for k, v in values.items() if k not in {'meta', 'weapon_flags', 'fields', 'headshot'}})
        return profile

    def package_ignores_weapon(self, block: WeaponBlock, weapon: str) -> bool:
        for pc in block.config_stack:
            ignored = pc.data.get('ignore_weapons')
            if isinstance(ignored, list) and weapon in {str(w).upper() for w in ignored}:
                return True
        return False

    def apply_headshot_policy(self, weapon: str, profile: dict[str, Any], block: WeaponBlock | None = None) -> dict[str, Any]:
        """Compatibilidad pública: delega en el motor de política V3."""
        if block is None:
            return profile
        policy = resolve_headshot_policy(self.settings, weapon, block.group, block)
        result, _ = apply_headshot_profile(
            profile,
            block.text,
            policy,
            disable_ai_headshot=self.settings.headshot.disable_ai_headshot,
            disabled_max_distance=self.settings.headshot.disabled_max_distance,
        )
        return result

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
