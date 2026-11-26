"""Chatbot RAG sobre los documentos de Gold4Good (mercurio: peces, salud, minería, agua).

ingest.py  PDFs + preguntas frecuentes -> fragmentos con embedding (OpenAI) en la tabla `chunks`
search.py  búsqueda híbrida (vector + texto en español) con fusión por rangos (RRF)
chat.py    arma el contexto y pide la respuesta a OpenAI, con citas [n]
"""
