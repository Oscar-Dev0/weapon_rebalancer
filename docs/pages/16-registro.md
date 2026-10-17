---
slug: registro
title: Registro, cambios a mano y paso a principal
group: Servidor
description: Sello de integridad, detección de cambios hechos fuera de la herramienta, wr.py sync y wr.py registro.
---
# Registro, cambios a mano y paso a principal

**Regla del servidor:** las armas se cambian **solo** con weapon_rebalancer. Nada de editar `weapons.meta` a mano ni copiarlos con `cp` a principal. Si no, los dos servidores se desincronizan, nadie sabe quién cambió qué y se pierden cosas como el `ArmourPenetrating` que dejó a los chalecos sin efecto.

## Qué queda registrado

Todo va a `data/logs/changes.jsonl`. Se ve con:

```bash
python3 wr.py registro            # lo más nuevo primero
python3 wr.py registro --json     # para scripts
```

| Evento | Cuándo |
| --- | --- |
| Aplicación de perfil | `wr.py generate --apply` (o el botón del panel) |
| Reversión | `wr.py rollback <id>` |
| Paso a otro servidor | `wr.py sync principal --apply` |
| Sello | después de cada aplicación, reversión o paso, y con `wr.py integrity seal` |
| **CAMBIO A MANO detectado** | un archivo de armas cambió sin pasar por la herramienta |
| **CLI ANTIGUA escribió** | `wr.py rebalance --write` o `run_rebalance.py --write` (sin transacción) |

## Sello de integridad

El sello guarda el SHA-256 de cada archivo de armas: los `.meta` y `fxmanifest.lua` de los packs y el `config.lua` de qbx_recoils. Hay uno por servidor (`local` y cada destino de `sync_targets`).

```bash
python3 wr.py integrity                       # ¿alguien cambió armas a mano en este servidor?
python3 wr.py integrity --server principal    # lo mismo en principal
python3 wr.py integrity seal --reason "revisado: arreglo X de Oscar"   # aceptar el estado actual
```

- `wr.py status` muestra la línea **Cambios a mano**.
- `wr.py generate` avisa si hay cambios a mano antes de aplicar encima.
- Cada cambio a mano se registra una vez, con la fecha de modificación del archivo.
- Lo correcto ante un cambio a mano: pasarlo a un perfil (`wr.py set` / `wr.py headshot`) y aplicarlo. Sellar a mano solo si se revisó y se acepta tal cual; el motivo es obligatorio.

## Paso a principal

Configurado una vez: `wr.py settings set sync_targets.principal=/fivem/principal`.

```bash
python3 wr.py sync principal                          # vista previa: qué archivos cambian
python3 wr.py sync principal --apply --reason "balance flow_onetap"   # pide escribir APLICAR
python3 wr.py rollback <id>                           # deshace el paso
```

- Copia solo los archivos de armas que difieren. **Nunca borra** archivos de principal; los que solo existen allí se informan.
- Respalda cada archivo de principal en `data/backups/<id>_sync_principal/` y verifica cada copia; si una falla, revierte las demás.
- Si un archivo de principal se cambió a mano desde su último sello, **no lo pisa** salvo con `--force` (queda marcado como FORZADO en el registro).
- Después hay que reiniciar principal para que cargue las armas.

## Límites

- Solo controla los packs configurados (`pack_roots`) y qbx_recoils. Un `weapons.meta` dentro de otro recurso (p. ej. `stungrenade`) no entra en el sello.
- El sello dice **qué** archivo cambió y **cuándo**, no **quién**: eso no lo guarda el sistema de archivos. Para saber quién, el cambio tiene que pasar por la herramienta.
