# Documentos para el RAG (carpeta docs/)

Estado al 25/11/2026. "Escaneado" = no se puede seleccionar el texto: necesita OCR antes de ingestar.

## Listos para ingestar (tienen texto)

| Archivo | Documento | Tema | Páginas |
|---|---|---|---|
| oms_mercurio_salud.pdf | OMS: *El mercurio y la salud* (31/03/2017) | salud | 1 |
| cincia_mercurio_loreto_peces.pdf | CINCIA / planetGOLD: *Mercurio en Loreto: exposición humana y en peces* (Perú) | peces / salud | 71 |
| sinchi_mercurio_peces_colombia.pdf | Instituto SINCHI: mercurio en agua, sedimento y peces de la Amazonía colombiana | peces / agua | 26 |
| defensoria_convenio_minamata_bolivia.pdf | Defensoría del Pueblo: *Cumplimiento del Convenio de Minamata en Bolivia (2017-2022)* | normas / salud | 152 (38 sin texto) |
| cedib_negocio_mercurio_bolivia.pdf | CEDIB (Campanini): *El negocio del mercurio en Bolivia*. Retorta, normas (RAAM art. 27), casos de cooperativas | minería / normas | 133 |
| cedib_agua_y_mineria_bolivia.pdf | CEDIB, *Pueblo y Soberanía n.º 3: Agua y minería en Bolivia* | agua | 32 |
| cedib_mineria_aluvial_oro_bolivia.pdf | CEDIB: *El caso de la minería aluvial de oro en Bolivia* | minería / agua | 44 |
| informe_cop16_mineria_ilegal_oro.pdf | *Minería ilegal de oro: impactos sobre los derechos humanos y la biodiversidad en la Amazonía* (COP-16) | salud / peces | 104 |
| llamamiento_amazonia_oro_mercurio_2026.pdf | *Llamamiento a la Santa Sede por la protección de la Amazonía: minería del oro y mercurio* (2026) | peces / salud | 48 |
| rutas_del_oro_riberalta.pdf | *Las rutas del oro ilegal*: el caso de Riberalta, Bolivia | minería | 29 |
| guia_oro42_colas_con_mercurio.pdf | Guía oficial del desafío ORO-4.2 (Gold4Good). Qué son las colas y cómo llegan al río | relaves | 6 |
| umsa_metaanalisis_mercurio_beni.pdf | Valdivieso, Bravo y Yapu (IIQ-UMSA): *Metaanálisis de la contaminación por mercurio en la cuenca del río Beni* (Revista Boliviana de Química, 2025). Mercurio en agua, sedimento y cabello entre 1995 y 2024; límite boliviano para agua (DS 24176: 1000 ng/l); referencias para sedimento (TEL 0,17 y PEL 0,486 µg/g) y cabello (1, 2 y 10 µg/g). **Texto en inglés con resumen en español** | agua / salud | 17 |
| umsa_boletin_peces_beni.pdf | Boletín UMSA: resultados del estudio UMSA-WCS de 10 peces del río Beni (2025). Blanquillo alto; surubí, pantalón y corvina intermedios; pacú, tambaquí, paiche y yatorana bajos | peces (Bolivia) | 3 |
| cedib_pronunciamiento_pesqueros.pdf | Pronunciamiento de 11 asociaciones de pescadores del río Beni sobre el mercurio (abril 2024) | peces / contexto | 2 |
| atsdr_toxfaqs_mercurio.pdf | ATSDR (EE. UU.): *ToxFAQs sobre el mercurio*. Síntomas, análisis (sangre, orina, cabello), lactancia, cuidados en casa, límite de agua | salud / agua | 2 |
| atsdr_resumen_salud_mercurio.pdf | ATSDR: *Resumen de salud pública: mercurio* (1999) | salud | 20 |
| epa_derrame_mercurio_casa.pdf | EPA (EE. UU.): qué hacer si se derrama mercurio (copia de la página web) | salud | 3 |
| manual_operacion_retorta_es.pdf | DNPM Brasil (1995): manual de amalgamación y retorta, **traducido al español** por el equipo. Pasos de la retorta (p. 10 del original). Se quitaron solo los primeros auxilios de 1995 que hoy no se recomiendan (provocar el vómito, hacer respirar éter, dar huevo crudo, leche o aceite) | retorta | 6 |
| oit_oms_ficha_seguridad_mercurio.pdf | OIT y OMS: *Ficha internacional de seguridad química ICSC 0056: Mercurio* (2019). **Primeros auxilios actuales** (inhalación, piel, ojos, ingestión), síntomas y prevención | salud | 4 |
| cdc_hervir_agua.pdf | CDC (EE. UU.): hervir el agua no elimina las sustancias químicas (copia de la página web) | agua | 1 |

## Libros escaneados, ya con OCR (25/11/2026)

Se pasaron por el OCR que trae Windows (español). Los PDFs de esta carpeta ya tienen el texto invisible encima de la imagen: se puede buscar y seleccionar, y `ingestar.py` los puede leer sin hacer OCR. El texto suelto está en `referencia/ocr_texto/` para revisarlo. Los originales escaneados siguen en Descargas.

| Archivo | Documento | Tema | Páginas |
|---|---|---|---|
| libro_manejo_ambiental_pequena_mineria.pdf | Wotruba y otros: *Manejo ambiental en la pequeña minería* (MEDMIN / COSUDE). Retorta paso a paso (p. 72-73), quema en casa y derrames (p. 24 y 28) | minería / agua | 94 |
| libro_pequena_mineria_tecnicas_procesos.pdf | Priester, Hentschel y Benthin: *Pequeña minería: técnicas y procesos*. Retortas (p. 41-47), métodos sin mercurio | minería | 72 |

El OCR tiene errores menores (por ejemplo "10" en vez de "lo", "denames" en vez de "derrames"), sobre todo en portadas y tablas. El texto corrido sale bien.

## Todavía faltan

- **Síntesis del IRD sobre el río Beni**: el sitio del IRD sigue en mantenimiento (probado de nuevo el 25/11). Ya no es urgente: el boletín UMSA cubre los peces de Bolivia.
- **El artículo completo UMSA-WCS** (DOI 10.1016/j.jfca.2025.108840) es de pago; el boletín resume sus resultados.

## Otras carpetas del proyecto

- `referencia/`: material del equipo que NO va al chatbot (guías ORO-4.1 y 4.2, notas de la app, planilla de inputs, mapas en PNG, recursos audiovisuales).
- `mapas/`: capa de ríos (22 289 tramos) y de áreas mineras de Bolivia (7 979, con su titular). Ver `mapas/LEEME.md`.
- `preguntas_frecuentes.csv` y `preguntas_prueba.csv`: en la carpeta principal.

| cedib_carvajal_mercurio_salud_amazonia_boliviana.pdf | Carvajal (SELADIS-CEDIB): Mercurio y salud en la Amazonía boliviana. Estudio piloto en mujeres indígenas de los ríos Beni y Madre de Dios | salud | |

| cedib_informe_cop30_cambio_climatico_mineria_ilegal.pdf | CEDIB y otros: Cambio climático, minería ilegal y derechos humanos en la Amazonía (COP30) | mineria | |
