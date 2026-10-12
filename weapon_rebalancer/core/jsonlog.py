from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from .paths import data_dir

_LOCK = threading.Lock()
_MAX_BYTES = 5 * 1024 * 1024
_KEEP = 3


def _log_path(name: str) -> Path:
    return data_dir('logs') / f'{name}.jsonl'


def _rotate(path: Path) -> None:
    if not path.exists() or path.stat().st_size < _MAX_BYTES:
        return
    for index in range(_KEEP - 1, 0, -1):
        older = path.with_suffix(f'.jsonl.{index}')
        newer = path.with_suffix(f'.jsonl.{index + 1}') if index + 1 <= _KEEP else None
        if older.exists() and newer is not None:
            older.replace(newer)
    path.replace(path.with_suffix('.jsonl.1'))


def log(event: str, level: str = 'info', *, stream: str = 'app', **fields: Any) -> None:
    """Log estructurado en una línea JSON. Nunca lanza: un log roto no debe tumbar la app."""
    record = {'ts': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'level': level, 'event': event, **fields}
    try:
        line = json.dumps(record, ensure_ascii=False, default=str)
        with _LOCK:
            path = _log_path(stream)
            _rotate(path)
            with open(path, 'a', encoding='utf-8') as handle:
                handle.write(line + '\n')
    except Exception:  # noqa: BLE001
        pass


def tail(stream: str = 'app', limit: int = 200) -> list[dict[str, Any]]:
    path = _log_path(stream)
    if not path.exists():
        return []
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()[-limit:]
    result: list[dict[str, Any]] = []
    for line in lines:
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return result
