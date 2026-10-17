#!/usr/bin/env python3
"""Compatibilidad: la CLI original vive en weapon_rebalancer/cli.py (también `python3 wr.py rebalance ...`)."""
import sys

sys.dont_write_bytecode = True

from weapon_rebalancer.cli.main import run_legacy  # noqa: E402

if __name__ == '__main__':
    run_legacy(sys.argv[1:], 'run_rebalance.py')
