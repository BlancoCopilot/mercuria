"""exportar_sql.py — Genera la carpeta sql/ a partir del índice actual:
  sql/chunks_pgvector.sql  -> tabla chunks(id, texto, fuente, pagina, tema, embedding vector(1536)) para PostgreSQL + pgvector
  sql/faq_offline.sql/.db  -> preguntas frecuentes en SQLite con búsqueda por palabras (app sin internet)
Lo llama ACTUALIZAR_DOCUMENTOS.bat automáticamente."""
import json, os, shutil, sqlite3, tempfile
import numpy as np
from comun import BASE, INDICE_META, INDICE_VEC, cargar_faq

SQL = BASE / "sql"
SQL.mkdir(exist_ok=True)
V = np.load(INDICE_VEC)
M = json.loads(INDICE_META.read_text(encoding="utf-8"))
q = lambda s: "NULL" if s is None else "'" + str(s).replace("'", "''") + "'"

with open(SQL / "chunks_pgvector.sql", "w", encoding="utf-8") as f:
    f.write("-- Pedazos del RAG con embeddings (text-embedding-3-small) para PostgreSQL + pgvector\n")
    f.write("CREATE EXTENSION IF NOT EXISTS vector;\nDROP TABLE IF EXISTS chunks;\n")
    f.write("CREATE TABLE chunks (id SERIAL PRIMARY KEY, texto TEXT NOT NULL, fuente TEXT, pagina INT, tema TEXT, embedding vector(1536));\n")
    for m, v in zip(M, V):
        emb = "'[" + ",".join(f"{x:.6f}" for x in v) + "]'"
        pag = m["pagina"] if m.get("pagina") else "NULL"
        f.write(f"INSERT INTO chunks (texto,fuente,pagina,tema,embedding) VALUES ({q(m['texto'])},{q(m['fuente'])},{pag},{q(m['tema'])},{emb});\n")
    f.write("-- Búsqueda: SELECT texto, fuente, pagina FROM chunks ORDER BY embedding <=> '[...vector de la pregunta...]' LIMIT 5;\n")

faqs = cargar_faq()
tmp = os.path.join(tempfile.gettempdir(), "faq_offline_tmp.db")
if os.path.exists(tmp):
    os.remove(tmp)
c = sqlite3.connect(tmp)
c.executescript("""CREATE TABLE faq (id INTEGER PRIMARY KEY, pregunta TEXT, respuesta TEXT, fuente TEXT, tema TEXT, audio TEXT);
CREATE VIRTUAL TABLE faq_fts USING fts5(pregunta, respuesta, tokenize='unicode61 remove_diacritics 2');""")
for i, x in enumerate(faqs, 1):
    c.execute("INSERT INTO faq VALUES (?,?,?,?,?,NULL)", (i, x["pregunta"], x["respuesta"], x["fuente"], x["tema"]))
    c.execute("INSERT INTO faq_fts (rowid,pregunta,respuesta) VALUES (?,?,?)", (i, x["pregunta"], x["respuesta"]))
c.commit()
with open(SQL / "faq_offline.sql", "w", encoding="utf-8") as f:
    f.write("-- Preguntas frecuentes para la app SIN internet (SQLite). Búsqueda:\n")
    f.write("-- SELECT f.* FROM faq_fts JOIN faq f ON f.id = faq_fts.rowid WHERE faq_fts MATCH 'pesca* OR comer*' ORDER BY bm25(faq_fts) LIMIT 3;\n")
    for line in c.iterdump():
        f.write(line + "\n")
c.close()
shutil.copyfile(tmp, SQL / "faq_offline.db")
print(f"SQL actualizado: {len(M)} pedazos en chunks_pgvector.sql y {len(faqs)} preguntas en faq_offline.db")
