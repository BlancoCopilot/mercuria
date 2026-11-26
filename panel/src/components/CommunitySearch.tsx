import { useEffect, useId, useRef, useState } from "react";
import { api, type Comunidad } from "../lib/api";
import { int } from "../lib/format";

/** Campo de búsqueda de comunidad con lista de sugerencias accesible (combobox). */
export function CommunitySearch({ onPick, placeholder = "Escribe el nombre de tu comunidad", autoFocus }: {
  onPick: (c: Comunidad) => void; placeholder?: string; autoFocus?: boolean;
}) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Comunidad[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [busy, setBusy] = useState(false);
  const id = useId();
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (q.trim().length < 2) { setItems([]); return; }
    setBusy(true);
    const t = setTimeout(() => {
      api<Comunidad[]>(`/v1/communities?q=${encodeURIComponent(q.trim())}&limit=8`, { auth: false })
        .then((r) => { setItems(r); setActive(0); setOpen(true); })
        .catch(() => setItems([]))
        .finally(() => setBusy(false));
    }, 220);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const h = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const pick = (c: Comunidad) => { setQ(c.name); setOpen(false); onPick(c); };

  return (
    <div ref={box} style={{ position: "relative" }}>
      <input
        className="input" type="search" value={q} placeholder={placeholder} autoFocus={autoFocus}
        role="combobox" aria-expanded={open && items.length > 0} aria-controls={`${id}-list`} aria-autocomplete="list"
        aria-activedescendant={open && items[active] ? `${id}-${items[active].id}` : undefined}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => items.length && setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          else if (e.key === "Enter" && items[active]) { e.preventDefault(); pick(items[active]); }
          else if (e.key === "Escape") setOpen(false);
        }}
      />
      {open && q.trim().length >= 2 && (
        <ul id={`${id}-list`} role="listbox" className="combo-list">
          {items.length === 0 && <li className="combo-empty">{busy ? "Buscando…" : "No encontramos esa comunidad. Prueba con otra escritura."}</li>}
          {items.map((c, i) => (
            <li
              key={c.id} id={`${id}-${c.id}`} role="option" aria-selected={i === active}
              onMouseDown={(e) => { e.preventDefault(); pick(c); }} onMouseEnter={() => setActive(i)}
            >
              <span>{c.name}</span>
              <span className="muted small num">{c.poblacion ? `${int(c.poblacion)} hab.` : ""}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
