"""Pasa las preguntas de prueba por POST /v1/chat y muestra respuesta, fuentes y lo que se esperaba.

Uso (desde backend/):  uv run python ../scripts/rag_prueba.py [--api http://localhost:8000] [--csv ...]
Cada pregunta es una llamada a OpenAI (cuesta). El límite por IP es CHAT_PER_IP_HOUR (30 por defecto).
"""
from __future__ import annotations

import argparse
import csv

import httpx

ap = argparse.ArgumentParser()
ap.add_argument("--api", default="http://localhost:8000")
ap.add_argument("--csv", default="../data/raw/rag/preguntas_prueba.csv")
a = ap.parse_args()

# La app manda la ubicación del teléfono; aquí se simula para las preguntas que dicen "ubicación compartida".
UBICACIONES = {"Guanay": (-15.4977, -67.8798)}

with open(a.csv, encoding="utf-8-sig") as fh, httpx.Client(base_url=a.api, timeout=120) as c:
    for r in csv.DictReader(fh, delimiter=";"):
        body = {"pregunta": r["pregunta"]}
        for lugar, (lat, lon) in UBICACIONES.items():
            if lugar in r["pregunta"] and "ubicación" in r["pregunta"]:
                body |= {"lat": lat, "lon": lon}
        res = c.post("/v1/chat", json=body)
        res.raise_for_status()
        out = res.json()
        print("=" * 90)
        print(f"{r['n']}. {r['pregunta']}  [{r['tipo']}]")
        print(f"ESPERADO: {r['que_esperamos']}")
        print(f"RESPUESTA ({out.get('latencia_ms')} ms, {out.get('modelo')}):\n{out['respuesta']}")
        if out.get("zona"):
            z = out["zona"]
            print(f"   zona: {z['comunidad']} · riesgo {z['nivel']}" + (" (sintético)" if z["sintetico"] else ""))
        for f in out["fuentes"]:
            print(f"   [{f['n']}] {f['archivo']}" + (f" p. {f['pagina']}" if f["pagina"] else ""))
