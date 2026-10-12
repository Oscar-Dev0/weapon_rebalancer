#!/usr/bin/env python3
"""Weapon Rebalancer — FiveM Weapon Configuration Studio.

    python3 wr.py               estudio interactivo en la terminal
    python3 wr.py --help        todos los comandos (automatización / SSH)
    python3 wr.py serve         panel web local

La terminal y el panel web usan el mismo motor, perfiles, validaciones e historial.
"""
import sys

sys.dont_write_bytecode = True

from weapon_rebalancer.cli.main import main  # noqa: E402

if __name__ == '__main__':
    sys.exit(main())
