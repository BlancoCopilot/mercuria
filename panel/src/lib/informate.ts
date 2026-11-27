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

// ── Nuestro video (archivo propio, en panel/public/videos/) ────────────
export const VIDEO_PROPIO = {
  titulo: "¿Cómo nos afecta el mercurio?",
  resumen: "Gota te cuenta en dos minutos cómo el mercurio del oro llega al río y al pescado, y cómo MercurIA te ayuda a cuidarte.",
  src: "videos/mercuria-resumen.mp4",
  poster: "videos/mercuria-resumen.jpg",
  duracion: "1:58",
  youtube: "", // pegar aquí el link cuando el video esté subido al canal
};

// ── Canal de YouTube de MercurIA ───────────────────────────────────────
export const CANAL_YOUTUBE = { url: "https://www.youtube.com/@mercuria-p9e", usuario: "@mercuria-p9e" };

// ── Videos de personas contando sus relatos y reportajes ───────────────
export const RELATOS: Relato[] = [
  {
    titulo: "El oro tóxico: el mercurio de la minería contamina el río Beni y amenaza a 164 comunidades indígenas",
    quien: "Te Lo Cuenta Víctor Hugo",
    lugar: "Río Beni",
    url: "https://youtu.be/tuQSZQ7aRLU",
  },
  {
    titulo: "Contaminación con mercurio en Bolivia",
    quien: "DW Español",
    url: "https://youtu.be/I_3HqQ0UB8c",
  },
  {
    titulo: "Bolivia: The Killer Gold",
    quien: "ARTE.tv Documentales",
    url: "https://youtu.be/PKMEgyMeDpc",
  },
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
  const id = youtubeId(url);
  return id ? `https://www.youtube-nocookie.com/embed/${id}` : null;
}

/** Identificador del video si el link es de YouTube (youtu.be, watch, embed, shorts, live). */
export function youtubeId(url: string): string | null {
  try {
    const u = new URL(url);
    const host = u.hostname.replace(/^www\.|^m\./, "");
    let id: string | null = null;
    if (host === "youtu.be") id = u.pathname.slice(1);
    else if (host === "youtube.com" || host === "youtube-nocookie.com") {
      if (u.pathname === "/watch") id = u.searchParams.get("v");
      else { const m = u.pathname.match(/^\/(embed|shorts|live)\/([\w-]+)/); id = m ? m[2] : null; }
    }
    return id && /^[\w-]{6,}$/.test(id) ? id : null;
  } catch {
    return null;
  }
}
