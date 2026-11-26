"""CLI de operación: `rastrohg <comando>` (dentro del contenedor: docker compose exec api rastrohg ...)."""
from __future__ import annotations

import argparse
import json
import logging
import sys


def _print(x):
    print(json.dumps(x, indent=2, ensure_ascii=False, default=str))


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser(prog="rastrohg")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("seed-synthetic", help="cuenca sintética + usuarios demo (todo marcado is_synthetic)")
    sub.add_parser("purge-synthetic", help="borra todo dato sintético")
    sub.add_parser("demo-mine-geojson", help="imprime el polígono de la mina nueva de la demo")

    h = sub.add_parser("load-hydrorivers")
    h.add_argument("path")
    h.add_argument("--outlet", type=int, help="HYRIV_ID de salida: carga todo lo que drena a él")
    h.add_argument("--min-upland", type=float, default=0)

    o = sub.add_parser("load-osm")
    o.add_argument("--file", help="JSON de Overpass ya descargado (si no, consulta Overpass)")

    for name in ("load-census", "load-concessions", "load-protected", "load-measurements"):
        sub.add_parser(name).add_argument("path")
    sub.add_parser("build-cells")

    sub.add_parser("recompute", help="recalcula ya (sin cola)")
    s = sub.add_parser("sampling")
    s.add_argument("--matrix", default="agua")
    s.add_argument("-k", type=int, default=3)
    i = sub.add_parser("ingest", help="tarea programada")
    i.add_argument("source", choices=["amw", "mapbiomas", "osm"])
    mb = sub.add_parser("export-mapbiomas", help="genera el GeoJSON de minería de MapBiomas desde Earth Engine")
    mb.add_argument("--out", required=True)
    mb.add_argument("--desde", type=int, default=2000)
    wp = sub.add_parser("load-worldpop", help="estima población por poblado con WorldPop (Earth Engine)")
    wp.add_argument("--radio-m", type=int, default=3000)
    sub.add_parser("push", help="envía notificaciones pendientes")
    sub.add_parser("enqueue-recompute", help="encola un recálculo (cron)")
    sub.add_parser("release-embargoes", help="publica estudios cuyo embargo venció (cron diario)")

    ri = sub.add_parser("rag-ingest", help="carga PDFs y preguntas frecuentes al chatbot RAG")
    ri.add_argument("path", help="carpeta con docs/*.pdf, docs/temas.json y preguntas_frecuentes.csv")
    ri.add_argument("--force", action="store_true", help="re-procesa aunque el archivo no haya cambiado")
    ra = sub.add_parser("rag-ask", help="pregunta al chatbot desde la terminal")
    ra.add_argument("pregunta")
    ra.add_argument("--tema", choices=["peces", "salud", "mineria", "agua"])
    ra.add_argument("--solo-buscar", action="store_true", help="muestra los fragmentos, sin llamar a OpenAI")
    ra.add_argument("--lat", type=float)
    ra.add_argument("--lon", type=float)

    u = sub.add_parser("create-user")
    u.add_argument("--email", required=True)
    u.add_argument("--name", required=True)
    u.add_argument("--role", required=True, choices=["admin", "laboratorio", "promotor", "lider", "autoridad"])
    u.add_argument("--password", required=True)

    a = p.parse_args(argv)
    from . import db, synthetic
    from .worker import jobs, pipeline

    if a.cmd == "seed-synthetic":
        _print(synthetic.seed())
        _print(pipeline.run_recompute([{"tipo": "inicial_sintetico"}]))
        _print(pipeline.run_sampling("agua"))
    elif a.cmd == "purge-synthetic":
        _print(synthetic.purge())
    elif a.cmd == "demo-mine-geojson":
        _print(synthetic.demo_new_mine_geojson())
    elif a.cmd == "load-hydrorivers":
        from .ingest.base import build_cells
        from .ingest.hydrorivers import load_hydrorivers
        _print(load_hydrorivers(a.path, a.outlet, a.min_upland))
        with db.tx() as c:
            _print(build_cells(c))
    elif a.cmd == "load-osm":
        from .ingest import osm
        if a.file:
            with open(a.file, encoding="utf-8") as fh:
                _print(osm.load_overpass_json(json.load(fh)))
        else:
            _print(osm.ingest_osm())
    elif a.cmd == "load-census":
        from .ingest.tables import load_census_csv
        _print(load_census_csv(a.path))
    elif a.cmd == "load-concessions":
        from .ingest.tables import load_concessions
        _print(load_concessions(a.path))
    elif a.cmd == "load-protected":
        from .ingest.tables import load_protected_areas
        _print(load_protected_areas(a.path))
    elif a.cmd == "load-measurements":
        from .services.measurements import insert_measurements, parse_csv
        with open(a.path, "rb") as fh, db.tx() as c:
            _print(insert_measurements(c, parse_csv(fh.read()), None, None))
    elif a.cmd == "build-cells":
        from .ingest.base import build_cells
        with db.tx() as c:
            _print(build_cells(c))
    elif a.cmd == "recompute":
        _print(pipeline.run_recompute([{"tipo": "cli"}]))
    elif a.cmd == "sampling":
        _print(pipeline.run_sampling(a.matrix, a.k))
    elif a.cmd == "ingest":
        _print(jobs.ingest(a.source))
    elif a.cmd == "export-mapbiomas":
        from .ingest.mapbiomas_ee import export_mining_geojson
        _print(export_mining_geojson(a.out, a.desde))
    elif a.cmd == "load-worldpop":
        from .ingest.worldpop_ee import load_worldpop
        _print(load_worldpop(a.radio_m))
    elif a.cmd == "push":
        _print(jobs.send_push())
    elif a.cmd == "enqueue-recompute":
        from .worker.queue import request_recompute
        _print({"job": request_recompute("cron")})
    elif a.cmd == "rag-ingest":
        from .rag.ingest import ingest_dir
        _print(ingest_dir(a.path, a.force))
    elif a.cmd == "rag-ask":
        from .rag.chat import answer, zone_card
        from .rag.search import search
        with db.tx() as c:
            if a.solo_buscar:
                for h in search(c, a.pregunta, tema=a.tema):
                    print(f"\n[{h['score']:.4f}] {h['filename']} p.{h['page']} ({h['kind']})\n{h['content']}")
            else:
                r = answer(c, a.pregunta, tema=a.tema, zone=zone_card(c, a.lat, a.lon))
                print(r["respuesta"], "\n")
                for f in r["fuentes"]:
                    print(f"  [{f['n']}] {f['archivo']}" + (f" p. {f['pagina']}" if f["pagina"] else ""))
    elif a.cmd == "release-embargoes":
        _print(jobs.release_embargoes())
    elif a.cmd == "create-user":
        from .api.security import hash_password
        with db.tx() as c:
            _print(db.one(c, """INSERT INTO app_user (email, name, role, password_hash) VALUES (:e,:n,:r,:p)
                                RETURNING id, email, role""",
                          e=a.email, n=a.name, r=a.role, p=hash_password(a.password)))


if __name__ == "__main__":
    sys.exit(main())
