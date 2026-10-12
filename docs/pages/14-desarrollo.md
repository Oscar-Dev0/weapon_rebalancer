---
slug: desarrollo
title: Desarrollo
group: Desarrollo
description: Arquitectura, módulos, API, esquemas, pruebas y cómo extender el sistema.
---
# Desarrollo

## Arquitectura

```text
weapon_rebalancer/                  (proyecto)
├── wr.py                           Lanzador: terminal interactiva, comandos y panel (serve)
├── run_rebalance.py                Lanzador de compatibilidad de la CLI original
├── weapon_rebalancer/              (paquete)
│   ├── cli/                        main (argparse), term (colores/teclas/ASCII), ui (tablas, paneles),
│   │                               commands (comandos directos), interactive (estudio), docs, legacy (CLI original)
│   ├── engine/                     config, rebalance, report, profile_loader, presets,
│   │                               tuning, headshot, baseline
│   ├── meta/                       fields, meta_utils, scanner, weapon_flags, vanilla_weapons,
│   │                               inventory, pack_audit, component_audit
│   ├── runtime/                    audit (scripts que alteran el daño), guard (recurso Lua generado)
│   ├── core/                       rutas protegidas, escritura atómica, bloqueo entre procesos (filelock),
│   │                               logs JSON, joaat, workspace
│   ├── adapters/                   lua_table, ox_inventory, fivem_pack, qbx_recoils
│   ├── catalog/params.py           registro de parámetros (método, límites, textos)
│   ├── profile_store/              schema (validación y contradicciones), resolver (herencia RFC 7386),
│   │                               repository (niveles, caché, historial, bloqueo), edit (operaciones de edición),
│   │                               migrations (v3–v7 → v8), legacy_migration (18 → 4 perfiles)
│   ├── services/                   catálogo, vista previa, procedencia, simulador, diagnóstico, generador, fachada App
│   └── api/server.py               servidor HTTP local (librería estándar)
├── web/                            panel (ES modules sin compilación): js/{core,components,pages}
├── docs/                           esta documentación (pages/*.md → js/docs-data.js); legacy/ = guías V4–V6
├── extras/                         os_headshot_guard y descargador de META de referencia
├── profiles/                       official/, server/, user/, legacy/, schemas/, migrations/
├── data/                           workspace, historial, backups, logs (no se versiona)
└── tests/
```

El **motor original** (`engine/`, `meta/`, `runtime/`) se conserva como núcleo: es el que sabe editar los META sin romperlos. Las capas nuevas lo usan sin duplicarlo:

- La **vista previa** ejecuta `RebalanceEngine` con `capture` (resultado en memoria) y `overlay` (segunda pasada para la repetibilidad).
- El **catálogo** usa el mismo escáner (`extract_weapon_blocks`) que el motor.
- El **validador** usa `apply_external_profile`: si el motor rechaza un perfil, el panel muestra su mensaje exacto.

## Un solo motor para la terminal y el panel {#motor-unico}

La terminal y el panel son dos interfaces sobre la misma fachada `services/app.py` (`App`). Ninguna de las dos tiene lógica propia de perfiles:

| Tarea | Módulo compartido |
| --- | --- |
| Leer, guardar, derivar, historial | `profile_store/repository.py` |
| Herencia y resolución | `profile_store/resolver.py` |
| Editar (fijar campo, `null`, cabeza, flags, módulos…) | `profile_store/edit.py` → `apply_ops` |
| Validar | `App.validate_profile` (`schema.py` + motor) |
| Procedencia de cada valor | `services/provenance.py` |
| Comparar, simular, generar | `App.compare`, `services/simulator.py`, `services/generator.py` |

El panel envía las modificaciones a `POST /api/profiles/ops` y la terminal llama a `App.apply_ops` directamente: mismas operaciones, mismas confirmaciones (módulos dormidos), mismo resultado. `tests/test_v8_cli.py` lo comprueba (mismo JSON, mismo `plan_hash`, misma comparación).

Concurrencia: `repository.save` toma `core/filelock.py` (bloqueo entre procesos, `fcntl` en Linux y `msvcrt` en Windows) y compara el `sha` con el que se abrió el perfil; si cambió, responde 409 en lugar de sobrescribir. Las escrituras son atómicas.

Caché: el índice de perfiles se recalcula solo si cambian las carpetas; cada perfil se relee solo si cambia su archivo; el perfil resuelto se invalida si cambia cualquier archivo de su cadena.

## Cambios en el motor

| Cambio | Motivo |
| --- | --- |
| Caché de la tokenización XML y de los regex | 4,1 s → 0,47 s con salida idéntica |
| `RebalanceEngine(capture=…, overlay=…)` | Vista previa sin escribir y comprobación de repetibilidad |
| `FileChange.content_changed` | El resumen ya no cuenta anotaciones como cambios |
| `engine_defaults` y `base_preset: none` | Perfiles neutros que no heredan de `config.py` |
| `ROOT` desde el workspace | Antes era una ruta fija |
| Paquete ordenado en `engine/`, `meta/`, `runtime/` | Antes 18 módulos sueltos en la raíz del paquete |
| Guard generado cada 250 ms | Antes reaplicaba natives en cada frame |

## API

Todo (API, página, JS, CSS y documentación) exige una sesión: cookie `wr_session` creada al canjear el enlace `/?token=` (un solo uso; ver `api/auth.py`). Las rutas `/api` exigen además la clave de la sesión en `X-WR-Token`; cuando rota, la respuesta trae `X-WR-Token-Next` y una cookie nueva, y `web/js/core/api.js` las adopta. Un 401/403 de sesión vacía la página.

| Método | Ruta | Uso |
| --- | --- | --- |
| GET | `/api/session` | Caducidad de la sesión y reglas de acceso |
| POST | `/api/session/logout` | Cierra la sesión |
| GET | `/api/status` | Versión, workspace, resumen del catálogo |
| GET/PUT | `/api/workspace` | Rutas y perfil activo |
| GET | `/api/workspace/detect` | Detección automática de rutas |
| GET | `/api/params` | Registro de parámetros, módulos y flags |
| GET | `/api/catalog[?refresh=1]` | Armas (resumen) |
| GET | `/api/catalog/weapons/<NOMBRE>` | Detalle de un arma |
| GET/POST | `/api/profiles[?all=1]` | Lista (con archivados) / crear |
| GET/PUT/DELETE | `/api/profiles/<id>` | Leer / guardar (con `sha` para conflictos) / papelera |
| POST | `/api/profiles/<id>/{derive,duplicate,rename,activate,restore,migrate,revert-migration}` | Gestión |
| GET | `/api/profiles/<id>/affected` | Armas que el perfil cambiaría |
| POST | `/api/profiles/ops` | Aplica operaciones de edición a un borrador (sin guardar) |
| POST | `/api/profiles/explain` | Procedencia de cada valor de un arma |
| POST | `/api/weapons/rows` | Estado de cada arma con un perfil (`cambia N`, `al día`…) |
| GET | `/api/profiles/<id>/history[/<archivo>]` | Historial |
| GET | `/api/profiles/<id>/export?resolved=&legacy=` | Exportar |
| POST | `/api/profiles/{import,validate,compare,migrate-all}` | Utilidades (`compare` acepta `{"source": "original"}` o `"current"` y `weapons`/`keys`) |
| POST | `/api/preview` | Vista previa de un perfil o borrador |
| POST | `/api/simulate` | Simulador |
| GET | `/api/diagnostics?runtime=&refresh_runtime=` | Diagnóstico |
| POST | `/api/generator/{plan,apply,rollback,guard}` | Generador |
| GET | `/api/generator/plan/<hash>/diff?path=` | Diff de un archivo del plan |
| GET | `/api/generator/transactions` | Historial de aplicaciones |
| GET | `/api/logs?stream=changes` | Registro de cambios |

Los errores devuelven `{error, message, hint?, details?}` con estado 400/403/404/409/422.

## Cómo extender

### Un parámetro nuevo

1. Agrega el campo a `FIELDS` en `meta/fields.py` (tag XML, tipo y sección del motor).
2. Documéntalo en `_P` de `catalog/params.py` (etiqueta, sección del panel, unidades, rango, descripción). Si no lo documentas, el registro falla al importar: no puede existir un campo sin explicación.
3. Si el motor debe recortarlo, añade sus límites a `SAFE_BOUNDS` en `engine/config.py`.
4. `python3 wr.py docs build` regenera su ficha en la [Referencia de parámetros](#parametros).

### Un validador

Las reglas estructurales están en `profile_store/schema.py` (`structural_issues` y `contradiction_issues`) y las que comparan lo declarado con el resultado del motor en `services/preview.py` (`effect_issues`). Cada aviso es `{code, severity, message, fix, path}`; `severity` es `error` (Bloqueante), `warning` (Advertencia) o `info` (Recomendación).

### Una operación de edición

Agrégala en `profile_store/edit.py` (`apply_ops`). Queda disponible a la vez para el panel (`/api/profiles/ops`) y la terminal. No la implementes en el JavaScript: `web/js/core/profile-edit.js` solo lee.

### Un comando de terminal

Escribe `cmd_x(app, term, args)` en `cli/commands.py` usando `App` y regístralo en `build_parser()` de `cli/main.py`. Usa `ui.fmt` para valores (muestra **N/D** si faltan) y respeta `--json`.

### Otro inventario

Crea un adaptador en `adapters/` que devuelva armas con nombre, etiqueta, hash y munición (como `OxInventoryData`) y úsalo en `services/catalog.py`.

### Otro recurso

`adapters/qbx_recoils.py` es el modelo: lectura, render que conserva el archivo y una sección en `resources` del perfil que el generador incluye en el plan.

## Pruebas

```bash
python3 -m unittest discover -s tests
```

- Las pruebas del motor (V3–V6, Flow Caribe) siguen intactas.
- `test_v7_*` montan un servidor completo en una carpeta temporal (pack con `.bak`, ox_inventory y qbx_recoils) y cubren adaptadores, catálogo, vista previa, repetibilidad, simulador, generador (aplicar, conflicto, UTF-8, revertir), perfiles (niveles, protección, herencia, historial, papelera, contradicciones) y la seguridad de la API.
- `test_v8_profiles.py`: JSON Merge Patch, los cuatro perfiles válidos y con metadatos, `flow_custom` ≡ `flow_caribe`, pendientes exactos, ningún perfil antiguo perdido, equivalencia sobre el pack real y migración reproducible.
- `test_v8_cli.py`: operaciones de edición, equivalencia terminal ↔ panel, protección de oficiales desde la terminal, modo sin color/ASCII, ayuda sin terminal y bloqueo entre procesos.

## Documentación

Edita `docs/pages/*.md` (front matter `slug`, `title`, `group`, `description`) y ejecuta `python3 wr.py docs build`. El build falla si un enlace interno apunta a una página o ancla inexistente, o si falta una página que el panel enlaza.
