---
slug: instalacion
title: Instalación
group: Primeros pasos
description: Requisitos, arranque del panel, acceso desde tu PC y configuración de rutas.
---
# Instalación

## Requisitos

- **Python 3.10 o superior.** No hace falta instalar paquetes: el panel usa solo la librería estándar.
- Acceso de lectura a la carpeta del servidor FiveM y de escritura a los packs de armas que quieras modificar.
- Un navegador moderno (Chrome, Edge o Firefox).

Comprueba la versión:

```bash
python3 --version
```

## Arrancar el panel

Desde la carpeta del proyecto:

```bash
cd /fivem/pruebas/weapon_rebalancer
python3 wr.py serve
```

La consola muestra una URL con un token de sesión:

```text
Weapon Rebalancer — panel web
  URL:   http://127.0.0.1:8765/?token=Xy3…
  Ctrl+C para detener.
```

Ábrela tal cual. El navegador guarda la sesión en una cookie; el token cambia cada vez que reinicias el panel.

> [!WARNING]
> El panel escucha solo en `127.0.0.1`. No lo expongas con `--host 0.0.0.0` en un servidor con IP pública: cualquiera con el token podría usarlo.

## Abrirlo desde tu PC {#acceso-remoto}

El servidor de juego no tiene escritorio, así que el panel se abre a través de un túnel:

- **VS Code (Remote SSH)**: abre la pestaña *Puertos*, agrega el `8765` y abre la URL con el token cambiando el host por `localhost`.
- **SSH**: `ssh -L 8765:127.0.0.1:8765 usuario@servidor` y abre `http://localhost:8765/?token=…` en tu PC.

## Configurar las rutas {#rutas}

La primera vez el panel detecta solo las rutas. Revísalas en **Configuración**:

| Ruta | Qué es | Uso |
| --- | --- | --- |
| Carpeta del servidor | La que contiene `resources/` | Todas las demás deben estar dentro |
| Packs de armas | Carpetas con los `weapons.meta` (por ejemplo `[PackArmas]`) | Lectura y **única escritura de META** |
| ox_inventory | Carpeta del recurso (con `data/weapons.lua`) | Solo lectura |
| qbx_recoils | `qbx_smallresources/qbx_recoils/config.lua` | Escritura solo si el perfil lo pide |
| Auditoría de scripts | Por defecto `resources/` | Solo lectura |
| Packs de referencia | META originales de GTA V (opcional) | Solo lectura (`baseline_repair`) |

La configuración se guarda en `data/workspace.json`. El botón **Detectar automáticamente** vuelve a buscar las rutas.

> [!NOTE]
> Si una ruta no existe o queda fuera de la carpeta del servidor, el panel no guarda la configuración y te dice cuál es.

## Terminal {#terminal}

Sin argumentos, `wr.py` abre el menú interactivo (navegación con flechas, números y `/` para buscar):

```bash
python3 wr.py
```

Todo también funciona con comandos directos, útiles por SSH o en scripts:

```bash
python3 wr.py status                         # estado del servidor y del perfil activo
python3 wr.py profiles                       # perfiles oficiales, servidor y usuario
python3 wr.py weapon WEAPON_PISTOL           # ficha de un arma con la procedencia de cada valor
python3 wr.py validate --preview             # valida todos los perfiles contra el pack real
python3 wr.py generate -p flow_custom        # vista previa del generador
python3 wr.py docs build                     # regenera esta documentación
```

La guía completa, con capturas reales, está en [Terminal](12-terminal.md).

La herramienta original sigue disponible con todas sus opciones (acepta un id de perfil o una ruta):

```bash
python3 run_rebalance.py --profile flow_custom            # vista previa
python3 run_rebalance.py --profile flow_custom --write    # escribe (crea .bak)
```

## Seguridad del panel

- Token por arranque y cabecera `X-WR-Token` en cada llamada a la API (protege contra CSRF).
- Se valida la cabecera `Host` (protege contra *DNS rebinding*).
- Solo se sirven archivos de `web/` y `docs/`.
- Escrituras limitadas a los packs configurados, `qbx_recoils`, `profiles/` y `data/`. Los perfiles oficiales no se pueden modificar.
- Nada se aplica al servidor sin escribir `APLICAR`.
