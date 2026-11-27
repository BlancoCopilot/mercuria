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

## Infografías de la OPS (agregado 26/11/2026)

| Archivo | Documento | Tema | Páginas |
|---|---|---|---|
| ops_infografias_mercurio.pdf | OPS/OMS: 4 infografías sobre el mercurio (metilmercurio y pescado, prevención en la minería, fuentes de exposición, mercurio metálico en la MAPE). Imagen con su texto transcrito como capa invisible | salud / mineria | 4 |

## Por descargar (agregado 26/11/2026)

Las preguntas frecuentes nuevas (19, de la 32 a la 50) ya citan estos archivos con el nombre de la primera columna. Descarguen cada uno, guárdenlo en `docs/` con ese nombre, agréguenlo a `temas.json` y vuelvan a correr `ingestar.py`. Si una página web no es un PDF, usen "Imprimir > Guardar como PDF" en el navegador.

| Archivo | Documento | Tema | Enlace |
|---|---|---|---|
| acha_peces_beni_jfca_2026.pdf | Loayza, Peñarrieta, Achá y Miranda-Chumacero: *Balancing nutrients and mercury* (2026), los 10 peces del río Beni. Acceso abierto según el portal de la UMSA | peces | https://doi.org/10.1016/j.jfca.2025.108840 |
| umsa_metaanalisis_mercurio_beni_2025.pdf | Valdivieso, Bravo y Yapu (IIQ-UMSA): metaanálisis del mercurio en agua, sedimentos y cabello en la cuenca del Beni, 1995-2024. Revista Boliviana de Química 42(2) | salud / agua | https://bolivianchemistryjournaliiq.umsa.bo/wp-content/uploads/2025/12/6.-nMercuryBeniRiver-Valdivieso2025.pdf |
| umsa_tesis_mercurio_madres_ninos_beni.pdf | UMSA: exposición a mercurio de 174 madres y 450 niños de 15 comunidades del río Beni | salud | https://repositorio.umsa.bo/xmlui/handle/123456789/173 |
| umsa_seladis_mercurio_adn_2026.pdf | Noticia UMSA (28/04/2026): estudio SELADIS sobre daño en sangre, hígado y ADN (guardar la página como PDF) | salud | https://www.umsa.bo/umsa-noticias-destacadas/-/asset_publisher/UusyASHyolnR/content/el-costo-oculto-del-oro-umsa-alerta-consecuencias-en-la-salud-y-el-adn-de-indigenas-de-la-amazonia-por-el-mercurio/20142 |
| ird_umsa_mercurio_bolivia_2001.pdf | Maurice-Bourgoin (IRD) con el IIQ y el Instituto de Ecología de la UMSA (2001): libro sobre el mercurio en la Amazonía boliviana | agua / peces | https://horizon.documentation.ird.fr/exl-doc/pleins_textes/doc34-04/010025628.pdf |
| ley_759_minamata.pdf | Ley 759 (17/11/2015): Bolivia ratifica el Convenio de Minamata | normas | https://diputados.gob.bo/wp-content/uploads/Leyes/Ley_N_0759.pdf |
| ds_4959_rume_mercurio.pdf | Decreto Supremo 4959 (14/06/2023): Registro Único de Mercurio y autorización previa | normas | https://faolex.fao.org/docs/pdf/bol222510.pdf |
| cedib_analisis_ds4959.pdf | CEDIB (Campanini): *Empujando al Estado para abordar el problema del mercurio* | normas | https://www.cedib.org/wp-content/uploads/2023/04/EMPUJANDO-AL-ESTADO-PARA-ABORDAR-EL-PROBLEMA-DEL-MERCURIO-OK.pdf |
| defensoria_rutas_denuncia_ambiental.pdf | Defensoría del Pueblo: cartilla de rutas de denuncia ambiental (Ley 1333, Código Penal) | normas | https://www.defensoria.gob.bo/uploads/files/cartilla-rutas-de-denuncia-y-gobernanza-final.pdf |
| ley_548_codigo_nna.pdf | Ley 548, Código Niña, Niño y Adolescente (trabajos prohibidos, art. 136) | normas | https://media.unesco.org/sites/default/files/webform/r2e002/ab5f0ee4dc8dec8c726a154eb3acfac84763e2df.pdf |
| planetgold_cartilla_comercializacion_oro.pdf | planetGOLD: cartilla de comercialización de oro responsable (requisitos para vender al BCB) | mineria | https://www.planetgold.org/sites/default/files/Cartilla%20Curso%20de%20Comrcializaci%C3%B3n%20de%20Oro%20Responsable%20FINAL.pdf |
| planetgold_folleto_bolivia.pdf | planetGOLD Bolivia: folleto informativo (5 distritos, meta de 18 t) | mineria | https://www.planetgold.org/sites/default/files/Folleto%20Informativo.pdf |
| ipen_bolivia_mape_2025.pdf | IPEN (2025): situación del mercurio en la minería de oro en Bolivia, en español | mineria / normas | https://ipen.org/sites/default/files/documents/bolivia_asgm_span_2025.pdf |

Fuentes de salud usadas en las preguntas 39 a 42 (vitaminas, quelantes y castaña). Son páginas web en inglés o portugués, así que basta con su cita:

- NIH, Oficina de Suplementos Dietéticos: selenio, vitamina C y vitamina D (límites máximos diarios).
- McKay (2013) y Kosnett (2013), *Journal of Medical Toxicology*: la quelación solo debe indicarla un médico.
- Agência FAPESP: estudio de la USP sobre selenio y mercurio en ribereños del Pará.
- Lemire y otros (2010): selenio de la castaña en la dieta de ribereños del Tapajós.

**Ojo con la recomendación de la docente:** "vitamina C y D, 1 g" solo cabe para la vitamina C (el límite es 2 g al día). Un gramo de vitamina D equivale a 40 millones de UI, una dosis tóxica (el límite es 4000 UI). La pregunta 40 ya lo explica.
