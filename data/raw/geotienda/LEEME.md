# Capas de GeoTienda Bolivia (https://geotiendabolivia.com)

Descargadas el 2026-11-25 desde el catálogo (`/catalogo-completo/?gtcat=...`). Son todas **gratuitas, con descarga directa**, y no piden datos personales. Según los términos de uso de GeoTienda, se mantienen los derechos y condiciones de las fuentes originales. La ficha no identifica esas fuentes, así que hay que VERIFICARLAS antes de publicar.

| Carpeta | Contenido | Rasgos (en la cuenca piloto) | Fuente original probable | Estado en RastroHg |
|---|---|---|---|---|
| `ap_nacionales/` | Áreas protegidas nacionales | 30 (4: Madidi PN, Madidi ANMI, Apolobamba, Pilón Lajas) | SERNAP | **cargada** en `protected_area` |
| `ap_subnacionales_2025/` | Áreas protegidas subnacionales 2025 | 206 (9: Guanay, Mayaya de Teoponte, Puerta Amazónica, Alto Beni…) | gobernaciones y municipios (compilación "subnacionales_1/2") | **cargada** en `protected_area` |
| `centros_mineros/` | Centros mineros de Bolivia | 77 (4) | — | no cargada |
| `centros_mineros_pasivos/` | Centros mineros y pasivos ambientales | 1.211 (58; 41 de oro) | "Proyecto Inventariación Minas Abandonadas" (columna INFORME); probablemente SERGEOMIN | no cargada; usada para validar |

`areas_protegidas_bolivia.gpkg` y `centros_mineros_pasivos.gpkg` las genera `scripts/preparar_geotienda.py`, que normaliza las columnas (nombre, categoria, ambito).

## Resultados al cargar las áreas protegidas

- 221 de 458 sitios (18.905 ha, el 61% del área minada) están dentro de un área protegida.
- **Madidi Parque Nacional: 33 sitios (1.054 ha), 30 activos.** Es la categoría más estricta.
- Áreas de manejo integrado, donde puede haber minería con licencia: Apolobamba (87 sitios, 9.541 ha), Mayaya de Teoponte (35), Puerta Amazónica (50) y Madidi ANMI (31).
- Hay 20 sitios que tocan más de un área. Hoy `protected_area_id` guarda solo una de ellas, no necesariamente la más estricta. Pendiente.

## Validación con el inventario de minas

De las 41 minas de oro del inventario en la cuenca, tienen un sitio satelital (AMW/MapBiomas) cerca:

- En operación: 15 de 24 a menos de 1 km, 18 de 24 a menos de 3 km.
- Paralizadas: 6 de 7 a menos de 1 km.
- Abandonadas: 5 de 10 a menos de 1 km.

Las minas en operación que no aparecen en el satélite probablemente son de veta y no aluviales.

## Concesiones mineras: NO descargadas (son de pago)

En la subcategoría "Áreas mineras", tanto la nacional (actualizada a 2019, 0,26 MB) como las de La Paz (0,099 MB) y Beni (0,017 MB) son de pago. Comprarlas pide nombre, correo y pago por QR; el precio solo aparece en ese paso. Ojo: la capa es de 2019 y su tamaño parece chico para el catastro completo de la AJAM, así que conviene revisar qué contiene antes de pagar.
