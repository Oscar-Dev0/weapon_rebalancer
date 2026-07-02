from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class FileChange:
    path: str
    weapon: str
    group: str
    changed_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    clamped_fields: dict[str, tuple[float, float]] = field(default_factory=dict)
    package_configs: list[str] = field(default_factory=list)
    block_source: str = 'CWeaponInfo'
    skipped: bool = False
    reason: str | None = None
    onetap_expected: bool = False
    onetap_ready: bool | None = None
    onetap_issues: list[str] = field(default_factory=list)
    onetap_metrics: dict[str, object] = field(default_factory=dict)


@dataclass
class RebalanceReport:
    dry_run: bool
    preset: str
    root: str
    files_scanned: int = 0
    weapon_blocks_found: int = 0
    files_changed: int = 0
    weapons_changed: int = 0
    files_skipped: int = 0
    package_configs_found: list[str] = field(default_factory=list)
    fxmanifest_data_files: dict[str, list[str]] = field(default_factory=dict)
    changes: list[FileChange] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    only_weapons: list[str] = field(default_factory=list)
    only_found: dict[str, str] = field(default_factory=dict)
    duplicate_weapons: dict[str, list[str]] = field(default_factory=dict)
    unregistered_meta_files: list[str] = field(default_factory=list)
    component_damage_modifiers: dict[str, list[str]] = field(default_factory=dict)
    reference_weapons_loaded: int = 0
    projectile_weapons: dict[str, str] = field(default_factory=dict)
    onetap_audit_total: int = 0
    onetap_audit_passed: int = 0
    onetap_audit_failed: int = 0

    def add(self, change: FileChange) -> None:
        self.changes.append(change)
        if change.skipped:
            self.files_skipped += 1
        elif change.changed_fields:
            self.weapons_changed += 1
        if change.onetap_expected:
            self.onetap_audit_total += 1
            if change.onetap_ready:
                self.onetap_audit_passed += 1
            else:
                self.onetap_audit_failed += 1

    def finalize_file_count(self) -> None:
        changed_paths = {c.path for c in self.changes if c.changed_fields and not c.skipped}
        self.files_changed = len(changed_paths)

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding='utf-8')

    def print_summary(self) -> None:
        if self.only_weapons:
            self.print_only_summary()
            return

        mode = 'DRY-RUN' if self.dry_run else 'WRITE'
        print(f'[{mode}] preset={self.preset}')
        print(f'ROOT: {self.root}')
        print(f'Archivos .meta escaneados: {self.files_scanned}')
        print(f'Bloques/armas encontrados: {self.weapon_blocks_found}')
        print(f'Archivos cambiados: {self.files_changed}')
        print(f'Armas/bloques cambiados: {self.weapons_changed}')
        print(f'Armas/bloques omitidos: {self.files_skipped}')
        if self.package_configs_found:
            print('\nConfigs por carpeta detectados:')
            for p in self.package_configs_found[:20]:
                print(f'  + {p}')
        if self.fxmanifest_data_files:
            print('\nfxmanifest/__resource con data_file detectados:')
            for manifest, entries in list(self.fxmanifest_data_files.items())[:20]:
                print(f'  # {manifest}')
                for entry in entries[:12]:
                    print(f'    - {entry}')
        if self.duplicate_weapons:
            print(f'\nDefiniciones duplicadas: {len(self.duplicate_weapons)}')
            for weapon, sources in list(self.duplicate_weapons.items())[:20]:
                print(f'  ! {weapon}: {" | ".join(sources)}')
        if self.unregistered_meta_files:
            print(f'\nMETA sin registro visible en manifest: {len(self.unregistered_meta_files)}')
            for path in self.unregistered_meta_files[:20]:
                print(f'  ! {path}')
        if self.reference_weapons_loaded:
            print(f'\nArmas cargadas desde paquete de referencia: {self.reference_weapons_loaded}')
        if self.projectile_weapons:
            print(f'\nArmas PROJECTILE (revisar AmmoInfo/explosión): {len(self.projectile_weapons)}')
            for weapon, detail in list(self.projectile_weapons.items())[:20]:
                print(f'  ! {weapon}: {detail}')
        if self.component_damage_modifiers:
            print(f'\nComponentes con modificadores de daño: {len(self.component_damage_modifiers)}')
            for path, entries in list(self.component_damage_modifiers.items())[:20]:
                print(f'  ! {path}: {", ".join(entries)}')
        if self.onetap_audit_total:
            print(f'\nAuditoría one-tap: ok={self.onetap_audit_passed} | fallos={self.onetap_audit_failed} | total={self.onetap_audit_total}')
        if self.warnings:
            print('\nWarnings:')
            for w in self.warnings[:40]:
                print(f'  ! {w}')
        print('\nCambios:')
        for c in self.changes[:120]:
            cfg = f' cfg={len(c.package_configs)}' if c.package_configs else ''
            if c.skipped:
                print(f'  - SKIP {c.weapon} [{c.group}] ({c.reason}){cfg} {c.path}')
            elif c.changed_fields:
                audit = ''
                if c.onetap_expected:
                    audit = ' [ONETAP OK]' if c.onetap_ready else f' [ONETAP FAIL: {",".join(c.onetap_issues)}]'
                print(f'  * {c.weapon} [{c.group}] {c.block_source}{cfg}{audit} -> {", ".join(c.changed_fields)}')


    def print_only_summary(self) -> None:
        mode = 'DRY-RUN' if self.dry_run else 'WRITE'
        print(f'[{mode}] ONLY MODE')
        print(f'ROOT: {self.root}')

        changed_by_weapon: dict[str, list[FileChange]] = {}
        processed_by_weapon: dict[str, list[FileChange]] = {}
        skipped_by_weapon: dict[str, list[FileChange]] = {}

        for change in self.changes:
            weapon = change.weapon.upper()
            processed_by_weapon.setdefault(weapon, []).append(change)
            if change.skipped:
                skipped_by_weapon.setdefault(weapon, []).append(change)
            elif change.changed_fields:
                changed_by_weapon.setdefault(weapon, []).append(change)

        success_count = 0
        missing_count = 0
        unchanged_count = 0
        skipped_count = 0

        for weapon in self.only_weapons:
            weapon = weapon.upper()
            changed = changed_by_weapon.get(weapon, [])
            processed = [c for c in processed_by_weapon.get(weapon, []) if not c.skipped]
            skipped = skipped_by_weapon.get(weapon, [])

            if changed:
                fields = sorted({field for c in changed for field in c.changed_fields})
                print(f'[OK] {weapon}: procesada correctamente | archivos={len({c.path for c in changed})} | campos={", ".join(fields)}')
                success_count += 1
            elif processed:
                print(f'[OK] {weapon}: encontrada, pero no necesitaba cambios')
                unchanged_count += 1
            elif skipped:
                reason = skipped[0].reason or 'skip'
                print(f'[SKIP] {weapon}: encontrada, pero omitida | reason={reason}')
                skipped_count += 1
            else:
                print(f'[NO ENCONTRADA] {weapon}: no apareció en ningún .meta escaneado')
                missing_count += 1

        print(f'Resultado: ok={success_count} | sin_cambios={unchanged_count} | skip={skipped_count} | no_encontradas={missing_count}')
        if self.warnings:
            print(f'Warnings: {len(self.warnings)}. Revisa el JSON si necesitas detalle.')
