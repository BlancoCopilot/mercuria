import * as maplibregl from "maplibre-gl";
import type { StyleSpecification } from "maplibre-gl";
import { cellToBoundary } from "h3-js";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import type { Celda } from "./api";

// MapLibre 6 distribuye su worker como módulo aparte: Vite lo empaqueta y le damos la URL.
maplibregl.setWorkerUrl(workerUrl);

// Mapa base vectorial libre (OpenFreeMap, sin clave). Si no carga (sin señal), queda un lienzo
// de papel y los datos de RastroHg se siguen viendo.
const BASE_STYLE = "https://tiles.openfreemap.org/styles/positron";
export const CENTER: [number, number] = [-67.95, -15.15];

const C = {
  paper: "#f7f0e1", paper2: "#efe5d0", paper3: "#e6d9be", water: "#bfe3f5", charcoal: "#23212c",
};

const BLANK: StyleSpecification = {
  version: 8,
  glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": C.paper } }],
};

/** Recolorea el estilo base a la paleta de papel: agua celeste suave, tierra crema, rutas finas. */
function paperize(style: StyleSpecification): StyleSpecification {
  for (const l of style.layers) {
    const id = l.id.toLowerCase();
    if (l.type === "background") l.paint = { ...l.paint, "background-color": C.paper };
    else if (l.type === "fill") {
      const color = id.includes("water") ? C.water
        : id.includes("park") || id.includes("wood") || id.includes("forest") || id.includes("landcover") ? C.paper2
        : id.includes("building") ? C.paper3 : C.paper2;
      l.paint = { ...l.paint, "fill-color": color, "fill-outline-color": color };
    } else if (l.type === "line") {
      const water = id.includes("water") || id.includes("river");
      l.paint = { ...l.paint, "line-color": water ? C.water : id.includes("boundary") ? "rgba(35,33,44,0.35)" : "rgba(35,33,44,0.14)" };
    } else if (l.type === "symbol" && l.paint) {
      l.paint = { ...l.paint, "text-color": "rgba(35,33,44,0.78)", "text-halo-color": C.paper, "text-halo-width": 1.4 };
    }
  }
  return style;
}

export async function loadBaseStyle(): Promise<StyleSpecification> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 6000);
    const r = await fetch(BASE_STYLE, { signal: ctrl.signal });
    clearTimeout(t);
    if (!r.ok) throw new Error(String(r.status));
    return paperize(await r.json());
  } catch {
    return BLANK;
  }
}

export function createMap(container: HTMLElement, style: StyleSpecification, opts: Partial<maplibregl.MapOptions> = {}) {
  const map = new maplibregl.Map({
    container, style, center: CENTER, zoom: 7.6, minZoom: 5, maxZoom: 15,
    attributionControl: false, cooperativeGestures: false, ...opts,
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-left");
  map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-left");
  // los créditos empiezan plegados (botón ⓘ): abiertos tapan medio mapa en el celular
  map.once("load", () => {
    const at = container.querySelector(".maplibregl-ctrl-attrib");
    at?.classList.remove("maplibregl-compact-show");
    at?.removeAttribute("open");
  });
  return map;
}

// ── Capas de RastroHg ─────────────────────────────────────
export const RISK_COLOR = ["match", ["get", "clase"], "alto", "#dd5000", "medio", "#fcbd1c", "#8fbf9a"] as const;

export function cellsToGeoJSON(cells: Celda[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: cells.map((c) => {
      const ring = cellToBoundary(c.h3, true);
      return {
        type: "Feature",
        id: undefined,
        properties: { ...c, orden: c.clase === "alto" ? 2 : c.clase === "medio" ? 1 : 0 },
        geometry: { type: "Polygon", coordinates: [[...ring, ring[0]]] },
      };
    }),
  };
}

/** Peligro relativo de un tramo (mediana / referencia de la matriz) para colorear ríos. */
export const REFERENCIA: Record<string, number> = { agua: 1.0, sedimento: 0.486, pez: 0.5 };

export function centroid(geom: GeoJSON.Geometry): [number, number] | null {
  const pts: number[][] = [];
  const walk = (c: unknown): void => {
    if (Array.isArray(c) && typeof c[0] === "number") pts.push(c as number[]);
    else if (Array.isArray(c)) c.forEach(walk);
  };
  walk((geom as { coordinates: unknown }).coordinates);
  if (!pts.length) return null;
  const s = pts.reduce((a, p) => [a[0] + p[0], a[1] + p[1]], [0, 0]);
  return [s[0] / pts.length, s[1] / pts.length];
}

// ── Centros de salud ──────────────────────────────────────
// Íconos dibujados aquí (sin imágenes externas): cruz pino sobre blanco = centro/puesto/consultorio;
// cruz blanca sobre pino, más grande = hospital. Forma, no color de riesgo: el ember queda para "riesgo alto".
function iconoSalud(lado: number, hospital: boolean): ImageData {
  const r = 2, n = lado * r;
  const c = document.createElement("canvas");
  c.width = c.height = n;
  const g = c.getContext("2d")!;
  const radio = n * 0.2;
  g.beginPath();
  g.roundRect(r, r, n - 2 * r, n - 2 * r, radio);
  g.fillStyle = hospital ? "#006434" : "#ffffff";
  g.fill();
  g.lineWidth = 2 * r;
  g.strokeStyle = hospital ? "#ffffff" : "#006434";
  g.stroke();
  const brazo = n * 0.17, largo = n * 0.56, m = n / 2;
  g.fillStyle = hospital ? "#ffffff" : "#006434";
  g.fillRect(m - brazo / 2, m - largo / 2, brazo, largo);
  g.fillRect(m - largo / 2, m - brazo / 2, largo, brazo);
  return g.getImageData(0, 0, n, n);
}

export function addIconosSalud(map: maplibregl.Map) {
  if (!map.hasImage("salud")) map.addImage("salud", iconoSalud(22, false), { pixelRatio: 2 });
  if (!map.hasImage("salud-h")) map.addImage("salud-h", iconoSalud(26, true), { pixelRatio: 2 });
}

export interface SaludProps { id: number; name: string; tipo: string; phone: string | null; osm_id: string | null; sintetico: boolean }
