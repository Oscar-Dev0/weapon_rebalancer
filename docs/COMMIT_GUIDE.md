# Flujo recomendado para commits

## Commit 1 — núcleo

```text
feat(rebalancer): add scoped one-tap policy and mathematical damage floor
```

Incluye `headshot.py`, loader, configuración y campos.

## Commit 2 — auditoría

```text
feat(audit): detect duplicate weapons, missing manifests and one-tap blockers
```

Incluye `pack_audit.py`, reporte y CLI estricta.

## Commit 3 — perfiles

```text
feat(profiles): add balanced RP and PvP one-tap variants
```

Incluye `profiles/*.json` y `catalog.json`.

## Commit 4 — pruebas y documentación

```text
test(rebalancer): cover helmet bypass, zero network damage and scoped ranges
```

```text
docs(rebalancer): document V3 profiles and troubleshooting
```

## Antes de hacer push

```powershell
python run_rebalance.py --validate-profiles profiles
python -m unittest discover -s tests -v
python -m compileall -q .
```

No incluyas en Git:

- `*.bak`;
- reportes generados;
- inventarios exportados;
- perfiles completos extraídos de packs privados.
