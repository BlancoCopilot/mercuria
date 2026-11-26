import { useId } from "react";

// Mascota de MercurIA: una gota. Silueta vectorizada de la ilustración original
// (contorno suavizado, 347 × 480 unidades). Sin cara = acompaña al logo; con cara = el chat.
export const DROP_PATH =
  "M180.1 480.0 C176.2 480.0 164.9 480.5 157.4 480.1 C149.9 479.7 142.2 478.7 135.1 477.4 C128.0 476.1 124.0 476.0 115.0 472.5 C106.0 469.0 90.8 461.9 81.1 456.4 C71.4 450.9 63.7 444.8 57.1 439.4 C50.5 434.0 46.2 428.8 41.7 423.8 C37.2 418.8 34.6 415.7 30.3 409.2 C26.0 402.7 19.0 390.5 15.8 384.7 C12.6 378.9 12.9 379.3 11.1 374.4 C9.3 369.5 6.8 363.6 5.0 355.5 C3.2 347.4 1.0 335.3 0.2 325.8 C-0.6 316.3 0.0 304.9 0.3 298.3 C0.6 291.7 0.8 291.1 1.9 286.4 C3.0 281.7 3.9 277.6 6.7 270.2 C9.5 262.8 13.4 252.4 18.6 242.1 C23.8 231.8 26.7 226.0 38.0 208.5 C49.3 191.0 72.7 158.5 86.7 137.2 C100.7 115.9 112.6 97.0 122.1 80.6 C131.5 64.2 137.5 50.8 143.4 38.9 C149.3 27.0 154.0 15.0 157.4 8.9 C160.8 2.8 161.4 3.7 163.7 2.2 C166.0 0.7 170.5 0.6 171.2 0.1 C171.2 0.1 168.0 -0.5 168.0 -0.5 C168.0 -0.5 180.0 1.5 180.0 1.5 C182.7 2.3 183.1 3.2 184.3 4.2 C185.5 5.2 184.7 3.5 187.0 7.5 C189.3 11.5 195.5 22.3 198.4 28.1 C201.3 33.9 201.4 36.2 204.3 42.2 C207.2 48.2 209.7 53.5 215.7 63.8 C221.7 74.1 231.8 90.9 240.2 104.3 C248.6 117.7 255.5 128.5 266.4 144.1 C277.3 159.7 296.8 185.9 305.4 198.1 C314.0 210.3 313.9 210.2 318.1 217.4 C322.3 224.6 326.7 233.3 330.4 241.1 C334.1 248.9 337.7 256.5 340.2 264.3 C342.7 272.1 344.5 281.5 345.6 287.9 C346.7 294.3 346.6 297.6 346.8 302.6 C347.0 307.6 347.0 312.6 346.6 318.1 C346.2 323.6 346.4 327.6 344.7 335.7 C343.0 343.8 338.9 358.8 336.2 366.7 C333.5 374.6 331.4 378.0 328.7 383.2 C326.0 388.4 323.1 393.0 320.1 397.6 C317.1 402.2 314.2 406.6 310.6 411.1 C307.0 415.6 303.0 420.0 298.3 424.8 C293.6 429.6 287.3 435.6 282.3 439.8 C277.3 444.0 273.1 446.6 268.3 449.8 C263.5 453.0 261.7 454.9 253.3 458.8 C244.9 462.7 226.8 470.2 217.8 473.3 C208.9 476.4 205.8 476.4 199.6 477.5 C193.4 478.6 184.2 479.5 180.9 479.9 C177.7 480.3 184.0 480.0 180.1 480.0 Z";

// Boca en "D": borde superior recto, fondo redondo (medida sobre la ilustración)
const MOUTH = "M119 356 Q119 343 132 343 H226 Q239 343 239 356 C239 400 212 432 179 432 C146 432 119 400 119 356 Z";

export type Mood = "idle" | "listening" | "thinking" | "talking";

const INK = "#065233";      // mismo verde del logo
const DEEP = "#063e28";     // pupilas y boca: apenas más oscuras que el cuerpo, como el original
const WHITE = "#fbf8f0";

export function Drop({ height = 32, title }: { height?: number; title?: string }) {
  return (
    <svg viewBox="-4 -6 355 490" height={height} width={(height * 355) / 490} role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true} aria-label={title} style={{ display: "block", flex: "none" }}>
      <path d={DROP_PATH} fill={INK} />
    </svg>
  );
}

/** Gota con cara. Parpadea sola; escucha mientras escribes, piensa mientras busca y mueve la boca al responder. */
export function Mascot({ mood = "idle", size = 140, label = "Gota, la mascota de MercurIA", still = false }: { mood?: Mood; size?: number; label?: string; still?: boolean }) {
  const clip = useId().replace(/:/g, "");
  return (
    <svg className={still ? "mascot mascot-still" : "mascot"} data-mood={mood} viewBox="-4 -6 355 490" width={(size * 355) / 490} height={size} role="img" aria-label={label}>
      <path className="m-body" d={DROP_PATH} fill={INK} />
      <defs>
        {/* Mejillas: recortan el borde inferior de ojos y pupilas, como en la ilustración */}
        <clipPath id={`e${clip}`}>
          <path d="M0 0 H347 V480 H0 Z M31 351 a70 30 0 1 0 140 0 a70 30 0 1 0 -140 0 Z M180.5 349 a70 30 0 1 0 140 0 a70 30 0 1 0 -140 0 Z" clipRule="evenodd" />
        </clipPath>
        <clipPath id={`m${clip}`}><path d={MOUTH} /></clipPath>
      </defs>
      <g className="m-eyes" clipPath={`url(#e${clip})`}>
        <g className="m-eye">
          <ellipse cx="101" cy="264.5" rx="54" ry="64.5" fill={WHITE} />
          <g className="m-pupil">
            <ellipse cx="115.5" cy="276" rx="32.5" ry="43" fill={DEEP} />
            <circle cx="97" cy="258" r="10.5" fill={WHITE} />
          </g>
        </g>
        <g className="m-eye">
          <ellipse cx="250.5" cy="263" rx="54.5" ry="64" fill={WHITE} />
          <g className="m-pupil">
            <ellipse cx="262.5" cy="274" rx="32.5" ry="43" fill={DEEP} />
            <circle cx="245" cy="254" r="10.5" fill={WHITE} />
          </g>
        </g>
      </g>
      <g className="m-mouth">
        <path d={MOUTH} fill={DEEP} />
        <g clipPath={`url(#m${clip})`}>
          <rect x="126" y="356" width="109" height="23" rx="9" fill={WHITE} />
          <path d="M141 396 Q175 387 209 396 Q203 420 175 420 Q147 420 141 396 Z" fill={WHITE} />
        </g>
      </g>
    </svg>
  );
}
