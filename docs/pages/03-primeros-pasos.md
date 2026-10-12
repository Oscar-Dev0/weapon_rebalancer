---
slug: primeros-pasos
title: Primeros pasos
group: Primeros pasos
description: Tutorial de principio a fin, de configurar las rutas a probar el cambio en FiveM.
---
# Primeros pasos

Este tutorial crea un perfil derivado de uno oficial, cambia el daño de una pistola, lo valida y lo aplica al servidor de pruebas. Tarda unos diez minutos. Al final de cada paso está el equivalente en la [terminal](12-terminal.md).

## 1. Configura el directorio del servidor

Abre el panel (ver [Instalación](02-instalacion.md)) y entra en **Configuración**. Comprueba que aparezca el mensaje *Todas las rutas son válidas*. Si no, pulsa **Detectar automáticamente**, revisa y **Guarda**.

## 2. Comprueba que se detectó ox_inventory

En el **Dashboard**, la tarjeta *Fuentes* muestra cuántas armas, componentes y municiones se leyeron de `ox_inventory/data/weapons.lua`. Si dice *no configurado*, vuelve al paso 1.

## 3. Escanea las armas

Entra en **Armamento**. La tabla une ox_inventory con los `weapons.meta`:

- **ox / sin ox**: si el arma está registrada como ítem.
- **META / META ×2 / sin META**: si tiene definición de balance (y cuántas).
- **Daño, RPM, Cabeza, Alcance**: valores actuales; si difieren del `.bak` verás el original tachado.
- **Estado**: punto de color con el número de problemas.

Si cambiaste archivos a mano, pulsa **Reescanear**. Haz clic en una fila para ver el detalle: valores original / actual / propuesto, componentes, datos de ox_inventory y problemas.

## 4. Crea un perfil

Los cuatro perfiles principales (ver [Perfiles oficiales](06-perfiles-oficiales.md)) son la base. Los oficiales están protegidos, así que se parte de uno **derivándolo**:

1. En **Perfiles**, haz clic en `competitive` y elige **Crear perfil derivado**.
2. **Identificador**: `prueba_pistolas` (será `profiles/user/prueba_pistolas.json`).

El derivado hereda todo de `competitive` y solo guardará lo que cambies. Si prefieres empezar de cero, **Nuevo perfil → Vacío**: un perfil vacío no toca nada.

Se abre el **Constructor** con el perfil nuevo.

```bash
python3 wr.py profile derive competitive prueba_pistolas
```

## 5. Modifica un arma

Ve al paso **Armas** del Constructor, escribe `WEAPON_PISTOL` y pulsa **Abrir en el editor** (o entra directo en **Editor**).

1. Deja el ámbito en **Esta arma**.
2. En la pestaña **Daño**, mueve el deslizador de **Daño base** o escribe el valor exacto, por ejemplo `20`.
3. La fila queda marcada *en el perfil* y arriba aparece *Cambios sin guardar*.
4. A los pocos segundos la columna **Propuesto** muestra el resultado calculado por el motor real.

> [!TIP]
> El botón **?** de cada parámetro explica qué controla, sus límites y enlaza a su ficha en la [Referencia de parámetros](#parametros).

## 6. Valida los cambios

Pulsa **Revisar** en la barra superior (o el paso **Revisión** del Constructor). Verás:

- **Validación**: si el motor acepta el perfil.
- **Efecto en el pack**: cuántas armas y archivos cambiarían.
- **Problemas y avisos**: por ejemplo, un valor que un preset pisa o un arma que no existe.
- **Diferencias** con la versión guardada y el **JSON** generado.

Pulsa **Guardar perfil**. La versión anterior queda en el historial.

```bash
python3 wr.py set prueba_pistolas WEAPON_PISTOL damage=20
python3 wr.py validate prueba_pistolas --preview
```

## 7. Genera los archivos

En **Generador**, elige `prueba_pistolas` y pulsa **Generar vista previa**. No se escribe nada todavía. Revisa:

- **Armas**: cada campo que cambia, de actual a propuesto.
- **Archivos**: qué `weapons.meta` se escribirán; **Ver diff** muestra las líneas exactas.
- **Avisos**: problemas que conviene corregir antes.

Si todo está bien, pulsa **Aplicar**, escribe `APLICAR` y confirma. Cada archivo se copia antes a `data/backups/`.

```bash
python3 wr.py generate -p prueba_pistolas            # vista previa
python3 wr.py generate -p prueba_pistolas --apply    # pide escribir APLICAR
```

## 8. Pruébalo en FiveM

El cliente carga los `weapons.meta` cuando arranca el recurso del arma. Reinicia el recurso (por ejemplo desde txAdmin o con `ensure` en la consola) y vuelve a entrar al servidor.

> [!WARNING]
> El simulador da números teóricos. La prueba definitiva es en el juego: dispara a un compañero con y sin chaleco a varias distancias.

¿Algo salió mal? En **Generador → Historial de aplicaciones** pulsa **Revertir** y escribe `APLICAR`: los archivos vuelven exactamente a como estaban.
