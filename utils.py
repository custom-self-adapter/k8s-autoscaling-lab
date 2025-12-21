import numpy as np


def format_size(v):
    try:
        v = float(v)
    except Exception:
        return "—"
    if not np.isfinite(v):
        return "—"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while v >= 1024 and i < len(units) - 1:
        v /= 1024.0
        i += 1
    return f"{v:.2f} {units[i]}" if i else f"{int(v)} {units[i]}"
