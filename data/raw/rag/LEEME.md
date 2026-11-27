# Gold4Good · contenido del chatbot RAG (de Leonie)

25/11/2026. Hay 3 paquetes; cada uno es para alguien distinto.

## 1. Para Ale: `Gold4Good_RAG_contenido.zip`

- `docs/`: **21 PDFs listos para `ingestar.py`.** Todos tienen texto, así que **no hace falta OCR ni Tesseract**: los 3 libros escaneados ya se pasaron por OCR, y el texto está dentro del PDF. Basta con `page.get_text()` de pymupdf.
- `docs/temas.json`: el tema de cada PDF (`peces`, `salud`, `mineria` o `agua`), para la columna `tema` de la tabla `chunks`.
- `docs/DOCUMENTOS.md`: qué es cada documento.
- `preguntas_frecuentes.csv`: las 31 preguntas, separadas por `;`. Cada una tiene su fuente con página, y la columna `verificado`:
  - `sí` (25): todo lo que dice está en un PDF.
  - `parcial` (2): una parte no tiene fuente; está explicado en `nota_revision`.
  - `propio` (4): textos del equipo sobre la app y las instituciones.
- `preguntas_prueba.csv`: 10 preguntas difíciles para probar `/chat`. La 10 está fuera de los documentos: el chatbot debe decir que no sabe.

Para tener en cuenta:

- `manual_operacion_retorta_es.pdf` es la **traducción al español** del manual brasileño de retorta. El original en portugués ya no va en `docs/`. En la traducción se quitaron los primeros auxilios de 1995 que hoy no se recomiendan (provocar el vómito, hacer respirar éter), para que el chatbot nunca los repita. Los primeros auxilios actuales salen de la ficha de la OIT y la OMS (`oit_oms_ficha_seguridad_mercurio.pdf`) y están en la pregunta 13, "¿Qué hago si alguien se intoxica con mercurio?".
- La entrevista del boletín UMSA y el estudio de CINCIA (Perú) no siempre coinciden en los peces. Para el paiche manda el estudio de Bolivia: en el río Beni tiene poco mercurio.
- Para la demo, las 3 preguntas ensayadas (pescado, retorta, síntomas) están verificadas.

## 2. Para Erlan: `preguntas_frecuentes.json`

Las mismas 31 preguntas en JSON, para el SQLite de la app sin internet:

```json
{ "id": 1, "pregunta": "...", "respuesta": "...", "fuente": "...", "tema": "peces",
  "palabras_clave": ["pescado", "comer", "pacú"], "verificado": "sí" }
```

Las 4 marcadas `propio` describen la app (reporte anónimo, 5 preguntas, sin internet). Confirmen que la app funciona así.

## 3. Para Hector y Erwin: `Gold4Good_mapas.zip`

Las dos capas están en WGS84, las mismas coordenadas del GPS. Más detalles en `mapas/LEEME.md`.

- `rios_menores/`: red de ríos de Bolivia, 22 289 tramos (shapefile).
- `concesiones_mineras/areas_mineras_bolivia_raisg.geojson`: 7 979 áreas mineras con su titular (`cia`). Fuente: RAISG, con datos de SERGETECMIN 2013. El catastro actual de la AJAM no es público.

## Figuras de los PDFs (26/11/2026)

Los gráficos, tablas en imagen y mapas de los PDFs también se pueden vectorizar:

```bash
docker compose exec api rastrohg rag-ingest /data/raw/rag --imagenes --force
```

Un modelo de visión de OpenAI describe cada figura útil (con sus cifras) y esa descripción entra al chatbot como un fragmento de su página. Se saltan los logos, los íconos y las páginas escaneadas que ya tienen OCR. Las descripciones quedan en `imagenes_descripciones.json`: revísenlas (se pueden corregir a mano) y la próxima ingesta las reutiliza sin volver a pagar. Tope: 40 figuras por PDF (`RAG_IMAGES_MAX_PER_DOC`); modelo: `RAG_VISION_MODEL` (vacío = el mismo del chat).
