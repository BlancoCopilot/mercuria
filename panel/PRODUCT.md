# Product

<!-- impeccable:product-schema 1 -->

## Platform

web (panel MercurIA) + android (app MercurIA: el mismo código React empaquetado con Capacitor; `mobile.html`, `src/mobile/`).

## Users

- Familias, pescadores y mineros de comunidades ribereñas de la Amazonía boliviana (ríos Beni, Madre de Dios, Tipuani, Mapiri, Kaká). Poca señal, celulares Android de gama baja, poca experiencia con apps; algunos leen poco y prefieren escuchar. Hablan castellano y también aymara, quechua o guaraní. *(Inferido del código y del brief del RAG; propuesto al usuario sin objeción.)*
- En el panel web, además: laboratorios, promotores de salud, líderes, autoridades e investigadores, cada uno con su sección y su ingreso.

## Product Purpose

MercurIA (backend RastroHg) estima dónde hay mercurio de la minería de oro en Bolivia, con qué certeza, y qué hacer: qué pescado comer, cómo protegerse, a qué centro de salud ir. Une detección satelital, factores de emisión, mediciones publicadas y reportes de la gente.

La app de celular es la versión para la comunidad. Tiene tres cosas y nada más: el riesgo de mi zona y qué hacer, preguntar a Gota (también por voz) y avisar de forma anónima. Además manda una alerta cuando la persona entra a una zona de riesgo medio o alto, también con la app cerrada. *(Pedido por el usuario el 26/11/2026: "simplifica la interfaz, no con tantas secciones como en la web, y manda alerta cuando esté en una zona con riesgo".)*

## Positioning

Estimaciones con incertidumbre explícita ("toda cifra es una estimación con su rango"), por zona H3 de ~5 km², con respuestas citadas de documentos verificados (OMS, UMSA-WCS, OIT/OMS) en vez de consejos genéricos.

## Constraints

- Privacidad: la ubicación exacta no sale del teléfono; solo se consulta la zona (celda H3 res 7). Reportes anónimos (sin nombre ni carnet). La IP no se guarda.
- Todo nivel de riesgo se muestra con texto, nunca solo con color.
- Funciona con mala señal: los reportes se guardan y se envían al volver la conexión.
- Primeros auxilios solo los de la ficha OIT/OMS; nunca provocar el vómito.
- Los parámetros de salud siguen en revisión con las autoridades: decirlo donde se muestre un consejo.

## Assets

Logo `public/logo-mercuria.png`, mascota Gota (`src/components/Mascot.tsx`, gota verde con cara), tokens en `src/styles/tokens.css`.

## Deployment

- Web y API en https://mercuria.hectorblanco.cloud (VPS propio detrás de un túnel de Cloudflare; elegido por el usuario el 26/11/2026). La app de celular usa ese mismo dominio.
- APK para instalar: https://mercuria.hectorblanco.cloud/descargas/MercurIA.apk
