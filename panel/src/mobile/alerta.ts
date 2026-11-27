// Texto de la alerta de zona con riesgo. Lo usan la app abierta y el revisor en segundo plano
// (runner/zona.ts), para que la persona reciba siempre el mismo mensaje.

export type NivelCelda = "bajo" | "medio" | "alto" | null;

export interface Alerta { title: string; body: string }

/** null = no hay que avisar. `cerca` = una zona vecina (≈3 km) tiene riesgo alto. */
export function alertaPara(nivel: NivelCelda, cerca: boolean, comunidad?: string | null): Alerta | null {
  const donde = comunidad ? ` (cerca de ${comunidad})` : "";
  if (nivel === "alto") {
    return { title: "Zona de riesgo ALTO por mercurio", body: `Estás en una zona de riesgo alto${donde}. Embarazadas y niños: no coman surubí, dorado ni palometa. Abre MercurIA para saber qué hacer.` };
  }
  if (nivel === "medio") {
    return { title: "Zona de riesgo MEDIO por mercurio", body: `Estás en una zona de riesgo medio${donde}. Prefiere pacú o yatorana y no quemes amalgama cerca de la casa.` };
  }
  if (cerca) {
    return { title: "Cerca hay una zona de riesgo ALTO", body: `A menos de 3 km de ti hay una zona de riesgo alto por mercurio${donde}. Abre MercurIA para saber qué hacer.` };
  }
  return null;
}

/** Clave para no repetir la misma alerta: cambia solo si cambia la zona o su nivel. */
export const claveAlerta = (h3: string, nivel: NivelCelda, cerca: boolean) => `${h3}:${nivel ?? "nd"}:${cerca ? 1 : 0}`;

export const CANAL_RIESGO = "riesgo";
export const RUNNER_LABEL = "bo.mercuria.app.zona";
export const ID_NOTIFICACION = 7001;
