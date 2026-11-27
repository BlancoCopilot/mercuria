import type { Mood } from "./Mascot";
import { srcDe, type Reaccion } from "../lib/mascota";

// Gota (la ilustración animada) para el chat: reemplaza a la gota vectorial verde.
//   escribiendo → señala el campo de texto · buscando → laptop · respondiendo → habla · error → sorpresa
const POR_ANIMO: Record<Mood, Reaccion> = { idle: "quieto", listening: "senalando", thinking: "laptop", talking: "hablando" };

export function GotaImg({ mood = "idle", size = 140, still = false, err = false, label = "Gota, la mascota de MercurIA" }:
  { mood?: Mood; size?: number; still?: boolean; err?: boolean; label?: string }) {
  const r: Reaccion = still ? "quieto" : err ? "sorpresa" : POR_ANIMO[mood];
  return (
    <img className="gota-img" data-reaccion={r} src={srcDe(r)} alt={label} role={label ? undefined : "presentation"}
      width={Math.round((size * 256) / 280)} height={size} draggable={false}
      style={{ width: Math.round((size * 256) / 280), height: size, objectFit: "contain", display: "block", flex: "none" }} />
  );
}
