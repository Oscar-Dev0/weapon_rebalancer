---
slug: constructor
title: Constructor visual
group: Perfiles
description: Crear un perfil completo paso a paso sin editar JSON.
---
# Constructor visual

El Constructor guía la creación de un perfil en nueve pasos. Trabaja sobre el mismo borrador que el [Editor](04-editor.md): puedes alternar entre ambos sin perder cambios.

## 1. General

- **Nombre, descripción, objetivo y etiquetas.** Documenta qué busca el perfil; los valores no deben presentarse como “realistas” si no están verificados.
- **Hereda de**: elige un perfil base para crear un [perfil derivado](07-perfiles.md#herencia).
- **Heredar valores internos del motor** (`engine_defaults`): desactivado en perfiles nuevos. Ver [engine_defaults](07-perfiles.md#engine-defaults).
- **Partir siempre del .bak** (`restore.from_backup`): hace el resultado [repetible](07-perfiles.md#repetible).

## 2. Módulos

Una fila por sección con su modo. Muestra si el valor está declarado en el perfil o viene por defecto del motor. Ver la tabla en [Perfiles → Módulos](07-perfiles.md#modulos).

## 3. Global

Valores para todas las armas procesadas (`defaults`) y la **política global de cabeza**. Las columnas Original/Actual/Propuesto usan el arma de referencia que elijas.

## 4. Categorías

Elige una categoría (`GROUP_PISTOL`, `GROUP_RIFLE`…) y ajusta sus valores y su política de cabeza. Es la forma de **aplicar cambios por categoría**. Las categorías salen de las armas reales del pack.

## 5. Armas

Lista de armas con valores propios en el perfil (campos, cabeza, flags, multiplicadores, `qbx_recoils`). Para crear una **excepción individual**, escribe el arma y ábrela en el Editor.

## 6. Excepciones

Listas `ignore_weapons`, `harmless_weapons` y sus contrapartes “permitir”. Ver [Excepciones](07-perfiles.md#excepciones).

## 7. Reglas avanzadas

- **Daño por cadencia**: tabla editable de reglas.
- **Multiplicadores exactos por arma**: arma + campo + multiplicador.
- **Clasificador de cadencia, reglas por familia, clasificación custom, reparación base y tags XML exactos**: editores JSON que se validan con el motor antes de aceptarse. Cada uno enlaza a su referencia.

## 8. Recursos

Cambios para `qbx_recoils` (recoil vertical de cámara). Ver [FiveM → qbx_recoils](10-fivem.md#qbx-recoils).

## 9. Revisión

- **Validación** del perfil con el motor.
- **Efecto en el pack**: armas y archivos que cambiarían, auditoría one-tap y si el resultado es repetible.
- **Problemas y avisos**, cada uno con su arreglo sugerido.
- **Diferencias** con la versión guardada, ruta por ruta.
- **JSON generado**, con o sin la herencia aplicada.
- **Guardar perfil** e ir al **Generador**.

> [!TIP]
> No hace falta saber JSON: cada paso escribe el perfil por ti. El JSON queda visible en la revisión para quien quiera controlarlo a mano.
