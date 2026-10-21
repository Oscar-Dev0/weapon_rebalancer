---
slug: balanceo
title: Balanceo y simulador
group: Balanceo
description: Cómo se calculan daño, cadencia, DPS, TTK y disparos para matar, y sus límites.
---
# Balanceo y simulador

El simulador estima el comportamiento de un arma con los campos de su META. Sirve para **comparar** armas y perfiles, no para sustituir una prueba en el juego.

> [!WARNING]
> Es un modelo teórico. No incluye la latencia, las animaciones, los componentes que cambian el daño, el desvío real de la bala ni los scripts que alteran la vida o el blindaje.

## Daño por disparo

```text
daño = Damage
     × modificador de objetivo   (NetworkPlayerDamageModifier contra jugadores, NetworkPedDamageModifier contra NPC)
     × modificador de zona       (cabeza / extremidades / torso = 1)
     × caída por distancia
     × perdigones que impactan   (BulletsInBatch × fracción que acierta, solo escopetas)
```

### Zona

| Zona | Contra jugador | Contra NPC |
| --- | --- | --- |
| Torso | 1 | 1 |
| Cabeza | `NetworkHeadShotPlayerDamageModifier` | `HeadShotDamageModifierPlayer` |
| Extremidades | `NetworkHitLimbsDamageModifier` | `HitLimbsDamageModifier` |

La cabeza solo multiplica si la distancia está entre `MinHeadShotDistancePlayer` y `MaxHeadShotDistancePlayer` **y** el objetivo tiene *critical hits* activos. Si no, cuenta como torso.

**One-tap a la misma distancia que el alcance.** En el perfil, `headshot.distance` puede ser un número (metros) o `"weapon_range"`. Con `"weapon_range"`, `MaxHeadShotDistancePlayer` se escribe igual al `WeaponRange` final del arma: el one-tap llega hasta donde llega el daño, ni más ni menos, y sigue igual si después se cambia el alcance. Con `dynamic_consider_falloff` el multiplicador se calcula con la caída máxima, así que también mata de un tiro en el último metro. La auditoría marca `headshot_distance_differs_from_weapon_range` si un arma con `"weapon_range"` quedó con otra distancia.

### Caída por distancia

```text
d ≤ DamageFallOffRangeMin              → 1
DamageFallOffRangeMin < d < RangeMax   → interpolación lineal de 1 a DamageFallOffModifier
d ≥ DamageFallOffRangeMax              → DamageFallOffModifier
d > WeaponRange                        → 0 (fuera de alcance)
```

## Cadencia

```text
intervalo = TimeBetweenShots / AnimFireRateModifier   (si el modificador es > 1)
RPM       = 60 / intervalo
```

Es la misma regla que usa el clasificador de cadencia del motor. En armas semiautomáticas es el máximo teórico haciendo clic muy rápido.

## Disparos para matar y TTK

El simulador resta el daño de cada disparo:

1. Si hay blindaje y la zona no es la cabeza (salvo que marques que el blindaje la protege), el blindaje absorbe `daño × absorción` hasta agotarse.
2. El resto baja la vida efectiva.
3. Cuenta disparos hasta que la vida llega a 0.

```text
TTK = (disparos − 1) × intervalo + recargas × ReloadTimeMP
```

Las recargas se suman si hacen falta más balas que `ClipSize` y la opción está activada.

## DPS

```text
DPS           = daño por disparo / intervalo
DPS sostenido = (ClipSize × daño) / (ClipSize × intervalo + ReloadTimeMP)
```

## Supuestos {#supuestos}

| Supuesto | Por defecto | Por qué |
| --- | --- | --- |
| Vida efectiva | 100 | Un jugador tiene 200 de vida y muere al bajar de 100 |
| Blindaje | 0 | Configurable de 0 a 100 (chaleco de GTA) |
| Absorción del blindaje | 1 (todo) | Supuesto simple; ajústalo si tu servidor usa otro sistema |
| El blindaje protege la cabeza | No | Supuesto conservador |
| Critical hits | Activos | Si un script los apaga, la cabeza cuenta como torso |
| Perdigones que impactan | 1 (todos) | Para escopetas a corta distancia |

Los supuestos solo afectan al cálculo; no modifican el perfil.

## Comparar

Agrega hasta 8 series combinando arma y fuente:

- **Original (.bak)**: cómo era antes de la primera escritura.
- **Actual**: el META tal como está.
- **Propuesto**: lo que produciría el perfil elegido (si es el borrador con cambios sin guardar, usa el borrador).

La tabla muestra la **variación porcentual** respecto a la primera serie, y las gráficas el daño y el TTK por distancia.

## Recoil, dispersión y precisión

Son tres cosas distintas:

- **Recoil del META**: el error de puntería crece con cada disparo (`RecoilAccuracyMax`, `RecoilErrorTime`) y se recupera (`RecoilRecoveryRate`). `RecoilShakeAmplitude` es la sacudida visual de cámara.
- **Recoil de cámara por script**: `qbx_recoils` sube la cámara al disparar. Es lo que el jugador siente como “patada”.
- **Dispersión / precisión**: el cono de disparo (`AccuracySpread`) y cuánto cambia al apuntar fino o al correr.
