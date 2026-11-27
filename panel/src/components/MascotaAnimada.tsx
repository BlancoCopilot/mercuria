import { useEffect, useRef, useState, type PointerEvent as RPointerEvent } from "react";
import { useLocation } from "react-router-dom";
import { useUbicacion } from "../lib/location";
import type { Mood } from "./Mascot";
import { DURACION, EVENTO, GLOBO, UNA_VEZ, srcDe, type DetalleReaccion, type Reaccion } from "../lib/mascota";
import "../styles/mascota.css";

// Gota animada, como una mascota de escritorio: reacciona a lo que pasa en la app.
//   · chat buscando → laptop · chat respondiendo → hablando · al abrir el chat → saludando
//   · cambiar de página → camina · /denunciar → sostiene un celular · mapa y fichas → señala
//   · zona de riesgo alto → se asusta · riesgo medio o error → sorpresa
// Otras partes de la app pueden hacerla reaccionar con reaccionar() de lib/mascota.
// Se puede arrastrar a cualquier parte de la pantalla (recuerda dónde la dejaste).

const TODAS: Reaccion[] = ["quieto", "saludando", "hablando", "laptop", "celular", "senalando", "caminando", "sorpresa", "asustado"];
const SALUDO_KEY = "rastrohg.gota-saludo";
const POS_KEY = "rastrohg.gota-pos";

interface Pos { right: number; bottom: number }
function leerPos(): Pos | null { try { const p = JSON.parse(localStorage.getItem(POS_KEY) || "null"); return p && typeof p.right === "number" ? p : null; } catch { return null; } }

/** Reacción que corresponde a la página (se queda mientras estés en ella). */
function dePagina(path: string): { r: Reaccion; fija: boolean; globo?: string | null } {
  if (path.startsWith("/denunciar")) return { r: "celular", fija: true, globo: "Tu denuncia es anónima." };
  if (path === "/") return { r: "senalando", fija: false };
  if (path.startsWith("/comunidad/")) return { r: "senalando", fija: false, globo: "Esto es lo que te conviene saber." };
  if (path.startsWith("/comunidades")) return { r: "senalando", fija: false, globo: "Busca tu comunidad." };
  if (path.startsWith("/informate")) return { r: "senalando", fija: false, globo: "Escucha lo que cuentan en los ríos." };
  if (/^\/(datos|aportar|laboratorio|panel|admin|validar|salud)/.test(path)) return { r: "laptop", fija: true, globo: path.startsWith("/datos") ? "Datos abiertos para todos." : null };
  return { r: "quieto", fija: true };
}

interface Evento { r: Reaccion; hasta: number; globo: string | null }

export function MascotaAnimada({ chatAbierto, mood, err, ocultarGlobo }: { chatAbierto: boolean; mood: Mood; err: string | null; ocultarGlobo?: boolean }) {
  const loc = useLocation();
  const { zona } = useUbicacion();
  const [evento, setEvento] = useState<Evento | null>(null);
  const [fija, setFija] = useState<Reaccion | null>(null); // pedida desde fuera con ms = 0
  const [globo, setGlobo] = useState<string | null>(null);
  const [ahora, setAhora] = useState(() => Date.now());
  const quieta = useReducedMotion();
  const primera = useRef(true);
  const blobs = useRef<Partial<Record<Reaccion, Blob>>>({});
  const img = useRef<HTMLImageElement>(null);
  const [pos, setPos] = useState<Pos | null>(leerPos);
  const [arrastrando, setArrastrando] = useState(false);
  const [lado, setLado] = useState<"izq" | "der">("izq");

  // Precarga las animaciones una vez (para que cambiar de reacción sea inmediato)
  useEffect(() => {
    let vivo = true;
    TODAS.forEach((r) => fetch(srcDe(r)).then((x) => x.blob()).then((b) => { if (vivo) blobs.current[r] = b; }).catch(() => { /* usa la URL directa */ }));
    return () => { vivo = false; };
  }, []);

  const lanzar = (r: Reaccion, ms?: number, g?: string | null) => {
    const dur = ms ?? (UNA_VEZ.has(r) ? DURACION[r] + 1500 : DURACION[r]);
    setEvento({ r, hasta: Date.now() + dur, globo: g === undefined ? GLOBO[r] ?? null : g });
  };

  // Reacciones pedidas desde cualquier parte de la app
  useEffect(() => {
    const on = (e: Event) => {
      const d = (e as CustomEvent<DetalleReaccion>).detail;
      if (!d || d.reaccion === null) { setFija(null); return; }
      if (d.ms === 0) { setFija(d.reaccion); if (d.globo) setGlobo(d.globo); return; }
      lanzar(d.reaccion, d.ms, d.globo);
    };
    window.addEventListener(EVENTO, on);
    return () => window.removeEventListener(EVENTO, on);
  }, []);

  // Saludo la primera vez de la sesión; al cambiar de página camina y luego hace lo de la página
  useEffect(() => {
    const p = dePagina(loc.pathname);
    if (primera.current) {
      primera.current = false;
      let saludo = false;
      try { saludo = !sessionStorage.getItem(SALUDO_KEY); sessionStorage.setItem(SALUDO_KEY, "1"); } catch { /* */ }
      if (saludo) { lanzar("saludando"); return; }
      if (!p.fija) lanzar(p.r, undefined, p.globo);
      return;
    }
    lanzar("caminando", DURACION.caminando, null);
    const t = window.setTimeout(() => { if (!p.fija) lanzar(p.r, undefined, p.globo); else if (p.globo) setGlobo(p.globo); }, DURACION.caminando);
    return () => window.clearTimeout(t);
  }, [loc.pathname]);

  // Aviso de riesgo por ubicación
  const nivel = zona?.nivel;
  const cerca = zona?.cercaAlto;
  useEffect(() => {
    if (nivel === "alto") lanzar("asustado");
    else if (nivel === "medio" || cerca) lanzar("sorpresa");
  }, [nivel, cerca]);

  // Al abrir el chat saluda; si falla, se sorprende
  const abiertoAntes = useRef(chatAbierto);
  useEffect(() => {
    if (chatAbierto && !abiertoAntes.current) lanzar("saludando", undefined, null);
    abiertoAntes.current = chatAbierto;
  }, [chatAbierto]);
  useEffect(() => { if (err) lanzar("sorpresa", undefined, "Uy, no pude responder."); }, [err]);

  // Reloj: vuelve sola al estado normal cuando termina una reacción
  useEffect(() => {
    if (!evento) return;
    const falta = evento.hasta - Date.now();
    if (falta <= 0) { setEvento(null); return; }
    const t = window.setTimeout(() => { setEvento(null); setAhora(Date.now()); }, falta);
    return () => window.clearTimeout(t);
  }, [evento]);

  // De vez en cuando, si nadie la usa, saluda (como una mascota de escritorio)
  useEffect(() => {
    const t = window.setInterval(() => {
      if (!document.hidden && !evento && mood === "idle" && !fija) lanzar("saludando", undefined, null);
    }, 45000);
    return () => window.clearInterval(t);
  }, [evento, mood, fija]);

  // Qué se ve ahora (de mayor a menor prioridad)
  const pagina = dePagina(loc.pathname);
  const r: Reaccion =
    (arrastrando ? "caminando" : null) ??
    fija ??
    (mood === "thinking" ? "laptop" : mood === "talking" ? "hablando" : null) ??
    (evento && evento.hasta > ahora - 50 ? evento.r : null) ??
    (pagina.fija ? pagina.r : "quieto");

  // Globo: aparece al empezar una reacción con texto y se va solo
  useEffect(() => {
    if (evento?.globo) setGlobo(evento.globo);
  }, [evento]);
  useEffect(() => {
    if (mood === "thinking" && !chatAbierto) setGlobo(GLOBO.laptop ?? null);
  }, [mood, chatAbierto]);
  useEffect(() => {
    if (!globo) return;
    const t = window.setTimeout(() => setGlobo(null), 3800);
    return () => window.clearTimeout(t);
  }, [globo]);

  // Cada vez que empieza una reacción se crea una URL nueva: así la animación arranca desde el principio
  const [src, setSrc] = useState(() => srcDe("quieto"));
  const vez = evento ? evento.hasta : 0;
  useEffect(() => {
    if (quieta) { setSrc(srcDe("quieto")); return; }
    const b = blobs.current[r];
    if (!b) { setSrc(srcDe(r)); return; }
    const url = URL.createObjectURL(b);
    setSrc(url);
    return () => URL.revokeObjectURL(url);
  }, [r, vez, quieta]);

  // ── Arrastrar: Gota se mueve a donde la dejes, como una mascota de escritorio ──
  const boton = () => img.current?.closest<HTMLElement>(".fab-pet") ?? null;

  // Aplica la posición guardada (si nunca se movió, manda el CSS de siempre)
  useEffect(() => {
    const b = boton();
    if (!b) return;
    const ajustar = () => {
      if (!pos) { b.style.right = ""; b.style.bottom = ""; return; }
      const w = b.offsetWidth, h = b.offsetHeight;
      const right = Math.min(Math.max(pos.right, 4), window.innerWidth - w - 4);
      const bottom = Math.min(Math.max(pos.bottom, 4), window.innerHeight - h - 4);
      b.style.right = `${right}px`; b.style.bottom = `${bottom}px`;
      document.documentElement.style.setProperty("--gota-r", `${right}px`);
      document.documentElement.style.setProperty("--gota-b", `${bottom}px`);
    };
    ajustar();
    const rect = b.getBoundingClientRect();
    setLado(rect.left + rect.width / 2 < 260 ? "der" : "izq");
    window.addEventListener("resize", ajustar);
    return () => window.removeEventListener("resize", ajustar);
  }, [pos]);

  const alPresionar = (e: RPointerEvent<HTMLImageElement>) => {
    if (e.button !== 0) return;
    const b = boton();
    if (!b) return;
    const r0 = b.getBoundingClientRect();
    const x0 = e.clientX, y0 = e.clientY;
    const inicio = { right: window.innerWidth - r0.right, bottom: window.innerHeight - r0.bottom };
    let movio = false;
    const mover = (ev: PointerEvent) => {
      const dx = ev.clientX - x0, dy = ev.clientY - y0;
      if (!movio && Math.hypot(dx, dy) < 6) return;
      if (!movio) { movio = true; setArrastrando(true); setGlobo(null); }
      const right = Math.min(Math.max(inicio.right - dx, 4), window.innerWidth - r0.width - 4);
      const bottom = Math.min(Math.max(inicio.bottom - dy, 4), window.innerHeight - r0.height - 4);
      b.style.right = `${right}px`; b.style.bottom = `${bottom}px`;
    };
    const soltar = () => {
      window.removeEventListener("pointermove", mover);
      window.removeEventListener("pointerup", soltar);
      window.removeEventListener("pointercancel", soltar);
      if (!movio) return;
      setArrastrando(false);
      const p = { right: parseFloat(b.style.right), bottom: parseFloat(b.style.bottom) };
      setPos(p);
      try { localStorage.setItem(POS_KEY, JSON.stringify(p)); } catch { /* */ }
      // el clic que sigue a un arrastre no abre el chat
      const tragar = (ev: MouseEvent) => { ev.stopPropagation(); ev.preventDefault(); };
      window.addEventListener("click", tragar, { capture: true, once: true });
      window.setTimeout(() => window.removeEventListener("click", tragar, { capture: true }), 300);
    };
    window.addEventListener("pointermove", mover);
    window.addEventListener("pointerup", soltar);
    window.addEventListener("pointercancel", soltar);
  };

  // Doble clic: vuelve a su lugar de siempre
  const alDobleClic = () => {
    setPos(null);
    try { localStorage.removeItem(POS_KEY); } catch { /* */ }
    document.documentElement.style.removeProperty("--gota-r");
    document.documentElement.style.removeProperty("--gota-b");
  };

  const verGlobo = globo && !chatAbierto && !ocultarGlobo && !arrastrando;
  return (
    <>
      {verGlobo && <span className="gota-globo" data-lado={lado} role="status" aria-live="polite">{globo}</span>}
      <img ref={img} className="gota-anim" data-reaccion={r} data-arrastrando={arrastrando || undefined} src={src} alt="" width={150} height={165}
        draggable={false} onPointerDown={alPresionar} onDoubleClick={alDobleClic} title="Arrástrame a donde quieras · doble clic para volver" />
    </>
  );
}

function useReducedMotion() {
  const [v, setV] = useState(() => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const m = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setV(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return v;
}
