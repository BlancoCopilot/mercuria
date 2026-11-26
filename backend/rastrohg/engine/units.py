"""Conversión a la unidad canónica de cada matriz (nunca se guardan unidades mezcladas)."""
from __future__ import annotations

CANONICA = {"agua": "ug/L", "sedimento": "mg/kg", "pez": "mg/kg"}

_FACTORES = {
    "agua": {"ng/l": 1e-3, "ug/l": 1.0, "µg/l": 1.0, "ppb": 1.0, "mg/l": 1e3, "ppm": 1e3},
    "sedimento": {"mg/kg": 1.0, "ug/g": 1.0, "µg/g": 1.0, "ppm": 1.0, "ng/g": 1e-3, "ug/kg": 1e-3, "µg/kg": 1e-3, "ppb": 1e-3},
}
_FACTORES["pez"] = _FACTORES["sedimento"]


def to_canonical(matrix: str, value: float, unit: str) -> float:
    try:
        return value * _FACTORES[matrix][unit.strip().lower().replace(" ", "")]
    except KeyError as exc:
        raise ValueError(f"unidad '{unit}' no válida para {matrix}; use una de {sorted(_FACTORES[matrix])}") from exc
