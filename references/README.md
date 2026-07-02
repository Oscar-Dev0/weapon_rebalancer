# Paquete de referencia vanilla

V6 puede leer un paquete de `weapons.meta` original mediante `--reference-root`. Esto permite restaurar valores absolutos aunque el `.bak` local ya esté modificado.

En Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\references\download_original_gtav_metas.ps1
```

Después usa:

```bat
python run_rebalance.py --root "C:\ruta\PackArmas" --profile profiles\vanilla_repair_custom_plus15_absolute_v6.json --reference-root references\snags_original\metas --write
```

Fuente de referencia: `CyCoSnag/snag_weapon_metas`, que publica los META originales de GTAV y DLC. Revisa su licencia GPL-3.0 antes de redistribuir esos archivos. El descargador no incluye ni redistribuye el paquete dentro de este ZIP.
