#!/usr/bin/env python3
"""Compatibilidad: la CLI original vive en weapon_rebalancer/cli.py (también `python3 wr.py rebalance ...`)."""
import sys

sys.dont_write_bytecode = True

from weapon_rebalancer.cli.legacy import main  # noqa: E402

if __name__ == '__main__':
    main()
