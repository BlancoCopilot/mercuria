"""probar.py — Hace las preguntas de preguntas_prueba.csv al chatbot encendido y muestra las respuestas.
Uso (con INICIAR.bat abierto en otra ventana):  python probar.py
"""
import csv, json, urllib.request
from pathlib import Path

ruta = Path(__file__).parent / "preguntas_prueba.csv"
texto = ruta.read_text(encoding="utf-8-sig")
filas = list(csv.DictReader(texto.splitlines(), delimiter=";"))
for f in filas:
    req = urllib.request.Request("http://localhost:8000/chat", method="POST",
                                 data=json.dumps({"pregunta": f["pregunta"]}).encode(),
                                 headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())
    print("=" * 70)
    print(f"{f.get('n','')}. {f['pregunta']}")
    print(f"   ESPERÁBAMOS: {f.get('que_esperamos','')}")
    print(f"   RESPONDIÓ:   {r['respuesta']}")
    print("   FUENTES:     " + " | ".join(f"[{x['n']}] {x['fuente']}" + (f" p.{x['pagina']}" if x['pagina'] else "") for x in r["fuentes"]))
