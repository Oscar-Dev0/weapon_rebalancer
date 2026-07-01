# Weapon Rebalancer META V4.0.0

Esta versión corrige la suposición principal de V3: un META correcto no puede producir headshots críticos cuando otro recurso los desactiva en ejecución.

## Resultado

- Balance corporal permanece en META.
- Headshot utiliza multiplicadores, distancia, falloff y flags del arma.
- Auditoría runtime localiza el recurso que desactiva críticos o restaura estados.
- Guard opcional mantiene críticos activos sin aplicar daño manual.

## Perfil recomendado

```text
profiles/rebelion_real_onetap_v4.json
```

## Orden de uso

```text
1. audit_rebelion_runtime.bat
2. verify_rebelion_v4.bat
3. apply_rebelion.bat
4. corregir el recurso marcado [X] o instalar os_headshot_guard
```
