"""
api.py — El chatbot (la "bibliotecaria").  Encender:  uvicorn api:app --host 0.0.0.0 --port 8000
Probar en el navegador: http://localhost:8000/docs

POST /chat  {"pregunta": "...", "lat": -15.4, "lon": -67.5}   (lat y lon son opcionales)
GET  /faq   lista de preguntas frecuentes (para que la app las guarde sin internet)
"""
import csv
import json

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel

from comun import BASE, INDICE_META, INDICE_VEC, MODELO_CHAT, MODELO_EMB, cargar_faq

K = 5
cliente = OpenAI()
app = FastAPI(title="Chatbot Mercurio — Gold4Good")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

VECTORES = np.load(INDICE_VEC)
PEDAZOS = json.loads(INDICE_META.read_text(encoding="utf-8"))
FAQS = cargar_faq()
FAQ_POR_ID = {f["id"]: f for f in FAQS}
print(f"Chatbot listo con {len(PEDAZOS)} pedazos de información.")

INSTRUCCION = """Eres el asistente de la app Gold4Good para comunidades y mineros de Bolivia que conviven con el mercurio.
Reglas:
- Responde SOLO con la información del CONTEXTO. No inventes datos ni cifras.
- Lenguaje muy simple y frases cortas. Responde en español sencillo.
- OBLIGATORIO: termina cada frase que tenga un dato con el número de su fuente entre corchetes, por ejemplo [1] o [2]. Nunca respondas sin al menos una cita.
- Una regla general del CONTEXTO también responde los casos particulares. Ejemplo: si el CONTEXTO dice "cocinar no elimina el mercurio", a "¿el pescado ahumado/frito/hervido tiene menos mercurio?" respondes "No. Cocinar el pescado, de cualquier forma, no quita el mercurio [n]".
- Antes de decir "No tengo esa información", revisa otra vez cada fragmento del CONTEXTO buscando una regla general que aplique.
- Solo si el CONTEXTO de verdad no tiene nada relacionado, di "No tengo esa información" y recomienda ir al centro de salud (si es de salud) o a la autoridad ambiental o minera (si es de minería).
- Si te dan el NIVEL DE RIESGO de la zona del usuario, menciónalo primero y adapta el consejo.
- No diagnostiques enfermedades: ante síntomas, recomienda ir al centro de salud.
- Máximo 6 frases."""


class Pregunta(BaseModel):
    pregunta: str
    lat: float | None = None
    lon: float | None = None


def riesgo_en(lat, lon):
    """Lee riesgo.csv (columnas: lat_min,lat_max,lon_min,lon_max,nivel,nota) si el equipo del mapa lo deja aquí."""
    ruta = BASE / "riesgo.csv"
    if lat is None or lon is None or not ruta.exists():
        return None
    for f in csv.DictReader(ruta.read_text(encoding="utf-8-sig").splitlines()):
        try:
            if float(f["lat_min"]) <= lat <= float(f["lat_max"]) and float(f["lon_min"]) <= lon <= float(f["lon_max"]):
                return {"nivel": f["nivel"], "nota": f.get("nota", "")}
        except (KeyError, ValueError):
            continue
    return None


@app.post("/chat")
def chat(p: Pregunta):
    q = np.array(cliente.embeddings.create(model=MODELO_EMB, input=p.pregunta).data[0].embedding, dtype=np.float32)
    q /= np.linalg.norm(q)
    sim = VECTORES @ q
    top = np.argsort(-sim)[:K]
    elegidos = [PEDAZOS[i] for i in top]

    contexto = "\n\n".join(
        f"[{n}] (Fuente: {c['fuente']}{', pág. ' + str(c['pagina']) if c['pagina'] else ''})\n{c['texto']}"
        for n, c in enumerate(elegidos, 1)
    )
    riesgo = riesgo_en(p.lat, p.lon)
    extra = f"\nNIVEL DE RIESGO EN LA ZONA DEL USUARIO: {riesgo['nivel']} {riesgo['nota']}" if riesgo else ""

    r = cliente.chat.completions.create(
        model=MODELO_CHAT, temperature=0,
        messages=[{"role": "system", "content": INSTRUCCION},
                  {"role": "user", "content": f"CONTEXTO:\n{contexto}\n{extra}\n\nPREGUNTA: {p.pregunta}"}],
    )

    # pregunta frecuente más parecida (para ofrecer su audio en la app)
    faq = None
    idx_faq = [i for i, c in enumerate(PEDAZOS) if "faq_id" in c]
    if idx_faq:
        mejor = max(idx_faq, key=lambda i: sim[i])
        if sim[mejor] > 0.5:
            f = FAQ_POR_ID.get(PEDAZOS[mejor]["faq_id"])
            if f:
                faq = {"id": f["id"], "pregunta": f["pregunta"], "audios": f.get("audios", {})}

    return {
        "respuesta": r.choices[0].message.content,
        "fuentes": [{"n": n, "fuente": c["fuente"], "pagina": c["pagina"], "extracto": c["texto"][:300]}
                    for n, c in enumerate(elegidos, 1)],
        "riesgo": riesgo,
        "faq_parecida": faq,
    }


@app.get("/faq")
def faq():
    return FAQS
