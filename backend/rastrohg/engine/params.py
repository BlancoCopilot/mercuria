"""Carga de parámetros (config/params.yaml) y utilidades de acceso."""
from __future__ import annotations

import hashlib
import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(os.environ.get("RASTROHG_CONFIG_DIR", Path(__file__).resolve().parents[2] / "config"))
MATRICES = ("agua", "sedimento", "pez")


@lru_cache(maxsize=8)
def load_yaml(name: str) -> dict[str, Any]:
    with open(CONFIG_DIR / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def params() -> dict[str, Any]:
    p = load_yaml("params.yaml")
    # Completa medias del prior que dependen del fondo (null => ln(fondo)).
    for m in MATRICES:
        cfg = p["matrices"][m]
        media = cfg["beta_prior"]["media"]
        if media[0] is None:
            media[0] = math.log(cfg["fondo"])
    return p


def params_hash() -> str:
    raw = (CONFIG_DIR / "params.yaml").read_bytes()
    return hashlib.sha256(raw).hexdigest()[:12]
