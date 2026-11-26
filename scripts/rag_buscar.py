"""Revisa qué encuentra la búsqueda del RAG (sin llamar a OpenAI) para las preguntas de prueba.

Uso (desde backend/, con DATABASE_URL apuntando a la base):  uv run python ../scripts/rag_buscar.py [csv]
"""
import csv
import sys

from rastrohg import db
from rastrohg.rag.search import search

path = sys.argv[1] if len(sys.argv) > 1 else "../data/raw/rag/preguntas_prueba.csv"
with open(path, encoding="utf-8-sig") as fh, db.tx() as c:
    for r in csv.DictReader(fh, delimiter=";"):
        print(f"\n{r['n']}. {r['pregunta']}\n   espera: {r['que_esperamos'][:110]}")
        for h in search(c, r["pregunta"]):
            print(f"   {h['score']:.4f} sim={h['similitud']:.2f} {h['filename'][:38]:38} p{h['page'] or '-':<4}"
                  f" {h['content'][:75]!r}")
