from __future__ import annotations


def joaat(text: str) -> int:
    """Hash Jenkins one-at-a-time de GTA V, sin signo (igual que `joaat()` en Lua)."""
    value = 0
    for byte in text.lower().encode('utf-8'):
        value = (value + byte) & 0xFFFFFFFF
        value = (value + (value << 10)) & 0xFFFFFFFF
        value ^= value >> 6
    value = (value + (value << 3)) & 0xFFFFFFFF
    value ^= value >> 11
    value = (value + (value << 15)) & 0xFFFFFFFF
    return value


def signed(value: int) -> int:
    """Convierte un hash sin signo a la forma con signo que muestran natives y configs."""
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value >= 0x80000000 else value


def unsigned(value: int) -> int:
    return value & 0xFFFFFFFF
