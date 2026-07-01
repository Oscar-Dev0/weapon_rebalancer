# os_headshot_guard

Compatibilidad mínima para servidores donde otro recurso ejecuta:

```lua
SetPedSuffersCriticalHits(PlayerPedId(), false)
```

Este recurso **no**:

- usa `ApplyDamageToPed`;
- usa `SetEntityHealth`;
- modifica armadura;
- cancela eventos de daño;
- calcula headshots;
- reemplaza el balance del `weapons.meta`.

Solo mantiene esta native en `true`:

```lua
SetPedSuffersCriticalHits(PlayerPedId(), true)
```

## Instalación

1. Copia `os_headshot_guard` a tus recursos.
2. Coloca `ensure os_headshot_guard` **después** de recursos de combate, daño, safezones, antitank y apariencia.
3. Reinicia el servidor o el cliente.
4. Mantén `Config.Mode = 'strict'` si el auditor encuentra otro loop con `false`.

La solución limpia sigue siendo eliminar/corregir el recurso conflictivo. El guard sirve para compatibilidad mientras localizas el responsable.
