import math

import numpy as np
import pytest

from rastrohg.engine import emissions, fish, kriging, pressure, risk, sampling, units
from rastrohg.engine.network import Reach, RiverNetwork
from rastrohg.engine.params import params


@pytest.fixture(scope="module")
def cfg():
    return params()


@pytest.fixture()
def net():
    """Dos tributarios (A: 1→2→3, B: 10→11) que se juntan en 4 → 5 → 6.

        1 → 2 → 3 ┐
                  4 → 5 → 6
        10 → 11 ──┘
    """
    def r(i, nd, area, q):
        return Reach(i, nd, 10.0, area, q)
    return RiverNetwork([
        r(1, 2, 50, 1), r(2, 3, 100, 2), r(3, 4, 150, 3),
        r(10, 11, 60, 1), r(11, 4, 120, 2),
        r(4, 5, 300, 6), r(5, 6, 320, 7), r(6, 0, 340, 8),
    ])


def test_downstream_y_conectividad(net):
    assert [x for x, _ in net.downstream(2)] == [2, 3, 4, 5, 6]
    assert net.downstream(2)[1][1] == pytest.approx(10.0)
    conn = net.flow_connected(2, 100)
    assert 1 in conn and 6 in conn
    assert 10 not in conn and 11 not in conn  # otro tributario: no conectado por el flujo


def test_emisiones_rango_y_determinismo(cfg):
    a = emissions.estimate_site(emissions.SiteInput(7, 20.0), cfg)
    b = emissions.estimate_site(emissions.SiteInput(7, 20.0), cfg)
    assert a.hg_total_p50 == b.hg_total_p50
    assert a.hg_total_p05 < a.hg_total_p50 < a.hg_total_p95
    assert 0 < a.hg_agua_p50 < a.hg_total_p50
    inactivo = emissions.estimate_site(emissions.SiteInput(7, 20.0, activo=False), cfg)
    assert inactivo.hg_total_p50 == pytest.approx(a.hg_total_p50 * cfg["emisiones"]["factor_inactivo"])


def test_presion_solo_rio_abajo(net):
    p = pressure.compute_pressure(net, [pressure.SiteLoad(1, 2, 10.0, 1.0)], L_km=30)
    assert p[1] == 0 and p[10] == 0 and p[11] == 0
    assert p[2] == pytest.approx(10.0)
    assert p[3] == pytest.approx(10.0 * math.exp(-10 / 30))
    assert p[2] > p[3] > p[4] > p[5] > p[6] > 0
    p_denuncia = pressure.compute_pressure(net, [pressure.SiteLoad(1, 2, 10.0, 0.2)], L_km=30)
    assert p_denuncia[3] == pytest.approx(0.2 * p[3])


def _kr(net, cfg, matrix, sites):
    p = pressure.compute_pressure(net, sites, cfg["matrices"][matrix]["decaimiento_L_km"])
    X = kriging.design_matrix(net, p, cfg["matrices"][matrix])
    return kriging.NetworkKriging(net, kriging.MatrixModel.from_cfg(matrix, cfg), X)


def test_kriging_sin_datos_es_el_prior(net, cfg):
    kr = _kr(net, cfg, "agua", [pressure.SiteLoad(1, 2, 50.0, 1.0)]).fit([])
    pr = kr.predict()
    i = net.index
    # Sin minería río arriba: mediana = fondo
    assert math.exp(pr.log_mu[i[10]]) == pytest.approx(cfg["matrices"]["agua"]["fondo"])
    # Con minería: más alto que el fondo
    assert pr.log_mu[i[2]] > pr.log_mu[i[10]]
    assert (pr.log_sd > 0.5).all()  # sin datos: incertidumbre grande


def test_kriging_dato_reduce_incertidumbre_solo_en_red_conectada(net, cfg):
    kr = _kr(net, cfg, "agua", [])
    sd0 = kr.fit([]).predict().log_sd
    pr = kr.fit([kriging.Observation(2, 0.05, 1.0, s=0.0)]).predict()   # promedio anual conocido
    i = net.index
    assert pr.log_sd[i[2]] < sd0[i[2]] * 0.5
    assert pr.log_mu[i[2]] == pytest.approx(math.log(0.05), abs=0.1)
    # El tributario B no está conectado: su residuo no cambia (solo el β global)
    assert pr.n_cercanos[i[10]] == 0
    assert pr.log_sd[i[10]] > pr.log_sd[i[3]]


def test_kit_pesa_menos_que_laboratorio(net, cfg):
    kr = _kr(net, cfg, "agua", [])
    lab = kr.fit([kriging.Observation(2, 0.05, 1.0)]).predict().log_sd[net.index[2]]
    kit = kr.fit([kriging.Observation(2, 0.05, 0.5)]).predict().log_sd[net.index[2]]
    assert kit > lab


def test_muestreo_prefiere_donde_no_hay_datos_y_hay_gente(net, cfg):
    kr = _kr(net, cfg, "agua", [pressure.SiteLoad(1, 1, 30.0, 1.0)])
    kr.fit([kriging.Observation(2, 0.05, 1.0), kriging.Observation(3, 0.04, 1.0)])
    pesos = {rid: 1.0 for rid in net.ids}
    pesos[11] = 50.0   # mucha gente en el tributario B, sin datos
    sug = sampling.suggest_points(kr, list(net.ids), pesos, k=3)
    assert len(sug) == 3
    assert sug[0].reach_id in (10, 11)
    assert len({s.reach_id for s in sug}) == 3
    assert len(kr.obs) == 2  # no deja observaciones virtuales


def test_riesgo_media_geometrica_y_confianza(cfg):
    fuerte = risk.CellInput("87283082bffffff", 0.9, 0.8,
                            [risk.HazardSource("agua", 1, math.log(10.0), 0.1)])
    r = risk.compute_cell(fuerte, cfg)
    assert r.risk_class == "alto" and r.confidence > 0.9 and not r.palida
    dudosa = risk.CellInput("87283082bffffff", 0.9, 0.8,
                            [risk.HazardSource("agua", 1, math.log(1.0), 2.0)])
    d = risk.compute_cell(dudosa, cfg)
    assert d.confidence < r.confidence
    sin_gente = risk.CellInput("87283082bffffff", 0.0, 0.8,
                               [risk.HazardSource("agua", 1, math.log(10.0), 0.1)])
    assert risk.compute_cell(sin_gente, cfg).risk == 0
    assert risk.compute_cell(fuerte, cfg) == r  # determinista
    fondo = risk.CellInput("87283082bffffff", 0.9, 0.8,
                           [risk.HazardSource("pez", 1, math.log(cfg["matrices"]["pez"]["fondo"]), 0.1)])
    assert risk.compute_cell(fondo, cfg).risk_class == "bajo"   # sin minería, no hay alarma


def test_indices(cfg):
    assert risk.hazard_index(math.log(1.0), 1.0, 0.01) == pytest.approx(0.5)
    assert risk.hazard_index(math.log(10.0), 1.0, 0.01) == pytest.approx(1.0)
    assert risk.hazard_index(math.log(0.01), 1.0, 0.01) == pytest.approx(0.0)
    assert risk.hazard_index(math.log(0.1), 1.0, 0.01) == pytest.approx(0.25)
    assert 0 < risk.exposure_index(100, 1, 0, cfg) < 1
    v = risk.vulnerability_index(100, 15, 25, 7, cfg)
    assert v == pytest.approx(1.0)
    assert risk.vulnerability_index(0, 0, 0, None, cfg) >= cfg["riesgo"]["vulnerabilidad"]["piso"]


def test_consejo_pescado(cfg):
    especies = [{"codigo": "surubi", "nombre": "Surubí", "grupo": "carnivoro"},
                {"codigo": "pacu", "nombre": "Pacú", "grupo": "herbivoro"}]
    adv = fish.fish_advice(math.log(1.0), 0.3, especies, cfg)
    por = {a["codigo"]: a for a in adv}
    assert por["surubi"]["consejo"] == "evitar"
    assert por["pacu"]["consejo"] in ("comer", "limitar")
    assert por["pacu"]["comidas_semana_nino"] > por["surubi"]["comidas_semana_nino"]


def test_unidades():
    assert units.to_canonical("agua", 500, "ng/L") == pytest.approx(0.5)
    assert units.to_canonical("pez", 300, "ng/g") == pytest.approx(0.3)
    with pytest.raises(ValueError):
        units.to_canonical("agua", 1, "mg/kg")


def test_ajuste_hiperparametros_no_rompe(net, cfg):
    kr = _kr(net, cfg, "agua", [])
    rng = np.random.default_rng(0)
    obs = [kriging.Observation(int(r), float(rng.lognormal(-4, 0.5)), 1.0) for r in rng.choice(net.ids, 12)]
    m = kriging.fit_hyperparameters(net, kr.model, kr.X, obs, cfg)
    assert m.range_km in cfg["ajuste"]["rangos_km"]


def test_calibracion_congelada_mina_nueva_solo_cambia_rio_abajo(net, cfg):
    """Con la covariable de los datos congelada, una mina nueva en el tramo 10 (tributario B)
    cambia SOLO 10, 11, 4, 5, 6; el tributario A (1, 2, 3) queda idéntico."""
    obs_raw = [(2, 0.05), (5, 0.02)]
    kr0 = _kr(net, cfg, "agua", [pressure.SiteLoad(1, 1, 20.0, 1.0)])
    us = {r: kr0.X[net.index[r], 1] for r, _ in obs_raw}
    obs = [kriging.Observation(r, v, 1.0, u=us[r]) for r, v in obs_raw]
    p0 = kr0.fit(obs).predict()
    kr1 = _kr(net, cfg, "agua", [pressure.SiteLoad(1, 1, 20.0, 1.0), pressure.SiteLoad(2, 10, 50.0, 1.0)])
    p1 = kr1.fit(obs).predict()
    cambiados = {rid for rid, i in net.index.items() if abs(p1.log_mu[i] - p0.log_mu[i]) > 1e-9}
    assert cambiados == {10, 11, 4, 5, 6}


def test_bajo_ld_alto_no_contamina_el_mapa(net, cfg):
    """LD = 1 µg/L (200× el fondo): antes se usaba LD/2 = 0,5 µg/L y el río salía contaminado."""
    kr = _kr(net, cfg, "agua", [])
    base = kr.fit([]).predict().log_mu[net.index[2]]
    p = kr.fit([kriging.Observation(2, 1.0, 1.0, below_dl=True)]).predict()
    assert kr.n_censurados_ignorados == 1
    assert p.log_mu[net.index[2]] == pytest.approx(base)


def test_bajo_ld_informativo_baja_la_estimacion(net, cfg):
    kr = _kr(net, cfg, "agua", [pressure.SiteLoad(1, 1, 200.0, 1.0)])
    base = kr.fit([]).predict().log_mu[net.index[2]]
    p = kr.fit([kriging.Observation(2, 0.002, 1.0, below_dl=True)]).predict()   # LD 2 ng/L
    assert kr.n_censurados_ignorados == 0
    assert p.log_mu[net.index[2]] < base
    assert math.exp(p.log_mu[net.index[2]]) < 0.002 * 3


def test_estacion_humeda_se_corrige_al_promedio(net, cfg):
    kr = _kr(net, cfg, "agua", [])
    assert kr.model.seasonal and kr.X.shape[1] == 3
    f = cfg["matrices"]["agua"]["efecto_estacion"]["factor"]
    hum = kr.fit([kriging.Observation(2, 0.08, 1.0, s=0.5)]).predict().log_mu[net.index[2]]
    sec = kr.fit([kriging.Observation(2, 0.08, 1.0, s=-0.5)]).predict().log_mu[net.index[2]]
    assert hum < sec                         # el mismo valor en crecida implica un promedio menor
    assert sec - hum == pytest.approx(math.log(f), rel=0.35)
    sd_conocida = kr.fit([kriging.Observation(2, 0.08, 1.0, s=0.5)]).predict().log_sd[net.index[2]]
    sd_descon = kr.fit([kriging.Observation(2, 0.08, 1.0, s=None)]).predict().log_sd[net.index[2]]
    assert sd_descon > sd_conocida
    assert not _kr(net, cfg, "sedimento", []).model.seasonal


def test_peso_por_antiguedad():
    from datetime import date
    from rastrohg.engine.weights import age_factor
    hoy = date(2026, 11, 25)
    assert age_factor(date(2026, 11, 25), 5, hoy) == pytest.approx(1.0)
    assert age_factor(date(2021, 11, 25), 5, hoy) == pytest.approx(0.5, rel=0.01)
    assert age_factor(date(1995, 7, 1), 15, hoy) == pytest.approx(0.24, abs=0.01)
    assert age_factor(None, 5, hoy) == 1.0


def test_anclaje_prefiere_cauce_principal():
    from rastrohg.ingest.base import choose_reach
    kaka_p9 = [{"hyriv_id": 1, "d": 221, "upland_skm": 13}, {"hyriv_id": 2, "d": 480, "upland_skm": 21440},
               {"hyriv_id": 3, "d": 900, "upland_skm": 60000}]
    assert choose_reach(kaka_p9)["hyriv_id"] == 2          # el Beni a 900 m queda fuera del margen
    arroyo = [{"hyriv_id": 1, "d": 30, "upland_skm": 40}, {"hyriv_id": 2, "d": 1500, "upland_skm": 21440}]
    assert choose_reach(arroyo)["hyriv_id"] == 1           # muestra de un arroyo real: lejos del río grande
    assert choose_reach([{"hyriv_id": 1, "d": 2500, "upland_skm": 10}]) is None


def test_nugget_se_ajusta_con_replicas_dispersas(net, cfg):
    """5 años en el mismo tramo con 20× de diferencia: el ajuste debe ver variabilidad temporal."""
    kr = _kr(net, cfg, "sedimento", [])
    obs = [kriging.Observation(2, v, 1.0) for v in (0.021, 0.088, 0.214, 0.433, 0.168)] + \
          [kriging.Observation(r, 0.07, 1.0) for r in (1, 3, 4, 5, 6, 10)]
    m = kriging.fit_hyperparameters(net, kr.model, kr.X, obs, cfg)
    assert m.nugget >= 0.5
    sd = kriging.NetworkKriging(net, m, kr.X).fit(obs).predict().log_sd[net.index[2]]
    sd_sin = kriging.NetworkKriging(net, kriging.MatrixModel(m.name, m.sigma2, m.range_km, m.noise_lab,
                                    m.beta_mean, m.beta_cov, 0.0), kr.X).fit(obs).predict().log_sd[net.index[2]]
    assert sd > sd_sin


def test_censurados_ignorados_no_disparan_ajuste(net, cfg):
    kr = _kr(net, cfg, "agua", [])
    obs = [kriging.Observation(r, 1.0, 1.0, below_dl=True) for r in net.ids] * 2   # 16 "< 1 µg/L"
    m = kriging.fit_hyperparameters(net, kr.model, kr.X, obs, cfg)
    assert m.sigma2 == cfg["matrices"]["agua"]["sigma2"] and m.range_km == cfg["matrices"]["agua"]["rango_km"]


def test_species_factor_override_and_note():
    from rastrohg.engine.fish import fish_advice
    from rastrohg.engine.params import load_yaml, params

    peces = {p["codigo"]: p for p in fish_advice(-0.5, 0.3, load_yaml("fish_species.yaml")["especies"], params())}
    assert peces["yatorana"]["mg_kg_p50"] == peces["pacu"]["mg_kg_p50"]          # UMSA-WCS: baja, como el pacú
    assert peces["yatorana"]["mg_kg_p50"] > 0 and "no es cero" in peces["yatorana"]["nota"]
    assert "nota" not in peces["surubi"]
