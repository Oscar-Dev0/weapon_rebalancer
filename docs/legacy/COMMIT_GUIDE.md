# Flujo de commits V4

## Commit 1 — auditoría runtime

```text
feat(audit): detect runtime headshot blockers and armour restoration
```

Incluye:

- `weapon_rebalancer/runtime_audit.py`;
- opciones `--audit-runtime`, `--runtime-only` y `--strict-runtime-audit`;
- `audit_rebelion_runtime.bat`.

## Commit 2 — corrección META

```text
fix(meta): avoid bodyshot amplification in helmet bypass policy
```

Cambios:

- `LightlyArmouredDamageModifier` neutral en `1.0`;
- contrato efectivo subido a `1000 × 1.25`;
- redondeo hacia arriba a seis decimales.

## Commit 3 — guard de compatibilidad

```text
feat(runtime): add minimal critical-hit guard without health or damage writes
```

Incluye `extras/os_headshot_guard` y el instalador CLI.

## Commit 4 — perfiles

```text
feat(profiles): add Rebelion real one-tap V4 variants
```

## Commit 5 — pruebas y documentación

```text
test(rebalancer): cover runtime conflicts and non-invasive guard
```

```text
docs(rebalancer): document V4 headshot diagnosis and migration
```

## Validación previa al push

```powershell
python run_rebalance.py --validate-profiles profiles
python -m unittest discover -s tests -v
python -m compileall -q .
```

No subas:

- `*.bak`;
- `reports/*.json`;
- `exports/*.json`;
- `__pycache__`;
- META privados extraídos de clientes.
