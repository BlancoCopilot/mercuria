import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import { createMap, loadBaseStyle } from "../lib/map";

/** Mapa pequeño para marcar un punto. Clic o arrastrar el marcador. */
export function PointPicker({ value, onChange, height }: {
  value: { lat: number; lon: number } | null; onChange: (p: { lat: number; lon: number }) => void; height?: number;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const marker = useRef<maplibregl.Marker | null>(null);
  const cb = useRef(onChange);
  cb.current = onChange;

  useEffect(() => {
    let off = false;
    loadBaseStyle().then((style) => {
      if (off || !el.current) return;
      const m = createMap(el.current, style, { zoom: 8 });
      map.current = m;
      m.on("click", (e) => cb.current({ lat: e.lngLat.lat, lon: e.lngLat.lng }));
    });
    return () => { off = true; map.current?.remove(); };
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m || !value) return;
    if (!marker.current) {
      const dot = document.createElement("div");
      dot.style.cssText = "width:22px;height:22px;border-radius:50%;background:#dd5000;border:3px solid #f7f0e1;outline:1px solid #23212c";
      marker.current = new maplibregl.Marker({ element: dot, draggable: true }).setLngLat([value.lon, value.lat]).addTo(m);
      marker.current.on("dragend", () => {
        const ll = marker.current!.getLngLat();
        cb.current({ lat: ll.lat, lon: ll.lng });
      });
    } else marker.current.setLngLat([value.lon, value.lat]);
  }, [value]);

  return <div ref={el} className="picker" style={height ? { height } : undefined} role="application" aria-label="Mapa para marcar el lugar" />;
}
