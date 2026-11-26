import { useState } from "react";
import { int } from "../lib/format";

// Small multiples de columnas: una serie por gráfico (sin leyenda; el título la nombra).
// Marcas según la guía de visualización: columna ≤ 24 px, extremo redondeado de 4 px y base recta,
// 2 px de aire entre columnas, una sola etiqueta (el último valor) y tooltip por columna.
// Color #2e8a5c validado (banda de luminosidad, croma y contraste sobre blanco).

export interface Serie { key: string; titulo: string; ayuda: string }

const MES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const mesCorto = (ym: string) => { const [y, m] = ym.split("-"); return `${MES[+m - 1]} ${y.slice(2)}`; };

export function Multiples({ rows, series }: { rows: Record<string, number | string>[]; series: Serie[] }) {
  const [tabla, setTabla] = useState(false);
  return (
    <div className="stack">
      <div className="row"><button className="btn btn-pill" aria-pressed={tabla} onClick={() => setTabla((t) => !t)}>{tabla ? "Ver gráficos" : "Ver tabla"}</button></div>
      {tabla ? (
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Mes</th>{series.map((s) => <th key={s.key} className="r">{s.titulo}</th>)}</tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={String(r.mes)}><td>{mesCorto(String(r.mes))}</td>{series.map((s) => <td key={s.key} className="r">{int(Number(r[s.key]))}</td>)}</tr>
            ))}</tbody>
          </table>
        </div>
      ) : (
        <div className="multiples">
          {series.map((s) => <Mini key={s.key} rows={rows} s={s} />)}
        </div>
      )}
    </div>
  );
}

function Mini({ rows, s }: { rows: Record<string, number | string>[]; s: Serie }) {
  const [hover, setHover] = useState<number | null>(null);
  const vals = rows.map((r) => Number(r[s.key]) || 0);
  const max = Math.max(1, ...vals);
  const last = vals[vals.length - 1] ?? 0;
  const h = hover ?? vals.length - 1;
  return (
    <figure className="mini" style={{ margin: 0 }}>
      <figcaption className="spread" style={{ alignItems: "baseline" }}>
        <span style={{ fontWeight: 500 }}>{s.titulo}</span>
        <span className="num" style={{ fontSize: 22, fontWeight: 300, letterSpacing: "-0.02em" }}>{int(vals[h])}</span>
      </figcaption>
      <p className="caption muted" style={{ minHeight: 16 }}>
        {hover !== null ? mesCorto(String(rows[hover].mes)) : `${mesCorto(String(rows[rows.length - 1]?.mes ?? "2026-01"))} · ${s.ayuda}`}
      </p>
      <div className="mini-plot" role="img" aria-label={`${s.titulo}: último mes ${int(last)}, máximo ${int(max)}`}>
        {vals.map((v, i) => (
          <button
            key={i} className="mini-col" type="button"
            onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}
            aria-label={`${mesCorto(String(rows[i].mes))}: ${int(v)}`}
          >
            <span className="mini-bar" data-active={h === i} data-zero={v === 0} style={{ height: v === 0 ? 2 : `${Math.max(4, (v / max) * 100)}%` }} />
          </button>
        ))}
      </div>
      <div className="spark-axis"><span>{rows[0] && mesCorto(String(rows[0].mes))}</span><span>{rows.length > 0 && mesCorto(String(rows[rows.length - 1].mes))}</span></div>
    </figure>
  );
}
