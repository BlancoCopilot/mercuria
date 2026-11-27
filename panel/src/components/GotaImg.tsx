import type { Mood } from "./Mascot";
import { srcDe, type Reaccion } from "../lib/mascota";

// Gota (la ilustración animada) para el chat: reemplaza a la gota vectorial verde.
//   escribiendo → señala el campo de texto · en llamada, escuchando → celular · buscando → laptop · respondiendo → habla · error → sorpresa
const POR_ANIMO: Record<Mood, Reaccion> = { idle: "quieto", listening: "senalando", thinking: "laptop", talking: "hablando" };

export function GotaImg({ mood = "idle", size = 140, still = false, err = false, llamada = false, label = "Gota, la mascota de MercurIA" }:
  { mood?: Mood; size?: number; still?: boolean; err?: boolean; llamada?: boolean; label?: string }) {
  // En llamada, mientras te escucha, sostiene el celular
  const r: Reaccion = still ? "quieto" : err ? "sorpresa" : llamada && mood === "listening" ? "celular" : POR_ANIMO[mood];
  return (
    <img className="gota-img" data-reaccion={r} src={srcDe(r)} alt={label} role={label ? undefined : "presentation"}
      width={Math.round((size * 256) / 280)} height={size} draggable={false}
      style={{ width: Math.round((size * 256) / 280), height: size, objectFit: "contain", display: "block", flex: "none" }} />
  );
}
