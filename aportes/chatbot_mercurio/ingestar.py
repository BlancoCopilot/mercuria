"""
ingestar.py — Lee todos los PDFs de docs/ (también subcarpetas) + las preguntas frecuentes,
los corta en pedazos, calcula embeddings con OpenAI y los guarda en dos archivos:
indice_vectores.npy y indice_textos.json.   (Sin base de datos.)

Se vuelve a correr cada vez que agreguen documentos.
"""
import json
import re
import sys

import numpy as np
import pymupdf
import tiktoken
from openai import OpenAI

from comun import DOCS, INDICE_META, INDICE_VEC, MODELO_EMB, cargar_faq

TAM, SOLAPE = 500, 50
enc = tiktoken.get_encoding("cl100k_base")

TEMAS = {
    "peces": ["pez", "peces", "pescado", "surubí", "pacú", "sábalo", "dorado", "pintado", "bagre", "especie"],
    "salud": ["salud", "síntoma", "cabello", "embaraz", "niño", "neurológ", "intoxica", "metilmercurio", "sangre", "orina"],
    "mineria": ["minería", "minero", "amalgam", "retorta", "relave", "cola", "draga", "oro", "cooperativa", "concesión"],
    "agua": ["río", "agua", "sedimento", "cuenca", "caudal", "lago", "turbidez"],
}


def tema_de(texto):
    t = texto.lower()
    pts = {k: sum(t.count(p) for p in v) for k, v in TEMAS.items()}
    k = max(pts, key=pts.get)
    return k if pts[k] else "general"


def limpiar(t):
    t = re.sub(r"-\n(\w)", r"\1", t)
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _leer_catalogo():
    """Usa docs/temas.json y docs/DOCUMENTOS.md (de Leonie) para el tema y el nombre de cada PDF."""
    temas, nombres = {}, {}
    tj = DOCS / "temas.json"
    if tj.exists():
        temas = json.loads(tj.read_text(encoding="utf-8"))
    md = DOCS / "DOCUMENTOS.md"
    if md.exists():
        for linea in md.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\|\s*([\w.-]+\.pdf)\s*\|\s*([^|]+)\|", linea)
            if m:
                n = m.group(2).replace("*", "").strip()
                corte = n.find(". ", 25)
                nombres[m.group(1)] = (n[:corte] if corte > 0 else n)[:120]
    return temas, nombres


TEMAS_DOC, NOMBRES_DOC = _leer_catalogo()


def nombre_bonito(ruta):
    if ruta.name in NOMBRES_DOC:
        return NOMBRES_DOC[ruta.name]
    n = ruta.stem.replace("Copy of ", "").replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", n).strip()


def pedazos_pdf(ruta):
    try:
        doc = pymupdf.open(ruta)
    except Exception as e:
        print(f"   ! no se pudo abrir: {e}")
        return [], 0
    fuente = nombre_bonito(ruta)
    tema_doc = TEMAS_DOC.get(ruta.name)
    salida, vacias = [], 0
    for pag in doc:
        texto = limpiar(pag.get_text())
        if len(texto) < 40:
            vacias += 1          # página escaneada (imagen) o en blanco
            continue
        toks = enc.encode(texto)
        for i in range(0, max(len(toks) - SOLAPE, 1), TAM - SOLAPE):
            trozo = enc.decode(toks[i:i + TAM])
            if len(trozo.strip()) > 80:
                salida.append({"texto": trozo, "fuente": fuente, "pagina": pag.number + 1, "tema": tema_doc or tema_de(trozo)})
    return salida, vacias


def huella(ruta):
    """Identifica el contenido del PDF (no el nombre): así detecta el mismo libro descargado con otro nombre."""
    import hashlib
    try:
        doc = pymupdf.open(ruta)
        # páginas del medio (la portada a veces cambia entre copias del mismo libro)
        ini = 4 if doc.page_count > 12 else 0
        texto = "".join(doc[i].get_text() for i in range(ini, min(ini + 8, doc.page_count)))
        return (doc.page_count, hashlib.md5(re.sub(r"\s+", "", texto).encode()).hexdigest())
    except Exception:
        return (ruta.name,)


def main():
    pedazos = []
    # primero los que tienen nombre en DOCUMENTOS.md, así entre repetidos se queda el de nombre bonito
    pdfs = sorted(DOCS.rglob("*.pdf"), key=lambda r: (r.name not in NOMBRES_DOC, r.name))
    print(f"\nEncontré {len(pdfs)} PDFs en la carpeta docs\n")
    vistos = set()
    for ruta in pdfs:
        clave = huella(ruta)
        if clave in vistos:
            print(f"-  {ruta.name}: repetido, lo salto")
            continue
        vistos.add(clave)
        ps, vacias = pedazos_pdf(ruta)
        aviso = f"  (ojo: {vacias} páginas sin texto, quizá escaneadas)" if vacias else ""
        print(f"OK {ruta.name}: {len(ps)} pedazos{aviso}")
        pedazos += ps

    faqs = cargar_faq()
    print(f"\nOK preguntas frecuentes: {len(faqs)}")
    for f in faqs:
        pedazos.append({"texto": f"Pregunta: {f['pregunta']}\nRespuesta: {f['respuesta']}",
                        "fuente": f["fuente"], "pagina": None, "tema": f["tema"], "faq_id": f["id"]})

    if not pedazos:
        sys.exit("\nNo hay nada que ingestar. Pon PDFs en la carpeta docs.")

    print(f"\nCalculando embeddings de {len(pedazos)} pedazos (esto cuesta centavos)...")
    cliente = OpenAI()
    vectores = []
    for i in range(0, len(pedazos), 100):
        lote = [p["texto"] for p in pedazos[i:i + 100]]
        r = cliente.embeddings.create(model=MODELO_EMB, input=lote)
        vectores += [d.embedding for d in r.data]
        print(f"   {min(i + 100, len(pedazos))}/{len(pedazos)}")

    v = np.array(vectores, dtype=np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)   # normalizado -> similitud coseno = producto punto
    np.save(INDICE_VEC, v)
    INDICE_META.write_text(json.dumps(pedazos, ensure_ascii=False), encoding="utf-8")
    print(f"\nLISTO. Guardé {len(pedazos)} pedazos. Ya puedes encender el chatbot.")


if __name__ == "__main__":
    main()
