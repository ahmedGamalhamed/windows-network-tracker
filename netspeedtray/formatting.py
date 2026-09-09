from __future__ import annotations

from datetime import date


UNIT_LABELS = ("B", "KB", "MB", "GB", "TB")
BIT_LABELS = ("b", "Kb", "Mb", "Gb", "Tb")


def format_rate(bytes_per_second: float, settings) -> str:
    value = max(0.0, float(bytes_per_second))
    if settings.use_bits:
        value *= 8
        labels = BIT_LABELS
        suffix = "/s"
    else:
        labels = UNIT_LABELS
        suffix = "/s"

    base = 1024.0 if settings.binary_units else 1000.0
    places = max(0, min(3, int(settings.decimal_places)))
    scale = settings.unit_scale
    min_unit = settings.min_display_unit if settings.min_display_unit in UNIT_LABELS else "B"
    min_index = UNIT_LABELS.index(min_unit)

    if scale != "auto" and scale in UNIT_LABELS:
        index = UNIT_LABELS.index(scale)
        scaled = value / (base ** index)
        return f"{scaled:.{places}f} {labels[index]}{suffix}"

    index = 0
    scaled = value
    while scaled >= base and index < len(labels) - 1:
        scaled /= base
        index += 1
    if index < min_index:
        scaled = value / (base ** min_index)
        index = min_index
    if scaled >= 100 and places > 0:
        places = 0
    elif scaled >= 10 and places > 1:
        places = 1
    return f"{scaled:.{places}f} {labels[index]}{suffix}"


def format_compact_rate(bytes_per_second: float, settings) -> str:
    text = format_rate(bytes_per_second, settings)
    if not settings.tray_show_units:
        text = text.replace("/s", "")
        parts = text.split()
        if len(parts) == 2:
            number, unit = parts
            return f"{number}{unit[0]}"
    return text.replace("/s", "").replace(" ", "")


def format_bytes(total_bytes: int, binary: bool = True) -> str:
    value = float(max(0, total_bytes))
    base = 1024.0 if binary else 1000.0
    index = 0
    while value >= base and index < len(UNIT_LABELS) - 1:
        value /= base
        index += 1
    places = 1 if value < 10 else 0
    return f"{value:.{places}f} {UNIT_LABELS[index]}"


def today_iso() -> str:
    return date.today().isoformat()
