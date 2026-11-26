# Mediciones publicadas de mercurio en la cuenca piloto (Beni alto: Kaká, Tipuani, Mapiri)

Revisión del 2026-11-25. `publicadas_beni_v1.csv`: 22 filas, **cargadas el 2026-11-25** (versión 10 del mapa), después de corregir el motor (ver "Correcciones hechas").

Efecto de la carga:
- Agua: los 12 valores "< 1 µg/L" no aportan información (el LD está por encima de lo esperado) y el motor los ignora. Siguen en la base.
- Sedimento: las 10 filas se usan con su peso por antigüedad (0,24–0,32). El Kaká bajo pasó de 1,4 mg/kg (rango 0,035–56), que salía del supuesto, a 0,18 (0,07–0,43), coherente con lo medido. El ajuste encontró variabilidad entre años (nugget 0,5).
- Riesgo: sin cambios apreciables. 47 de las 52 celdas en "alto" las decide el **pescado**, que no tiene ningún dato. Lo más urgente ahora son las mediciones de peces.

## Qué hay en el CSV

| Fuente | Matriz | Filas | Año | Ubicación | Problema |
|---|---|---|---|---|---|
| Maldonado Flores 2022, tesis UMSA (laboratorio ABEN) | agua | 12 | feb-2019 (época húmeda) | exacta (UTM 19S, validada contra HydroRIVERS) | **todas < 1 µg/L** (límite de detección alto): solo sirven como cota superior |
| Valdivieso et al. 2025, metaanálisis Rev. Bol. Quím. (compila IRD) | sedimento | 10 | 1995–2000 | aproximada (~10 km) | datos de 25–30 años; no está claro si es sedimento de fondo o en suspensión |

Hallazgo clave del metaanálisis: el último dato de agua de la cuenca es de 2006 y el último de sedimento de 2004–2005. **No hay mediciones ambientales recientes publicadas.**

## Revisado y NO cargado (motivo)

- **Rodriguez-Levy et al. 2022**, Heliyon 8:e11649 (PMC9699965). Peces de mercado de Rurrenabaque y Riberalta, 2015. Solo publica agregados (mediana 0,19; p5 0,03; p95 1,30 µg/g ww; n = 106). La tabla A1 tiene especie y zona pero no el Hg por individuo. → Pedir los datos crudos a los autores (zona 1 = 22 peces del Beni en Rurrenabaque).
- **UMSA/WCS 2024**, 10 especies del mercado de Rurrenabaque, n = 70. Solo se conoce por prensa (Mongabay 13-mar-2026), con cifras contradictorias. Se mencionan Erick Loayza, Darío Achá (Instituto de Ecología, UMSA) y Mauricio Peñarrieta (IIQ, UMSA). → Pedir el artículo y los datos.
- **Rivera et al. 2016**, Environ. Pollut., doi:10.1016/j.envpol.2016.07.013. Peces y caimán, comunidades tacanas, 2007–2008. Solo se leyó el resumen (carnívoros 0,35–1,27 µg/g ww); el texto completo es de pago.
- **Maurice-Bourgoin et al. 2002**, IAHS Publ. 276:161-168 (leído). Agua total del Beni: 19 ng/L en estiaje y 460 ng/L en crecida (1999). Los núcleos de sedimento están río abajo de Rurrenabaque, sin tabla por estación.
- **Maurice-Bourgoin et al. 1999** (Ambio 28:302), **2000** (Sci. Total Environ. 260:73), **1997** (Rev. Bol. Quím. 14:42), **2001** (síntesis IRD fdi:010025628) y **2003** (J. Phys. IV 107:855). Son las fuentes primarias con tablas por estación (Kaká, Tipuani, Mapiri, Coroico; agua, partículas y peces). **El repositorio del IRD (horizon.documentation.ird.fr) estaba en mantenimiento**: reintentar.
- "575/799 ppb en peces del Kaká" (Mongabay 2016): en realidad es un estudio de 1992 en Pando. Descartado.
- Lechler et al. 2000 (repositorio UFC): río Madeira en Brasil, fuera de la cuenca.
- Lagunas de la zona A del Beni (Valdivieso 2025): sedimento de lagunas de inundación (0,064–0,073 µg/g). No es cauce de río; si se usa, va como capa aparte.
- Suelos de la tesis del Kaká (0,04 / 0,08 / 0,04 mg/kg): es suelo agrícola, no sedimento de río.

## Correcciones hechas en el motor (2026-11-25)

1. **Bajo el límite de detección**: si el LD supera el p84 de lo esperado, el dato se ignora; si no, se usa la media truncada (aproximación tobit). Antes se usaba LD/2.
2. **Antigüedad**: peso × 0,5^(años / vida media); vida media de 5 años en agua, 15 en sedimento y 8 en peces.
3. **Anclaje al cauce principal**: si a menos de 500 m más que el tramo más cercano hay un río con cuenca 10 veces mayor, se usa ese. La columna `tramo_id` permite forzar el tramo.
4. **Estación**: columna `estacion_climatica` (seca/húmeda). El agua lleva un efecto estacional ×8 (prior). El mapa da el promedio geométrico, y un dato sin estación conocida lleva incertidumbre extra.
5. **Variabilidad temporal (nugget)**: se ajusta con los datos; antes el modelo daba rangos demasiado estrechos.
6. Los censurados ignorados ya no cuentan para decidir si se ajustan los hiperparámetros.

## Segunda ronda (HAL, acceso abierto; el IRD seguía en mantenimiento)

- **Laffont et al. 2009**, ES&T 43:8985 (ird-00452959). Surubí del Beni en Puerto Salinas (14°15'S 67°30'W), 1.597–10.315 ng/g de peso seco (≈0,42–2,7 mg/kg en peso húmedo, factor 3,78). Queda ~6 km al norte del bbox piloto; la tabla por muestra está en el material suplementario, que HAL no incluye. → Útil para contrastar el supuesto del pescado: muy por encima del fondo de 0,2.
- **Bénéfice et al. 2008, 2009, 2010** y **Luna Monrroy 2006**: mercurio en **cabello** de comunidades del Beni (medianas ≈3,8–4,4 µg/g; ~11% sobre 10 µg/g). → Validación del módulo de salud, no del mapa.

## Contactos para conseguir datos crudos

- Fabiola Valdivieso (IIQ-Ambiental, UMSA): su "base de datos II" del metaanálisis tiene los valores por sitio de todas las fuentes 1995–2024.
- Darío Achá (Instituto de Ecología, UMSA) y WCS Bolivia: peces de Rurrenabaque 2024.
- Paul Van Damme (FAUNAGUA) y Lieven Bervoets (Univ. Amberes): Hg por individuo de Heliyon 2022.
