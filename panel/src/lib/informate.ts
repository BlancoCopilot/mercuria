// Contenido de la sección "Infórmate".
// Para agregar algo basta con añadir un elemento a la lista que corresponda; la página se arma sola.
// Una lista vacía muestra el aviso "Pronto…" en su lugar.

export interface Relato {
  titulo: string;          // ej.: "Ya no pescamos como antes"
  quien: string;           // ej.: "Doña María, pescadora"
  lugar?: string;          // ej.: "Guanay, río Kaka"
  url: string;             // link de YouTube, Facebook, TikTok, Drive…
  resumen?: string;        // una o dos frases
}

export interface Lectura {
  titulo: string;
  fuente: string;          // ej.: "Mongabay Latam"
  anio?: number;
  url: string;
  resumen?: string;
}

export interface Recurso {
  titulo: string;
  tipo: string;            // ej.: "Guía", "Infografía", "Podcast", "Audio en aymara"
  url: string;
  resumen?: string;
}

// ── Videos de personas contando sus relatos ────────────────────────────
export const RELATOS: Relato[] = [
  // { titulo: "…", quien: "…", lugar: "…", url: "https://www.youtube.com/watch?v=…", resumen: "…" },
];

// ── Textos para leer ───────────────────────────────────────────────────
export const LECTURAS: Lectura[] = [
  // { titulo: "…", fuente: "…", anio: 2026, url: "https://…", resumen: "…" },
];

// ── Más: guías, infografías, audios, podcasts… ─────────────────────────
export const RECURSOS: Recurso[] = [
  // { titulo: "…", tipo: "Guía", url: "https://…", resumen: "…" },
];

/** Si el link es de YouTube, devuelve la dirección para verlo dentro de la página. */
export function embedDe(url: string): string | null {
  try {
    const u = new URL(url);
    const host = u.hostname.replace(/^www\.|^m\./, "");
    let id: string | null = null;
    if (host === "youtu.be") id = u.pathname.slice(1);
    else if (host === "youtube.com" || host === "youtube-nocookie.com") {
      if (u.pathname === "/watch") id = u.searchParams.get("v");
      else { const m = u.pathname.match(/^\/(embed|shorts|live)\/([\w-]+)/); id = m ? m[2] : null; }
    }
    return id && /^[\w-]{6,}$/.test(id) ? `https://www.youtube-nocookie.com/embed/${id}` : null;
  } catch {
    return null;
  }
}
