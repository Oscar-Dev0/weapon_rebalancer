---
slug: generador
title: Generador
group: Servidor
description: Vista previa, aplicación como transacción, respaldos y reversión.
---
# Generador

El Generador escribe en el servidor lo que el perfil propone, con estas garantías:

1. **Vista previa sin escribir.** El motor trabaja sobre una copia en memoria.
2. **Plan atado al contenido.** El plan guarda el hash de cada archivo; si alguno cambia antes de aplicar, no se aplica nada.
3. **Respaldo antes de escribir.** Cada archivo se copia a `data/backups/<transacción>/files/` y se crea el `.bak` hermano si no existía.
4. **Escritura atómica** (archivo temporal + reemplazo) y verificación posterior del contenido. Si un archivo falla, se revierten los ya escritos.
5. **Solo destinos autorizados**: los packs configurados y `qbx_recoils`.
6. **Confirmación escrita**: hay que teclear `APLICAR`.

## Vista previa

| Pestaña | Contenido |
| --- | --- |
| Armas | Cada arma que cambia, campo por campo (actual → propuesto) y la auditoría one-tap |
| Archivos | Qué archivos se escriben y sus líneas; **Ver diff** muestra el cambio exacto |
| Avisos | Validación y valores sin efecto |
| qbx_recoils | Cambios del recoil por script |

Los **bloqueos** impiden aplicar:

- Archivo que no es UTF-8 válido (escribirlo perdería bytes).
- Resultado que dejaría de ser XML válido.
- El perfil pide `qbx_recoils` pero no se encontró su `config.lua`.

Si no hay nada que cambiar, el panel lo dice: el servidor ya coincide con el perfil.

## Aplicar

Pulsa **Aplicar**, escribe `APLICAR` y confirma. Después [reinicia los recursos afectados](10-fivem.md#que-reiniciar-despues-de-aplicar).

Cada aplicación queda en `data/backups/<fecha>_<perfil>/manifest.json` con los hashes antes y después de cada archivo, y en el registro `data/logs/changes.jsonl` con las armas y campos cambiados (visible en **Configuración → Registro de cambios**).

## Revertir

**Historial de aplicaciones → Revertir** devuelve los archivos byte a byte. Por seguridad, si alguno de esos archivos cambió después de aplicar, no se revierte nada (se pisaría ese cambio). También se borra el `.bak` que la transacción creó, si sigue intacto.

## Desde la línea de comandos

`run_rebalance.py` sigue funcionando igual: sin `--write` es vista previa y con `--write` escribe y crea `.bak`. El resumen de la CLI ahora distingue los cambios reales (`*`) de las anotaciones del motor (`=`) que no modifican el XML.
