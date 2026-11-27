import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import * as maplibregl from "maplibre-gl";
import type { MapGeoJSONFeature } from "maplibre-gl";
import { cellToLatLng } from "h3-js";
import { api, type Celda, type CeldaDetalle, type Comunidad, type SitioProps } from "../lib/api";
import { addIconosSalud, cellsToGeoJSON, centroid, createMap, loadBaseStyle, REFERENCIA, RISK_COLOR, type SaludProps } from "../lib/map";
import { useMedia } from "../lib/hooks";
import { comoLlegar, confianzaTexto, fecha, int, LEGAL_TEXTO, MATRIZ, num, pct, rango } from "../lib/format";
import { CommunitySearch } from "../components/CommunitySearch";
import { ErrorNote, RiskChip, Skeleton, SyntheticTag } from "../components/ui";
import { useUbicacion, type Posicion, type Zona } from "../lib/location";

type Capa = "riesgo" | "agua" | "sedimento" | "pez";
type Seleccion =
  | { tipo: "celda"; h3: string }
  | { tipo: "sitio"; props: SitioProps }
  | { tipo: "yo" }
  | { tipo: "salud"; props: SaludProps; lat: number; lon: number }
  | { tipo: "tramo"; props: { hyriv_id: number; p05: number; p50: number; p95: number; n_cercanos: number; presion_kg: number }; matriz: string }
  | null;

const CAPAS: { id: Capa; label: string }[] = [
  { id: "riesgo", label: "Riesgo por zona" },
  { id: "pez", label: "Mercurio en peces" },
  { id: "agua", label: "Mercurio en agua" },
  { id: "sedimento", label: "Mercurio en sedimento" },
];

type Hoja = "baja" | "media" | "alta";
const NIVELES_HOJA: Hoja[] = ["baja", "media", "alta"];

/** `app`: versión de la app de celular: menús desplegables arriba y hoja inferior de 3 alturas, para ver el mapa. */
export default function MapPage({ app = false }: { app?: boolean } = {}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [capa, setCapa] = useState<Capa>("riesgo");
  const [sitios, setSitios] = useState(true);
  const [salud, setSalud] = useState(true);
  const saludRef = useRef<Centro[]>([]);
  const [sel, setSel] = useState<Seleccion>(null);
  const [comunidad, setComunidad] = useState<Comunidad | null>(null);
  const [stats, setStats] = useState<{ alto: number; medio: number; palidas: number; sitios: number; enAp: number } | null>(null);
  // Hoja inferior: en la web, abierta o cerrada; en la app, baja (una línea), media (40 %) o alta.
  const [hoja, setHoja] = useState<Hoja>("baja");
  const sheetOpen = hoja !== "baja";
  const setSheetOpen = useCallback((v: boolean | ((o: boolean) => boolean)) => setHoja((h) => {
    const abrir = typeof v === "function" ? v(h !== "baja") : v;
    return abrir ? (h === "baja" ? (app ? "media" : "alta") : h) : "baja";
  }), [app]);
  const [menu, setMenu] = useState<null | "buscar" | "capas">(null);
  const arrastre = useRef<number | null>(null);
  const moverHoja = (d: 1 | -1) => setHoja((h) => NIVELES_HOJA[Math.max(0, Math.min(2, NIVELES_HOJA.indexOf(h) + d))]);
  const mobile = useMedia("(max-width: 900px)");
  const riversLoaded = useRef(new Set<string>());
  const nav = useNavigate();
  const [params] = useSearchParams();
  const celdaParam = params.get("celda");
  const yoParam = params.get("yo") === "1";
  const { pos, zona, ubicar, estado } = useUbicacion();
  const cellsRef = useRef<Celda[]>([]);
  const meMarker = useRef<maplibregl.Marker | null>(null);
  const [irAPos, setIrAPos] = useState(false);

  // ── Mapa y capas ──────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const style = await loadBaseStyle();
      if (cancelled || !el.current) return;
      const m = createMap(el.current, style);
      map.current = m;
      m.on("load", async () => {
        try {
          const [cells, sites, centros] = await Promise.all([
            api<{ celdas: Celda[] }>("/v1/map/cells?since=0", { auth: false }),
            api<GeoJSON.FeatureCollection>("/v1/map/sites", { auth: false }),
            // si falla, el mapa sigue sin la capa de salud
            api<GeoJSON.FeatureCollection<GeoJSON.Point, SaludProps>>("/v1/map/salud", { auth: false })
              .catch(() => ({ type: "FeatureCollection", features: [] }) as GeoJSON.FeatureCollection<GeoJSON.Point, SaludProps>),
          ]);
          if (cancelled) return;
          const fc = cellsToGeoJSON(cells.celdas);
          m.addSource("celdas", { type: "geojson", data: fc });
          m.addLayer({
            id: "celdas-fill", type: "fill", source: "celdas",
            layout: { "fill-sort-key": ["get", "orden"] },
            paint: {
              "fill-color": RISK_COLOR as unknown as maplibregl.ExpressionSpecification,
              "fill-opacity": ["case", ["==", ["get", "clase"], "bajo"], 0.1, ["get", "palida"], 0.22, 0.62],
            },
          });
          m.addLayer({
            id: "celdas-line", type: "line", source: "celdas",
            filter: ["!=", ["get", "clase"], "bajo"],
            paint: { "line-color": "#23212c", "line-opacity": ["case", ["get", "palida"], 0.18, 0.28], "line-width": 0.6 },
          });
          m.addLayer({
            id: "celda-sel", type: "line", source: "celdas", filter: ["==", ["get", "h3"], ""],
            paint: { "line-color": "#23212c", "line-width": 2.5 },
          });

          const pts: GeoJSON.Feature[] = sites.features.flatMap((f) => {
            const c = centroid(f.geometry);
            return c ? [{ type: "Feature", properties: f.properties, geometry: { type: "Point", coordinates: c } }] : [];
          });
          m.addSource("sitios", { type: "geojson", data: sites });
          m.addSource("sitios-pt", { type: "geojson", data: { type: "FeatureCollection", features: pts } });
          m.addLayer({ id: "sitios-fill", type: "fill", source: "sitios", minzoom: 10, paint: { "fill-color": "#23212c", "fill-opacity": 0.28 } });
          m.addLayer({ id: "sitios-line", type: "line", source: "sitios", minzoom: 10, paint: { "line-color": "#23212c", "line-width": 1 } });
          m.addLayer({
            id: "sitios-pt", type: "circle", source: "sitios-pt", maxzoom: 10.5,
            // Forma, no color: lleno = sitio; hueco = sitio en área protegida (el ember queda para "riesgo alto")
            paint: {
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 1.8, 8, 2.6, 10, 4.5],
              "circle-color": ["case", ["==", ["get", "legal_status"], "en_area_protegida"], "#f7f0e1", "#23212c"],
              "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 6, 0.8, 10, 1.6],
              "circle-stroke-color": "#23212c",
            },
          });

          // Centros de salud: encima de todo, siempre visibles (aunque se encimen)
          addIconosSalud(m);
          m.addSource("salud", { type: "geojson", data: centros });
          m.addLayer({
            id: "salud", type: "symbol", source: "salud",
            layout: {
              "icon-image": ["case", ["==", ["get", "tipo"], "Hospital"], "salud-h", "salud"],
              "icon-size": ["interpolate", ["linear"], ["zoom"], 6, 0.75, 9, 0.9, 12, 1.1],
              "icon-allow-overlap": true, "icon-ignore-placement": true,
              "symbol-sort-key": ["case", ["==", ["get", "tipo"], "Hospital"], 1, 0],
            },
          });
          saludRef.current = centros.features.map((f) => ({ ...f.properties, lon: f.geometry.coordinates[0], lat: f.geometry.coordinates[1] }));

          // Encuadre: las zonas con riesgo (o todas), dejando libres la barra y el panel
          const foco = fc.features.filter((f) => f.properties?.clase !== "bajo");
          const b = new maplibregl.LngLatBounds();
          (foco.length ? foco : fc.features).forEach((f) => (f.geometry as GeoJSON.Polygon).coordinates[0].forEach((c) => b.extend(c as [number, number])));
          if (!b.isEmpty()) {
            const narrow = window.matchMedia("(max-width: 900px)").matches;
            m.fitBounds(b, { padding: narrow ? { top: 110, bottom: 150, left: 20, right: 20 } : { top: 150, bottom: 40, left: 60, right: 470 }, duration: 0, maxZoom: 10 });
          }

          cellsRef.current = cells.celdas;
          const props = cells.celdas;
          const enAp = sites.features.filter((f) => f.properties?.legal_status === "en_area_protegida").length;
          setStats({
            alto: props.filter((c) => c.clase === "alto").length,
            medio: props.filter((c) => c.clase === "medio").length,
            palidas: props.filter((c) => c.palida && c.clase !== "bajo").length,
            sitios: sites.features.length, enAp,
          });
          setReady(true);
        } catch (e) {
          setError((e as Error).message);
        }
      });

      const clickable = ["salud", "sitios-pt", "sitios-fill", "rios", "celdas-fill"];
      // los centros de salud se tocan con margen (íconos chicos, dedos grandes)
      const tocar = (p: maplibregl.Point) => {
        const pad = 10;
        const salud = m.getLayer("salud") && m.getLayoutProperty("salud", "visibility") !== "none"
          ? m.queryRenderedFeatures([[p.x - pad, p.y - pad], [p.x + pad, p.y + pad]], { layers: ["salud"] }) : [];
        return salud.length ? salud : m.queryRenderedFeatures(p, { layers: clickable.filter((l) => m.getLayer(l)) });
      };
      m.on("click", (e) => {
        setMenu(null);
        const hits = tocar(e.point);
        const f: MapGeoJSONFeature | undefined = hits[0];
        if (!f) { setSel(null); return; }
        if (f.layer.id === "salud") {
          const [lon, lat] = (f.geometry as GeoJSON.Point).coordinates;
          setSel({ tipo: "salud", props: f.properties as SaludProps, lat, lon });
        } else if (f.layer.id.startsWith("sitios")) setSel({ tipo: "sitio", props: f.properties as SitioProps });
        else if (f.layer.id === "rios") setSel({ tipo: "tramo", props: f.properties as never, matriz: String(m.getLayer("rios")?.metadata ?? "") });
        else setSel({ tipo: "celda", h3: String(f.properties.h3) });
        setSheetOpen(true);
      });
      m.on("mousemove", (e) => {
        const hits = tocar(e.point);
        m.getCanvas().style.cursor = hits.length ? "pointer" : "";
      });
    })();
    return () => { cancelled = true; map.current?.remove(); map.current = null; };
  }, []);

  // Capa de ríos por matriz (se descarga solo cuando se pide; ~600 KB por matriz)
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const showCells = capa === "riesgo";
    for (const l of ["celdas-fill", "celdas-line"]) m.setLayoutProperty(l, "visibility", showCells ? "visible" : "none");
    if (m.getLayer("rios")) m.removeLayer("rios");
    if (showCells) return;
    const src = `rios-${capa}`;
    const add = () => {
      if (m.getLayer("rios")) m.removeLayer("rios");
      const ref = REFERENCIA[capa];
      m.addLayer({
        id: "rios", type: "line", source: src, metadata: capa,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": ["interpolate", ["linear"], ["ln", ["max", 0.0001, ["/", ["get", "p50"], ref]]],
            Math.log(0.02), "#9fd0e6", Math.log(0.25), "#8fbf9a", Math.log(0.7), "#fcbd1c", Math.log(2), "#dd5000"],
          "line-width": ["interpolate", ["linear"], ["zoom"], 6, ["*", 0.25, ["get", "ord_stra"]], 11, ["*", 0.9, ["get", "ord_stra"]]],
          "line-opacity": ["case", [">", ["/", ["get", "p95"], ["max", ["get", "p05"], 0.000001]], 60], 0.45, 0.95],
        },
      }, m.getLayer("sitios-fill") ? "sitios-fill" : undefined);
    };
    if (riversLoaded.current.has(src)) { add(); return; }
    api<GeoJSON.FeatureCollection>(`/v1/map/rivers?matrix=${capa}&simplify_m=80`, { auth: false })
      .then((fc) => {
        if (!m.getSource(src)) m.addSource(src, { type: "geojson", data: fc });
        riversLoaded.current.add(src);
        add();
      })
      .catch((e) => setError((e as Error).message));
  }, [capa, ready]);

  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    for (const l of ["sitios-fill", "sitios-line", "sitios-pt"]) m.setLayoutProperty(l, "visibility", sitios ? "visible" : "none");
  }, [sitios, ready]);

  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !m.getLayer("salud")) return;
    m.setLayoutProperty("salud", "visibility", salud ? "visible" : "none");
  }, [salud, ready]);

  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    m.setFilter("celda-sel", ["==", ["get", "h3"], sel?.tipo === "celda" ? sel.h3 : ""]);
  }, [sel, ready]);

  // /?celda=<h3>: abre esa zona (viene del aviso de ubicación)
  useEffect(() => {
    if (!ready || !celdaParam) return;
    try {
      const [lat, lng] = cellToLatLng(celdaParam);
      map.current?.flyTo({ center: [lng, lat], zoom: 11, duration: 900 });
      setCapa("riesgo");
      setSel({ tipo: "celda", h3: celdaParam });
      setSheetOpen(true);
    } catch { /* celda inválida: se ignora */ }
  }, [ready, celdaParam]);

  const irAComunidad = useCallback((c: Comunidad) => {
    setComunidad(c);
    const h = c.h3 || null;
    if (!h) return;
    const [lat, lng] = cellToLatLng(h);
    map.current?.flyTo({ center: [lng, lat], zoom: 11, duration: 900 });
    setCapa("riesgo");
    setSel({ tipo: "celda", h3: h });
    setSheetOpen(true);
  }, []);

  // "Estás aquí": punto en la posición exacta (solo en este navegador; no se envía a ningún lado)
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !pos) return;
    if (!meMarker.current) {
      const el = document.createElement("div");
      el.className = "me-marker";
      el.setAttribute("role", "img");
      el.setAttribute("aria-label", "Tu ubicación");
      el.innerHTML = '<span class="me-pulse"></span><span class="me-dot"></span>';
      el.addEventListener("click", (e) => { e.stopPropagation(); setSel({ tipo: "yo" }); setSheetOpen(true); });
      meMarker.current = new maplibregl.Marker({ element: el }).setLngLat([pos.lon, pos.lat]).addTo(m);
    } else meMarker.current.setLngLat([pos.lon, pos.lat]);
  }, [pos, ready]);
  useEffect(() => () => { meMarker.current?.remove(); meMarker.current = null; }, []);

  const enfocarYo = useCallback(() => {
    if (!pos) return;
    const conDatos = zona && zona.nivel !== "sin_datos";
    map.current?.flyTo({ center: [pos.lon, pos.lat], zoom: conDatos ? 11 : 9, duration: 900 });
    setCapa("riesgo");
    setSel({ tipo: "yo" });
    setSheetOpen(true);
  }, [pos, zona]);

  // /?yo=1 (desde el aviso) o el botón "Mi ubicación": centra en la persona; si aún no hay posición, la pide.
  useEffect(() => { if (ready && yoParam) setIrAPos(true); }, [ready, yoParam]);
  useEffect(() => {
    if (!irAPos || !ready) return;
    if (pos && zona) { enfocarYo(); setIrAPos(false); }
    else if (!pos && estado !== "ubicando") ubicar();
  }, [irAPos, ready, pos, zona, estado, ubicar, enfocarYo]);

  const usarUbicacion = () => setIrAPos(true);

  const irACelda = (h: string) => {
    const [lat, lng] = cellToLatLng(h);
    map.current?.flyTo({ center: [lng, lat], zoom: 10.5, duration: 900 });
    setSel({ tipo: "celda", h3: h });
  };

  const irACentro = (c: Centro) => {
    map.current?.flyTo({ center: [c.lon, c.lat], zoom: Math.max(map.current.getZoom(), 12), duration: 900 });
    setSalud(true);
    setSel({ tipo: "salud", props: c, lat: c.lat, lon: c.lon });
  };

  const panel = sel?.tipo === "yo" ? (
    <YoInfo pos={pos} zona={zona} celdas={cellsRef.current} centros={saludRef.current} onClose={() => setSel(null)} onCelda={irACelda} onCentro={irACentro} />
  ) : sel?.tipo === "salud" ? (
    <SaludInfo c={sel.props} lat={sel.lat} lon={sel.lon} pos={pos} onClose={() => setSel(null)} />
  ) : (
    <PanelContent
      sel={sel} capa={capa} stats={stats} ready={ready} error={error}
      onClose={() => setSel(null)} onComunidad={(id) => nav(`/comunidad/${id}`)}
    />
  );

  return (
    <div className="map-page" data-fab-space="true" data-hoja={app ? hoja : undefined}>
      <div ref={el} className="map-canvas" role="region" aria-label="Mapa de riesgo por mercurio"
        onPointerDown={app ? () => setMenu(null) : undefined} />

      {!app && <form className="marigold-bar map-bar" onSubmit={(e) => { e.preventDefault(); if (comunidad) nav(`/comunidad/${comunidad.id}`); }}>
        <div className="field" style={{ flex: "2 1 0" }}>
          <label className="label">Mi comunidad</label>
          <CommunitySearch onPick={irAComunidad} placeholder={mobile ? "Tu comunidad" : undefined} />
        </div>
        {!mobile && (
          <>
            <div className="field">
              <label className="label" htmlFor="capa">Ver en el mapa</label>
              <select id="capa" className="select" value={capa} onChange={(e) => setCapa(e.target.value as Capa)}>
                {CAPAS.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
              </select>
            </div>
            <div className="field" style={{ flex: "0 0 auto" }}>
              <span className="label">Minería</span>
              <label className="row" style={{ gap: 8, minHeight: 40, cursor: "pointer" }}>
                <input type="checkbox" checked={sitios} onChange={(e) => setSitios(e.target.checked)} style={{ width: 18, height: 18, accentColor: "#23212c" }} />
                <span>Sitios</span>
              </label>
            </div>
            <div className="field" style={{ flex: "0 0 auto" }}>
              <span className="label">Salud</span>
              <label className="row" style={{ gap: 8, minHeight: 40, cursor: "pointer" }}>
                <input type="checkbox" checked={salud} onChange={(e) => setSalud(e.target.checked)} style={{ width: 18, height: 18, accentColor: "#006434" }} />
                <span>Centros</span>
              </label>
            </div>
          </>
        )}
        <button className="btn" type="submit" disabled={!comunidad}>Ver ficha</button>
      </form>}

      {app ? (
        <>
          <div className="m-mapa-top">
            <button className="m-mapa-btn" aria-expanded={menu === "buscar"} onClick={() => setMenu((m) => (m === "buscar" ? null : "buscar"))}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6" /><path d="M15.4 15.4l4.6 4.6" /></svg>
              <span>{comunidad ? comunidad.name : "Buscar comunidad"}</span>
            </button>
            <button className="m-mapa-btn" aria-expanded={menu === "capas"} onClick={() => setMenu((m) => (m === "capas" ? null : "capas"))}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinejoin="round" aria-hidden="true"><path d="M12 3.5l8.5 4.5-8.5 4.5L3.5 8z" /><path d="M3.5 12.2l8.5 4.5 8.5-4.5M3.5 16.2l8.5 4.5 8.5-4.5" /></svg>
              <span>Capas</span>
            </button>
          </div>
          {menu === "buscar" && (
            <div className="m-mapa-menu" role="dialog" aria-label="Buscar comunidad">
              <CommunitySearch onPick={(c) => { irAComunidad(c); setMenu(null); }} placeholder="Escribe el nombre de tu comunidad" autoFocus />
            </div>
          )}
          {menu === "capas" && (
            <div className="m-mapa-menu" role="dialog" aria-label="Capas del mapa">
              <p className="m-mapa-menu-titulo">Ver en el mapa</p>
              {CAPAS.map((c) => (
                <label key={c.id} className="m-opcion">
                  <input type="radio" name="m-capa" checked={capa === c.id} onChange={() => setCapa(c.id)} />
                  <span>{c.label}</span>
                </label>
              ))}
              <p className="m-mapa-menu-titulo">Mostrar también</p>
              <label className="m-opcion"><input type="checkbox" checked={sitios} onChange={(e) => setSitios(e.target.checked)} /><span>Sitios mineros</span></label>
              <label className="m-opcion"><input type="checkbox" checked={salud} onChange={(e) => setSalud(e.target.checked)} /><span>Centros de salud</span></label>
              <button className="btn btn-block m-mapa-listo" onClick={() => setMenu(null)}>Listo</button>
            </div>
          )}
          {hoja !== "alta" && (
            <button className="map-locate-fab" onClick={usarUbicacion} disabled={estado === "ubicando"} aria-label={estado === "ubicando" ? "Ubicando…" : "Ir a mi ubicación"}>
              <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round">
                <circle cx="12" cy="12" r="3.2" fill="currentColor" /><circle cx="12" cy="12" r="7.2" /><path d="M12 2.5v2.4M12 19.1v2.4M2.5 12h2.4M19.1 12h2.4" />
              </svg>
            </button>
          )}
          <section className="sheet" data-hoja={hoja} aria-label="Información del mapa">
            <button
              className="sheet-handle m-hoja-manija"
              aria-label={hoja === "baja" ? "Subir panel" : "Bajar panel"}
              onPointerDown={(e) => { arrastre.current = e.clientY; e.currentTarget.setPointerCapture(e.pointerId); }}
              onPointerUp={(e) => {
                const y0 = arrastre.current; arrastre.current = null;
                if (y0 === null) return;
                const dy = e.clientY - y0;
                if (dy < -30) moverHoja(1); else if (dy > 30) moverHoja(-1);
                else setHoja((h) => (h === "baja" ? "media" : "baja"));
              }}
              onClick={(e) => { if (e.detail === 0) setHoja((h) => (h === "baja" ? "media" : "baja")); }}   // teclado
              onKeyDown={(e) => { if (e.key === "ArrowUp") moverHoja(1); if (e.key === "ArrowDown") moverHoja(-1); }}
            >
              <span aria-hidden="true" className="grip" />
              <span className="m-hoja-titulo">
                {sel?.tipo === "celda" ? "Zona seleccionada" : sel?.tipo === "sitio" ? "Sitio minero" : sel?.tipo === "salud" ? "Centro de salud"
                  : sel?.tipo === "tramo" ? "Río" : sel?.tipo === "yo" ? "Estás aquí" : "Leyenda y resumen"}
                <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" data-up={hoja !== "alta"}><path d="M4 10l4-4 4 4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
              </span>
            </button>
            <div className="sheet-body">{panel}</div>
          </section>
        </>
      ) : mobile ? (
        <>
        {!sheetOpen && (
          <button className="map-locate-fab" onClick={usarUbicacion} disabled={estado === "ubicando"} aria-label={estado === "ubicando" ? "Ubicando…" : "Ir a mi ubicación"}>
            <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round">
              <circle cx="12" cy="12" r="3.2" fill="currentColor" /><circle cx="12" cy="12" r="7.2" /><path d="M12 2.5v2.4M12 19.1v2.4M2.5 12h2.4M19.1 12h2.4" />
            </svg>
          </button>
        )}
        <section className="sheet" data-open={sheetOpen} aria-label="Información del mapa">
          <button className="sheet-handle" onClick={() => setSheetOpen((o) => !o)} aria-expanded={sheetOpen}>
            <span aria-hidden="true" className="grip" />
            <span className="visually-hidden">{sheetOpen ? "Bajar panel" : "Subir panel"}</span>
          </button>
          <div className="row" style={{ gap: 8, padding: "0 20px 12px", overflowX: "auto", flexWrap: "nowrap" }}>
            {CAPAS.map((c) => (
              <button key={c.id} className="btn btn-pill" aria-pressed={capa === c.id} onClick={() => setCapa(c.id)} style={{ whiteSpace: "nowrap" }}>
                {c.label.replace("Mercurio en ", "")}
              </button>
            ))}
            <button className="btn btn-pill" aria-pressed={sitios} onClick={() => setSitios((s) => !s)}>Sitios</button>
            <button className="btn btn-pill" aria-pressed={salud} onClick={() => setSalud((v) => !v)} style={{ whiteSpace: "nowrap" }}>Centros de salud</button>
          </div>
          <div className="sheet-body">{panel}</div>
        </section>
        </>
      ) : (
        <>
          <aside className="map-panel" aria-label="Información del mapa">{panel}</aside>
          <button className="btn btn-pill map-locate" onClick={usarUbicacion} disabled={estado === "ubicando"}>
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="3" fill="currentColor" /><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" strokeWidth="1.4" /></svg>
            {estado === "ubicando" ? "Ubicando…" : "Mi ubicación"}
          </button>
        </>
      )}
    </div>
  );
}

// ── Contenido del panel ───────────────────────────────────
// ── Mi ubicación ──────────────────────────────────────────
function distKm(a: { lat: number; lon: number }, b: { lat: number; lon: number }) {
  const R = 6371, r = Math.PI / 180;
  const dLat = (b.lat - a.lat) * r, dLon = (b.lon - a.lon) * r;
  const x = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
}

type Centro = SaludProps & { lat: number; lon: number };

function YoInfo({ pos, zona, celdas, centros, onClose, onCelda, onCentro }: {
  pos: Posicion | null; zona: Zona | null; celdas: Celda[]; centros: Centro[];
  onClose: () => void; onCelda: (h3: string) => void; onCentro: (c: Centro) => void;
}) {
  if (!pos || !zona) return <div className="stack"><CloseBtn onClose={onClose} /><Skeleton lines={3} /></div>;
  const conDatos = zona.nivel !== "sin_datos";
  let cercana: { h3: string; km: number; clase: string } | null = null;
  if (!conDatos) {
    for (const c of celdas) {
      const [lat, lon] = cellToLatLng(c.h3);
      const km = distKm(pos, { lat, lon });
      if (!cercana || km < cercana.km) cercana = { h3: c.h3, km, clase: c.clase };
    }
  }
  return (
    <div className="stack">
      <CloseBtn onClose={onClose} />
      <span className="meta">Estás aquí</span>
      {conDatos ? (
        <>
          <RiskChip nivel={zona.nivel} confianza={zona.confianza} palida={zona.palida} />
          <h3>Tu zona{zona.comunidad ? `, cerca de ${zona.comunidad.name}` : ""}</h3>
          {zona.cercaAlto && <p className="muted">Hay una zona de riesgo alto a menos de 3 km.</p>}
          <button className="btn" onClick={() => onCelda(zona.h3)}>Ver el detalle de mi zona</button>
        </>
      ) : (
        <>
          <h3>Sin estimación aquí</h3>
          <p className="muted">
            Tu ubicación está fuera de la cuenca piloto o lejos de los ríos que modelamos, así que no podemos decir si hay riesgo.
          </p>
          {cercana && (
            <>
              <p>La zona estimada más cercana está a <strong className="num" style={{ fontWeight: 500 }}>{num(cercana.km)} km</strong>.</p>
              <button className="btn" onClick={() => onCelda(cercana!.h3)}>Ir a la zona más cercana</button>
            </>
          )}
        </>
      )}
      <CentroCercano pos={pos} centros={centros} onCentro={onCentro} />
      <p className="caption muted">Tu posición exacta solo se usa en este teléfono para dibujar el punto; no se envía a ningún lado. Precisión ≈ {num(pos.precision)} m.</p>
    </div>
  );
}

function CentroCercano({ pos, centros, onCentro }: { pos: Posicion; centros: Centro[]; onCentro: (c: Centro) => void }) {
  if (!centros.length) return null;
  let mejor: { c: Centro; km: number } | null = null;
  for (const c of centros) {
    const km = distKm(pos, c);
    if (!mejor || km < mejor.km) mejor = { c, km };
  }
  if (!mejor) return null;
  return (
    <div className="salud-cerca">
      <IconoSalud hospital={mejor.c.tipo === "Hospital"} />
      <div className="stack" style={{ gap: 2, minWidth: 0 }}>
        <span className="small muted">Centro de salud más cercano</span>
        <span style={{ fontWeight: 500 }}>{mejor.c.name}</span>
        <span className="small muted num">{mejor.km < 1 ? "A menos de 1 km" : `A ${num(mejor.km)} km en línea recta`}</span>
      </div>
      <button className="btn btn-pill" onClick={() => onCentro(mejor!.c)}>Ver</button>
    </div>
  );
}

function IconoSalud({ hospital = false, size = 22 }: { hospital?: boolean; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 22 22" aria-hidden="true" style={{ flex: "none" }}>
      <rect x="1" y="1" width="20" height="20" rx="4.4" fill={hospital ? "#006434" : "#fff"} stroke={hospital ? "#fff" : "#006434"} strokeWidth="2" />
      {hospital && <rect x="0.5" y="0.5" width="21" height="21" rx="4.8" fill="none" stroke="#006434" strokeWidth="1" />}
      <path d="M9.1 4.8h3.8v4.3h4.3v3.8h-4.3v4.3H9.1v-4.3H4.8V9.1h4.3z" fill={hospital ? "#fff" : "#006434"} />
    </svg>
  );
}

function SaludInfo({ c, lat, lon, pos, onClose }: { c: SaludProps; lat: number; lon: number; pos: Posicion | null; onClose: () => void }) {
  const km = pos ? distKm(pos, { lat, lon }) : null;
  const tel = c.phone?.split(/[;,]/)[0].trim() || null;
  return (
    <div className="stack">
      <CloseBtn onClose={onClose} />
      <div className="row" style={{ gap: 10 }}>
        <IconoSalud hospital={c.tipo === "Hospital"} size={26} />
        <span className="tag">{c.tipo}</span>
        <SyntheticTag show={c.sintetico} />
      </div>
      <h3>{c.name}</h3>
      {km !== null && <p className="muted num">{km < 1 ? "A menos de 1 km de ti" : `A ${num(km)} km de ti en línea recta`}</p>}
      <div className="stack" style={{ gap: 10 }}>
        {tel && (
          <a className="btn btn-block" href={`tel:${tel.replace(/[^\d+]/g, "")}`}>
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6.62 10.79a15.05 15.05 0 0 0 6.59 6.59l2.2-2.2a1 1 0 0 1 1.02-.24c1.12.37 2.33.57 3.57.57a1 1 0 0 1 1 1V20a1 1 0 0 1-1 1C10.61 21 3 13.39 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.57a1 1 0 0 1-.25 1.02l-2.2 2.2z" /></svg>
            Llamar {tel}
          </a>
        )}
        <a className="btn btn-pill btn-block" href={comoLlegar(lat, lon)} target="_blank" rel="noopener noreferrer">Cómo llegar ↗</a>
      </div>
      <p className="small">
        Si alguien tiene síntomas de intoxicación por mercurio (temblores, hormigueo, dolor de cabeza fuerte, problemas para ver o caminar):
        que se aleje de la fuente y acuda a este centro. No provoques el vómito.
      </p>
      <p className="caption muted">
        Datos de OpenStreetMap{c.osm_id ? ` (${c.osm_id})` : ""}: pueden faltar centros o haber cambiado el horario o el teléfono.
        {!tel && " No tenemos su teléfono."}
      </p>
    </div>
  );
}

function PanelContent({ sel, capa, stats, ready, error, onClose, onComunidad }: {
  sel: Seleccion; capa: Capa; stats: { alto: number; medio: number; palidas: number; sitios: number; enAp: number } | null;
  ready: boolean; error: string | null; onClose: () => void; onComunidad: (id: number) => void;
}) {
  if (error) return <ErrorNote error={error} />;
  if (sel?.tipo === "celda") return <CeldaInfo h3={sel.h3} onClose={onClose} onComunidad={onComunidad} />;
  if (sel?.tipo === "sitio") return <SitioInfo p={sel.props} onClose={onClose} />;
  if (sel?.tipo === "tramo") return <TramoInfo p={sel.props} matriz={sel.matriz} onClose={onClose} />;
  return (
    <div className="stack">
      <div className="stack" style={{ gap: 8 }}>
        <span className="meta">Cuenca piloto · Beni alto</span>
        <h2>Dónde hay mercurio y qué tan seguros estamos</h2>
      </div>
      {!ready ? <Skeleton lines={4} /> : stats && (
        <p className="muted">
          <strong className="num" style={{ color: "var(--charcoal)", fontWeight: 500 }}>{int(stats.alto)}</strong> zonas con riesgo alto y{" "}
          <strong className="num" style={{ color: "var(--charcoal)", fontWeight: 500 }}>{int(stats.medio)}</strong> con riesgo medio.{" "}
          <strong className="num" style={{ color: "var(--charcoal)", fontWeight: 500 }}>{int(stats.sitios)}</strong> sitios mineros detectados por satélite,{" "}
          {int(stats.enAp)} dentro de áreas protegidas.
        </p>
      )}
      <Legend capa={capa} />
      <p className="small muted">Toca una zona, un río, un sitio o un centro de salud para ver el detalle. Busca tu comunidad arriba para ver su ficha.</p>
    </div>
  );
}

function Legend({ capa }: { capa: Capa }) {
  if (capa === "riesgo") {
    return (
      <div className="legend" aria-label="Leyenda">
        <div className="legend-row"><span className="sw" style={{ background: "var(--risk-alto)" }} />Riesgo alto</div>
        <div className="legend-row"><span className="sw" style={{ background: "var(--risk-medio)" }} />Riesgo medio</div>
        <div className="legend-row"><span className="sw" style={{ background: "var(--risk-bajo)", opacity: 0.6 }} />Riesgo bajo</div>
        <div className="legend-row"><span className="sw sw-pale" />Color pálido: no sabemos bien, faltan muestras</div>
        <div className="legend-row"><span className="sw sw-dot" />Sitio minero · <span className="sw sw-dot sw-ap" /> en área protegida</div>
        <LeyendaSalud />
      </div>
    );
  }
  const m = MATRIZ[capa];
  return (
    <div className="legend" aria-label="Leyenda">
      <div className="legend-ramp" aria-hidden="true" />
      <div className="spread small muted"><span>Cerca del fondo natural</span><span>Sobre la referencia</span></div>
      <p className="small muted">
        {m.nombre}: mediana estimada por tramo, en {m.unidad}. Los tramos tenues tienen un rango muy amplio: no sabemos bien.
        {capa === "pez" && " Valor de un pez carnívoro de referencia (surubí, dorado)."}
      </p>
      <LeyendaSalud />
    </div>
  );
}

function LeyendaSalud() {
  return (
    <div className="legend-row"><IconoSalud size={16} />Centro de salud · <IconoSalud hospital size={16} /> hospital</div>
  );
}

function CloseBtn({ onClose }: { onClose: () => void }) {
  return <button className="btn-quiet btn" style={{ justifySelf: "start", paddingLeft: 8 }} onClick={onClose} aria-label="Volver a la leyenda">← Leyenda</button>;
}

function CeldaInfo({ h3, onClose, onComunidad }: { h3: string; onClose: () => void; onComunidad: (id: number) => void }) {
  const [d, setD] = useState<CeldaDetalle | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setD(null); setErr(null);
    api<CeldaDetalle>(`/v1/map/cells/${h3}`, { auth: false }).then(setD).catch((e) => setErr(e.status === 404 ? "sin" : e.message));
  }, [h3]);
  if (err === "sin") return (
    <div className="stack"><CloseBtn onClose={onClose} /><h3>Zona sin estimación</h3><p className="muted">Aquí no hay ríos ni poblados en la red del modelo.</p></div>
  );
  if (err) return <ErrorNote error={err} />;
  if (!d) return <Skeleton lines={5} />;
  const comps = [
    { k: "Peligro", v: d.hazard, help: "cuánto mercurio estimamos en ríos y peces cercanos" },
    { k: "Exposición", v: d.exposure, help: "gente, tomas de agua y zonas de pesca" },
    { k: "Vulnerabilidad", v: d.vulnerability, help: "niños, mujeres en edad fértil y consumo de pescado" },
  ];
  return (
    <div className="stack">
      <CloseBtn onClose={onClose} />
      <div className="stack" style={{ gap: 10 }}>
        <RiskChip nivel={d.risk_class} palida={d.palida} />
        <h3>{d.comunidades.length ? d.comunidades.map((c) => c.name).join(", ") : "Zona sin poblados registrados"}</h3>
        <p className="small muted">
          Confianza {pct(d.confidence)}: {confianzaTexto(d.confidence)}. {d.palida && "Una muestra de laboratorio aquí cambiaría mucho lo que sabemos."}
        </p>
      </div>
      {d.comunidades.length > 0 && (
        <div className="row">
          {d.comunidades.map((c) => (
            <button key={c.id} className="btn" onClick={() => onComunidad(c.id)}>Ficha de {c.name}</button>
          ))}
        </div>
      )}
      <div className="stack" style={{ gap: 14 }}>
        {comps.map((c) => (
          <div key={c.k} className="meter">
            <div className="spread"><span>{c.k}</span><span className="num muted">{num(c.v * 100, 2)}/100</span></div>
            <div className="meter-track"><div className="meter-fill" style={{ width: `${Math.max(2, c.v * 100)}%` }} /></div>
            <span className="caption muted">{c.help}</span>
          </div>
        ))}
      </div>
      {Object.keys(d.drivers).length > 0 && (
        <div className="list">
          {Object.entries(d.drivers).map(([m, x]) => (
            <div key={m} className="list-item" style={{ gridTemplateColumns: "1fr auto" }}>
              <span>{MATRIZ[m]?.nombre ?? m}</span>
              <span className="num">{num(x.mediana)} {MATRIZ[m]?.unidad ?? x.unidad}</span>
            </div>
          ))}
        </div>
      )}
      {d.insumos && (
        <p className="caption muted">
          {int(d.insumos.poblacion)} personas · {d.insumos.n_tomas_agua} tomas de agua · {d.insumos.n_zonas_pesca} zonas de pesca registradas · versión {d.version_id}
        </p>
      )}
    </div>
  );
}

function SitioInfo({ p, onClose }: { p: SitioProps; onClose: () => void }) {
  return (
    <div className="stack">
      <CloseBtn onClose={onClose} />
      <div className="row"><span className="tag">{p.origin === "denuncia" ? "Denuncia (peso 0,2)" : "Detección satelital"}</span>
        <span className={`tag ${p.legal_status === "en_area_protegida" ? "tag-ember" : ""}`}>{LEGAL_TEXTO[p.legal_status]}</span>
        <SyntheticTag show={p.sintetico} />
      </div>
      <h3>Sitio minero {p.status === "activo" ? "activo" : "inactivo"} · {num(p.area_ha)} ha</h3>
      {p.area_protegida && <p>Dentro de <strong style={{ fontWeight: 500 }}>{p.area_protegida}</strong>.</p>}
      <div className="list">
        <div className="list-item" style={{ gridTemplateColumns: "1fr auto" }}><span>Mercurio liberado (estimado)</span><span className="num">{num(p.hg_total_p50)} kg/año</span></div>
        <div className="list-item" style={{ gridTemplateColumns: "1fr auto" }}><span>Rango probable</span><span className="num">{rango(p.hg_total_p05, p.hg_total_p95)} kg/año</span></div>
        <div className="list-item" style={{ gridTemplateColumns: "1fr auto" }}><span>Primera detección</span><span className="num">{fecha(p.first_detected, { year: "numeric" })}</span></div>
        <div className="list-item" style={{ gridTemplateColumns: "1fr auto" }}><span>Última detección</span><span className="num">{fecha(p.last_detected, { year: "numeric" })}</span></div>
      </div>
      <p className="caption muted">
        "Sin concesión" o "en área protegida" describen lo que muestran los datos; no es una determinación legal. La estimación usa factores de emisión en revisión.
      </p>
    </div>
  );
}

function TramoInfo({ p, matriz, onClose }: { p: { hyriv_id: number; p05: number; p50: number; p95: number; n_cercanos: number; presion_kg: number }; matriz: string; onClose: () => void }) {
  const m = MATRIZ[matriz] ?? { nombre: matriz, unidad: "" };
  const ratio = p.p50 / (REFERENCIA[matriz] ?? 1);
  return (
    <div className="stack">
      <CloseBtn onClose={onClose} />
      <span className="meta">Tramo de río {p.hyriv_id}</span>
      <h3>{m.nombre}: {num(p.p50)} {m.unidad}</h3>
      <p className="muted">
        Rango probable {rango(p.p05, p.p95)} {m.unidad}. {ratio >= 1 ? "Por encima del valor de referencia." : ratio >= 0.5 ? "Cerca del valor de referencia." : "Por debajo del valor de referencia."}
      </p>
      <div className="list">
        <div className="list-item" style={{ gridTemplateColumns: "1fr auto" }}><span>Mediciones conectadas por el río</span><span className="num">{p.n_cercanos}</span></div>
        <div className="list-item" style={{ gridTemplateColumns: "1fr auto" }}><span>Presión minera río arriba</span><span className="num">{num(p.presion_kg)} kg/año</span></div>
      </div>
      {p.n_cercanos === 0 && <p className="small muted">Sin mediciones en este tramo: el valor sale del modelo. <Link to="/ingresar">¿Eres laboratorio?</Link></p>}
    </div>
  );
}
