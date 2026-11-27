# Chatbot del mercurio (RAG de Leonie y Alejandra)

Primera versión del asistente con documentos (RAG), hecha aparte de la plataforma para que
se integre después en `backend/rastrohg/rag/`.

- **Cómo usarlo solo:** ver `LEEME.txt` (Windows: `INICIAR.bat`).
- **Qué hace:** `ingestar.py` lee los PDFs de `docs/` y arma el índice; `api.py` responde en `POST /chat`
  con la respuesta, las fuentes (documento y página), el riesgo de la zona y la pregunta frecuente parecida.
- **Preguntas frecuentes:** `preguntas_frecuentes.csv` y `faq.json`; `sql/faq_offline.sql` es la misma lista para SQLite.
- **Documentos:** la lista completa, con tema y páginas, está en `docs/DOCUMENTOS.md`.

## Lo que NO está en el repositorio (y por qué)

| Qué | Por qué | Cómo conseguirlo |
|---|---|---|
| `clave.txt` | Es la clave de OpenAI | Cada uno pone la suya (`_clave.bat` la pide) |
| PDFs de `docs/` (~400 MB) | Son libros y estudios de otros autores, y el repositorio es público | Pedirlos al equipo (Drive) |
| `indice_vectores.npy`, `indice_textos.json` | Se generan con los PDFs | `python ingestar.py` (o `ACTUALIZAR_DOCUMENTOS.bat`) |
| `sql/chunks_pgvector.sql` (75 MB) | Se genera del índice | `python exportar_sql.py` |
