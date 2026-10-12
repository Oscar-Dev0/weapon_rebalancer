from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Escribe en un temporal del mismo directorio y lo reemplaza de forma atómica.

    Si el proceso se corta a mitad de escritura el archivo original queda intacto.
    Conserva los permisos del archivo anterior cuando existe.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.wrtmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            shutil.copymode(path, temp_name)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode('utf-8'))


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def write_if_changed(path: Path, text: str) -> bool:
    """Evita escrituras redundantes: solo toca el disco si el contenido cambia."""
    encoded = text.encode('utf-8')
    if path.exists() and path.read_bytes() == encoded:
        return False
    atomic_write_bytes(path, encoded)
    return True


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


def decode_strict(data: bytes) -> tuple[str | None, str | None]:
    """Decodifica UTF-8 estricto. Devuelve (texto, error)."""
    try:
        return data.decode('utf-8'), None
    except UnicodeDecodeError as exc:
        return None, f'byte inválido en posición {exc.start}'
