#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from weapon_rebalancer.config import Settings
from weapon_rebalancer.fields import print_supported_fields
from weapon_rebalancer.inventory import export_full_profile, export_meta_inventory
from weapon_rebalancer.weapon_flags import print_weapon_flags
from weapon_rebalancer.rebalance import RebalanceEngine
from weapon_rebalancer.profile_loader import ProfileError, apply_external_profile, load_profile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Rebalanceador deep-scan de weapon metas para FiveM/GTA V RP.'
    )
    parser.add_argument('--root', type=Path, default=None, help='Ruta del pack de armas.')
    parser.add_argument('--write', action='store_true', help='Escribe cambios reales. Sin esto corre en dry-run.')
    parser.add_argument('--preset', default=None, help='Preset interno base.')
    parser.add_argument('--profile', type=Path, default=None, help='Perfil JSON externo. Permite configurar todo sin editar Python.')
    parser.add_argument('--recoil', choices=('original', 'none', 'low', 'normal', 'high'), default=None, help='Perfil independiente de recoil.')
    parser.add_argument('--accuracy', choices=('original', 'laser', 'high', 'normal', 'low'), default=None, help='Perfil independiente de precisión/dispersión.')
    parser.add_argument('--damage', choices=('original', 'none', 'head_only', 'low', 'normal', 'high', 'lethal'), default=None, help='Perfil de daño. none=0 total; head_only=daño corporal mínimo para permitir headshot por META.')
    parser.add_argument('--armour', choices=('original', 'none', 'normal', 'piercing', 'max'), default=None, help='Modificador independiente contra armadura ligera/cascos nativos.')
    parser.add_argument('--range-profile', choices=('original', 'short', 'normal', 'long', 'very_long'), default=None, help='Perfil independiente de alcance.')
    parser.add_argument('--fire-rate', choices=('original', 'slow', 'normal', 'fast', 'very_fast'), default=None, help='Perfil independiente de cadencia.')
    parser.add_argument('--reload', choices=('original', 'slow', 'normal', 'fast', 'very_fast'), default=None, help='Perfil independiente de recarga.')
    parser.add_argument('--headshot-profile', choices=('original', 'off', 'normal', 'onetap'), default=None, help='Perfil independiente de headshot.')
    parser.add_argument('--only', nargs='*', default=None, help='Procesar solo estas armas: WEAPON_PISTOL ...')
    parser.add_argument('--weapontype', nargs='+', default=None, help='Filtrar por tipo o familia: revolver, pistol, smg, rifle, shotgun, sniper, mg, melee.')
    parser.add_argument('--ignore', nargs='*', default=None, help='Ignorar estas armas.')
    parser.add_argument('--list-fields', action='store_true', help='Lista campos CWeaponInfo modificables y sale.')
    parser.add_argument('--list-flags', action='store_true', help='Lista WeaponFlags conocidas y sale.')
    parser.add_argument('--export-meta', type=Path, default=None, help='Exporta inventario JSON de TODOS los .meta y sus hojas XML.')
    parser.add_argument('--export-full-profile', type=Path, default=None, help='Genera un perfil JSON completo desde todos los CWeaponInfo encontrados.')
    parser.add_argument('--export-only', action='store_true', help='Solo exporta información; no ejecuta el rebalanceo.')
    parser.add_argument('--disable-headshots', action='store_true', help='Quita daño extra de cabeza a todas las armas procesadas.')
    parser.add_argument('--enable-headshots', action='store_true', help='Activa headshot normal/balanceado. No es one tap.')
    parser.add_argument('--onetap-headshots', action='store_true', help='Activa headshot one tap en las armas procesadas.')
    parser.add_argument('--headshot-mode', choices=('off', 'normal', 'onetap'), default=None, help='Modo de headshot: off, normal u onetap.')
    parser.add_argument('--onetap-distance', type=float, default=None, help='Distancia máxima real del one tap. Si no se usa, toma WeaponRange del perfil.')
    parser.add_argument('--onetap-multiplier', type=float, default=None, help='Multiplicador de headshot para one tap. Recomendado: 300 para matar sí o sí dentro del rango.')
    parser.add_argument('--onetap-no-falloff', action='store_true', help='Fuerza que el one tap no pierda daño dentro de su distancia.')
    parser.add_argument('--onetap-through-helmets', action='store_true', help='Fuerza META contra cascos nativos mediante LightlyArmouredDamageModifier.')
    parser.add_argument('--no-onetap-through-helmets', action='store_true', help='No fuerza el modificador META específico para cascos.')
    parser.add_argument('--helmet-multiplier', type=float, default=None, help='Valor de LightlyArmouredDamageModifier usado por one tap. Default del perfil: 100.')
    parser.add_argument('--helmet-penetration', type=float, default=None, help='Valor Penetration usado junto al modo cascos. Default del perfil: 1.0.')
    parser.add_argument('--include-bak', action='store_true', help='También escanea .bak/.meta.bak. Normalmente NO recomendado.')
    parser.add_argument('--no-recursive', action='store_true', help='No buscar en subcarpetas.')
    parser.add_argument('--report', type=Path, default=None, help='Ruta del reporte JSON.')
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.list_fields:
        print_supported_fields()
        return
    if args.list_flags:
        print_weapon_flags()
        return

    settings = Settings.from_config()

    if args.profile is not None:
        try:
            apply_external_profile(settings, load_profile(args.profile))
        except ProfileError as exc:
            raise SystemExit(f'ERROR DE PERFIL: {exc}') from exc

    if args.root is not None:
        settings.root = args.root
    if not settings.root.exists() or not settings.root.is_dir():
        raise SystemExit(f'ROOT inválido o inexistente: {settings.root}')

    if args.export_meta is not None:
        result = export_meta_inventory(settings.root, args.export_meta)
        print(f'[EXPORT META] archivos={result["summary"]["meta_files"]} tags={result["summary"]["unique_tags"]} -> {args.export_meta}')
    if args.export_full_profile is not None:
        result = export_full_profile(settings.root, args.export_full_profile, settings.scan)
        print(f'[EXPORT PROFILE] armas={result["_documentation"]["weapons_exported"]} -> {args.export_full_profile}')
    if args.export_only:
        if args.export_meta is None and args.export_full_profile is None:
            raise SystemExit('--export-only requiere --export-meta y/o --export-full-profile')
        return

    if args.write:
        settings.dry_run = False
    if args.preset:
        settings.active_preset = args.preset
    if args.recoil:
        settings.recoil_profile = args.recoil
    if args.accuracy:
        settings.accuracy_profile = args.accuracy
    if args.damage:
        settings.damage_profile = args.damage
    if args.range_profile:
        settings.range_profile = args.range_profile
    if args.armour:
        settings.armour_profile = args.armour
    if args.fire_rate:
        settings.fire_rate_profile = args.fire_rate
    if args.reload:
        settings.reload_profile = args.reload
    if args.headshot_profile:
        settings.headshot_profile = args.headshot_profile
        if args.headshot_profile == 'off':
            settings.headshot.enabled = False
            settings.headshot.one_tap = False
        elif args.headshot_profile == 'normal':
            settings.headshot.enabled = True
            settings.headshot.one_tap = False
        elif args.headshot_profile == 'onetap':
            settings.headshot.enabled = True
            settings.headshot.one_tap = True
    if args.only:
        settings.only_weapons = {w.upper() for w in args.only}
    if args.weapontype:
        settings.weapon_types = {w.upper() for w in args.weapontype}
    if args.ignore:
        settings.ignore_weapons.update(w.upper() for w in args.ignore)
    if args.disable_headshots:
        settings.headshot.enabled = False
        settings.headshot.one_tap = False
    if args.enable_headshots:
        settings.headshot.enabled = True
        settings.headshot.one_tap = False
    if args.onetap_headshots:
        settings.headshot.enabled = True
        settings.headshot.one_tap = True
    if args.headshot_mode:
        if args.headshot_mode == 'off':
            settings.headshot.enabled = False
            settings.headshot.one_tap = False
        elif args.headshot_mode == 'normal':
            settings.headshot.enabled = True
            settings.headshot.one_tap = False
        elif args.headshot_mode == 'onetap':
            settings.headshot.enabled = True
            settings.headshot.one_tap = True
    if args.onetap_distance is not None:
        settings.headshot.one_tap_default_distance = args.onetap_distance
        settings.headshot.one_tap_sync_distance_with_weapon_range = True
    if args.onetap_multiplier is not None:
        settings.headshot.one_tap_player_modifier = args.onetap_multiplier
        settings.headshot.one_tap_network_modifier = args.onetap_multiplier
        settings.headshot.one_tap_ai_modifier = args.onetap_multiplier
    if args.onetap_no_falloff:
        settings.headshot.one_tap_force_no_falloff = True
    if args.onetap_through_helmets:
        settings.headshot.one_tap_through_helmets = True
    if args.no_onetap_through_helmets:
        settings.headshot.one_tap_through_helmets = False
    if args.helmet_multiplier is not None:
        settings.headshot.one_tap_helmet_damage_modifier = args.helmet_multiplier
    if args.helmet_penetration is not None:
        settings.headshot.one_tap_force_penetration = True
        settings.headshot.one_tap_penetration = args.helmet_penetration
    if args.include_bak:
        settings.scan.include_bak = True
    if args.no_recursive:
        settings.scan.recursive = False
    if args.report:
        settings.report_path = args.report
        settings.write_json_report = True

    engine = RebalanceEngine(settings)
    report = engine.run()
    report.print_summary()


if __name__ == '__main__':
    main()
