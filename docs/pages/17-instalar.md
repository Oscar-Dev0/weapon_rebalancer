---
slug: instalar
title: Instalar un arma nueva
group: Servidor
description: wr.py install copia los .meta de un arma nueva a un pack como transacción reversible, con registro y sello.
---
# Instalar un arma nueva

Un arma nueva (por ejemplo la que arma `od_weapon_builder`) trae sus `.meta`: `weapons.meta`, `weaponarchetypes.meta`, `weaponanimations.meta`, `pedpersonality.meta`, `components/…/weaponcomponents.meta`. **No se copian a mano** al pack: `wr.py integrity` los marcaría como cambio a mano y no habría forma de deshacerlo. Se instalan con `wr.py install`, que deja transacción, respaldo, registro y sello.

## Uso {#uso}

```bash
# vista previa: no escribe nada
python3 wr.py install /fivem/pruebas/od_weapon_builder/out/meta/od_gs_odcobalt \
  --dest "/fivem/pruebas/resources/[streaming]/[PackArmas]/odpack/meta/od_gs_odcobalt"

# instalar (pide escribir APLICAR; en scripts va con --confirm)
python3 wr.py install /fivem/pruebas/od_weapon_builder/out/meta/od_gs_odcobalt \
  --dest "/fivem/pruebas/resources/[streaming]/[PackArmas]/odpack/meta/od_gs_odcobalt" \
  --apply --confirm APLICAR --reason "arma nueva OD Cobalt"

# deshacer
python3 wr.py rollback <transacción>
```

Pon las rutas **entre comillas**: los corchetes de `[streaming]` y `[PackArmas]` los interpreta la shell si no.

| Opción | Qué hace |
| --- | --- |
| `CARPETA` | Origen. Se copian todos sus `*.meta`, con sus subcarpetas (`components/…`). Lo demás (`.ydr`, `.ytd`, textos, carpetas ocultas, enlaces simbólicos) se ignora y la vista previa lo avisa. |
| `--dest RUTA` | Carpeta destino. Tiene que quedar dentro de un **recurso** (carpeta con `fxmanifest.lua`) de un pack configurado (`pack_roots`). Si no existe, se crea. |
| `--replace` | Permite reemplazar archivos que ya existen y son distintos. Nunca pisa uno cambiado a mano. |
| `--apply` | Instala. Sin él, solo vista previa. |
| `--confirm APLICAR` | Confirmación sin terminal interactiva. |
| `--reason "…"` | Motivo, obligatorio para instalar. Queda en el registro. |
| `--json` | Vista previa o resultado en JSON. |

También está en el menú interactivo: **Generar recurso FiveM → Instalar un arma nueva**.

## Vista previa {#vista-previa}

Por archivo muestra el estado, el tamaño nuevo y el de antes:

| Estado | Significa |
| --- | --- |
| `nuevo` | No existe en el destino: se crea. |
| `reemplaza` | Existe y es distinto: necesita `--replace`. |
| `idéntico` | Ya está igual: no se toca. |
| `bloqueado` | El archivo de origen no sirve (ver bloqueos). |

**Bloqueos** (impiden instalar):

- Un `.meta` del origen que no es UTF-8 válido o no es XML válido.
- El origen no tiene ningún `.meta`.
- Destino fuera de los packs, fuera del servidor, o fuera de cualquier recurso (sin `fxmanifest.lua`, FiveM no lo cargaría).
- Origen y destino solapados, o una ruta destino que sale del pack por un enlace simbólico.
- Un archivo que ya existe y es distinto, sin `--replace`.
- Con `--replace`: un archivo **cambiado a mano** según el sello (`wr.py integrity`), o un servidor sin sello (no se puede saber si se cambió a mano).

**Avisos** (no impiden instalar, conviene leerlos):

- Ningún `data_file` del `fxmanifest.lua` del recurso carga ese archivo (el arma no aparecería en el juego).
- El arma ya está definida en otro `.meta` de los packs (quedaría duplicada).
- El arma no está en `ox_inventory` (`data/weapons.lua`): no aparece en el inventario hasta agregarla.
- Al reemplazar un archivo, armas que estaban en él y el nuevo ya no define.
- El archivo reemplazado tiene `.bak` hermano: el «original» de las comparaciones sigue siendo el de antes.
- El servidor no tiene sello: al instalar se crea uno completo.

## Qué hace al instalar {#aplicar}

1. Vuelve a calcular la vista previa; si el origen o el destino cambiaron desde que la viste, no instala nada.
2. Respalda cada archivo que se reemplaza en `data/backups/<fecha>_install_<carpeta>/files/` y escribe `manifest.json` (los archivos nuevos y las carpetas que crea quedan anotados).
3. Crea las carpetas que falten (mismos permisos y grupo que su carpeta madre) y escribe cada archivo de forma atómica. Los archivos nuevos quedan con los permisos de su carpeta, sin ejecución (p. ej. `664` en una carpeta `775`); los reemplazados conservan los suyos.
4. Verifica cada archivo escrito. Si uno falla, deshace todo: restaura los reemplazados, borra los nuevos y las carpetas creadas.
5. Registra el evento **Instalación de arma** (`install.apply`: archivos, destino, armas y motivo) y sella solo esos archivos. Lo que otro haya cambiado a mano en otro lado sigue apareciendo en `wr.py integrity`.

Después: agrega el arma a `ox_inventory` si hace falta, ajústala con el perfil (`wr.py set flow_caribe WEAPON_X …` y `wr.py generate --apply`) y **reinicia el recurso** del pack.

## Revertir {#revertir}

`python3 wr.py rollback <transacción>` (el id sale al instalar, en `wr.py transactions` y en `wr.py registro`):

- Borra los archivos que la instalación creó y restaura byte a byte los que reemplazó.
- Quita las carpetas que creó la instalación **si quedaron vacías**; si alguien puso otra cosa adentro, la carpeta se queda.
- Actualiza el sello: los archivos borrados dejan de esperarse.
- Misma regla que con las aplicaciones: si **cualquiera** de esos archivos cambió después de instalar (por ejemplo, un `generate --apply` posterior), no revierte nada. Revierte primero lo más nuevo.

## Límites {#limites}

- Solo instala `.meta`. No copia modelos ni texturas (`stream/`) ni cambia el `fxmanifest.lua` (está en el sello: si hay que tocarlo, saldrá como cambio a mano).
- El recurso tiene que existir con su `fxmanifest.lua`: no crea recursos nuevos.
- Instala en este servidor. A principal llega con `wr.py sync principal` como el resto de las armas.
