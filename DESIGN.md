# Design

Inspirado en la referencia de estilo "cuaderno de campo" que eligió el equipo (adaptada a RastroHg, sin marca ajena).

## Logo

Wordmark **MercurIA** en `panel/public/logo-mercuria.png`: tinta plana `#065233` sobre transparente, recortado del original con bordes suavizados, 96 px de alto y 32 px en la barra (26 px en celular). Versión grande para documentos: `logo-mercuria@large.png`. El favicon es la "M" sobre un cuadrado redondeado color papel.

## Mascota: "Gota"

Componente vectorial en `panel/src/components/Mascot.tsx`, hecho a partir de la ilustración del equipo: silueta suavizada (51 puntos) y cara con las medidas del original.

- `<Drop />`: gota lisa, sin cara. Va junto al logo (34 px en la barra, 26 px en el pie) y es el favicon.
- `<Mascot mood />`: con cara, para el chat. Parpadea cada ~5 s. Estados: `listening` (mira hacia abajo, al campo de texto, mientras se escribe), `thinking` (mira hacia arriba, boca chica, se balancea mientras busca) y `talking` (abre y cierra la boca un tiempo proporcional al largo de la respuesta, entre 1,5 y 6 s). Con `prefers-reduced-motion` no se anima. Los avatares chicos del historial van quietos (`still`).

## Chat flotante

`panel/src/components/ChatWidget.tsx`: Gota en un círculo abajo a la derecha, en todas las pantallas menos /preguntar. Al tocarla se despliega el chat: panel de 420 × 620 en escritorio y pantalla completa en celular. Escape lo cierra y devuelve el foco. La primera vez muestra un globo de invitación. La conversación vive en `lib/chat.tsx`: se comparte con /preguntar y sobrevive a la navegación (sessionStorage). En el mapa, el panel lateral y la hoja inferior dejan sitio a Gota.

## Aviso por ubicación

`panel/src/lib/location.tsx` y `components/LocationAlert.tsx`. Se pide en cada visita (sesión del navegador). Si el permiso del navegador ya está concedido, ubica directo. Si no, una franja explica para qué se pide antes del permiso del navegador, y "Ahora no" lo silencia hasta la próxima visita. Las coordenadas se convierten en el teléfono a la celda H3 (res. 7, ~5 km²) y al servidor solo se le pide el riesgo de esa celda y de sus 6 vecinas. Resultados:

- **Riesgo medio o alto, o una zona alta a menos de 3 km:** franja destacada (melocotón para alto, crema caléndula para medio) con "Qué hacer aquí" (ficha de la comunidad más cercana) y "Ver en el mapa" (`/?celda=<h3>`). En escritorio agrega un consejo breve. Cerrarla la oculta por esta visita.
- **Bajo, o sin estimación (fuera de la cuenca):** franja discreta.

El chat recibe el centro de la celda y la comunidad cercana para responder según el riesgo local.

**"Estás aquí" en el mapa:** cuando hay ubicación, el mapa dibuja un punto pulsante en la posición exacta. Esa posición vive solo en el navegador y no se envía. `/?yo=1` (desde el aviso) y el botón "Mi ubicación" centran el mapa y abren el panel de la ubicación: el riesgo de tu zona o, si no hay estimación, la distancia a la zona estimada más cercana, con un botón para ir a ella.

## Theme

Claro. Lienzo crema de papel, superficies sin sombras: la profundidad sale de capas crema sobre crema y de radios generosos. Una sola exclamación visual por pantalla, la **barra caléndula** (búsqueda de comunidad o la acción principal).

## Color

| Token | Valor | Rol |
|---|---|---|
| `--charcoal` | #23212c | Texto, bordes finos, botón principal |
| `--paper` | #f7f0e1 | Lienzo de todas las páginas |
| `--paper-2` | #efe5d0 | Segunda capa (paneles, filas alternas) |
| `--snow` | #ffffff | Paneles sobre imagen o mapa, campos |
| `--pine` | #006434 | Marca, titulares del inicio, enlaces. Nunca relleno de botón |
| `--marigold` | #fcbd1c | Barra de búsqueda y bloques de acento (solo superficie) |
| `--sky` | #a6dfff | Franja de aviso superior |
| `--ember` | #dd5000 | Enlace urgente en la franja de aviso |
| Riesgo bajo / medio / alto | #8fbf9a / #fcbd1c / #dd5000 | Solo en datos (mapa, leyenda, chips), siempre con texto |

## Typography

Inter (sustituto de neue-haas-unica), pesos 300 y 400. Títulos en 300 con tracking negativo (-0.02em en display, -0.005em en texto). Escala: 12 / 14 / 16 / 18 / 22 / 28 / 36 / 40 px. Números tabulares en datos.

## Shape

Radios: tarjetas y botones 20 px, bloques destacados 40 px, píldoras 99 px, chips 12 px. Sin sombras. Bordes de 1 px en charcoal para botones fantasma.

## Layout

Ancho máximo 1280 px. Escritorio: mapa con panel lateral de 400 px. Celular: mapa a pantalla completa con hoja inferior deslizable. Navegación superior transparente que en celular se vuelve un menú.
