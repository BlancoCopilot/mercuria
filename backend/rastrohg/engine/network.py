"""Red fluvial (HydroRIVERS) como árbol dirigido tramo -> tramo río abajo.

HydroRIVERS ya trae NEXT_DOWN (siguiente tramo), LENGTH_KM, UPLAND_SKM (área de
cuenca aguas arriba) y DIS_AV_CMS (caudal medio). Con eso basta un diccionario: no
hace falta un grafo general (networkx) para recorrer río abajo o río arriba.
Las distancias se miden entre puntos medios de tramo, a lo largo del río.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Reach:
    id: int
    next_down: int          # 0 = desembocadura / sale del área cargada
    length_km: float
    upland_skm: float
    dis_av_cms: float


class RiverNetwork:
    def __init__(self, reaches: list[Reach]):
        self.reaches: dict[int, Reach] = {r.id: r for r in reaches}
        self.upstream: dict[int, list[int]] = defaultdict(list)
        for r in reaches:
            if r.next_down in self.reaches:
                self.upstream[r.next_down].append(r.id)
        self.ids: list[int] = sorted(self.reaches)
        self.index: dict[int, int] = {rid: i for i, rid in enumerate(self.ids)}
        self._conn_cache: dict[tuple[int, float], dict[int, float]] = {}

    def __len__(self) -> int:
        return len(self.reaches)

    def downstream(self, rid: int, max_km: float = float("inf")) -> list[tuple[int, float]]:
        """[(tramo, distancia_km)] desde rid (incluido, d=0) hacia la desembocadura."""
        out = [(rid, 0.0)]
        cur = self.reaches[rid]
        d = 0.0
        seen = {rid}
        while cur.next_down in self.reaches and cur.next_down not in seen:
            nxt = self.reaches[cur.next_down]
            d += cur.length_km / 2 + nxt.length_km / 2
            if d > max_km:
                break
            out.append((nxt.id, d))
            seen.add(nxt.id)
            cur = nxt
        return out

    def upstream_within(self, rid: int, max_km: float) -> list[tuple[int, float]]:
        """Todos los tramos río arriba de rid (sin incluirlo) a menos de max_km."""
        out: list[tuple[int, float]] = []
        q = deque([(rid, 0.0)])
        while q:
            cur, d = q.popleft()
            lc = self.reaches[cur].length_km
            for up in self.upstream.get(cur, ()):
                du = d + lc / 2 + self.reaches[up].length_km / 2
                if du <= max_km:
                    out.append((up, du))
                    q.append((up, du))
        return out

    def flow_connected(self, rid: int, max_km: float) -> dict[int, float]:
        """Tramos conectados por el flujo (río arriba o abajo) con distancia de red.

        Dos tramos en tributarios distintos que solo se juntan más abajo NO están
        conectados por el flujo: el agua de uno nunca pasa por el otro.
        """
        key = (rid, max_km)
        if key not in self._conn_cache:
            res = dict(self.downstream(rid, max_km))
            res.update(dict(self.upstream_within(rid, max_km)))
            self._conn_cache[key] = res
        return self._conn_cache[key]

    def is_upstream_of(self, a: int, b: int, max_km: float) -> bool:
        return any(r == b for r, _ in self.downstream(a, max_km))
