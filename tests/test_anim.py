"""Pruebas de las animaciones: coherencia física/estadística de los datos que se envían
al navegador y compatibilidad del JavaScript con el saneamiento de st.html (DOMPurify)."""
import dataclasses
import math
import re
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.anim import cycle_animation_html  # noqa: E402
from core.anim_physics import (area_check, energy_flow_animation_html, energy_flow_params,  # noqa: E402
                               pv_cycle_animation_html, pv_cycle_params)
from core.anim_value import (QMAX, QMIN, fleet_animation_html, fleet_payload, sample_from_table,  # noqa: E402
                             ucf_stream_animation_html, ucf_stream_payload)
from core.physics import COMPRESSION_MODES, CycleParams, cycle  # noqa: E402
from core.reliability import firm_capacity_identical  # noqa: E402
from core.ucf import FirmModularResource, HydroRoRResource, PVResource, WindResource  # noqa: E402

STREAM_RES = [("Solar FV", "#F59E0B", PVResource()), ("Eólica", "#64748B", WindResource()),
              ("PCH filo de agua", "#3A49E0", HydroRoRResource()), ("IE (escenario)", "#0FA99A", FirmModularResource())]


def _script(html: str) -> str:
    m = re.search(r"<script>(.*)</script>", html, re.S)
    assert m, "la animación debe incluir un <script>"
    return m.group(1)


# ----------------------------------------------------------------------------- p–V
@pytest.mark.parametrize("mode", COMPRESSION_MODES)
@pytest.mark.parametrize("tw,ta", [(25.0, 25.0), (35.0, 15.0), (10.0, 30.0)])
def test_pv_areas_equal_model_work(mode, tw, ta):
    """Las áreas ∫V dp dibujadas son exactamente los trabajos del modelo."""
    p = dataclasses.replace(CycleParams(), compression=mode, T_w_C=tw, T_a_C=ta)
    r = cycle(p)
    P = pv_cycle_params(p, r)
    wc, wa = area_check(P)
    assert wc == pytest.approx(r.W_comp_ideal, rel=1e-4)
    assert wa == pytest.approx(r.W_buoy, rel=1e-4)
    assert P["ERRi"] == pytest.approx(r.W_buoy / r.W_comp_ideal, rel=1e-9)


def test_pv_states_consistent():
    p = dataclasses.replace(CycleParams(), compression="isotérmica", T_w_C=25, T_a_C=25)
    P = pv_cycle_params(p, cycle(p))
    assert P["V2"] == pytest.approx(P["V3"])          # sin intercambio térmico neto
    assert P["V4"] == pytest.approx(P["V0"])          # el ciclo cierra en el estado 1
    assert P["T2"] == pytest.approx(P["Ta"])
    pa = dataclasses.replace(p, compression="adiabática")
    Pa = pv_cycle_params(pa, cycle(pa))
    assert Pa["T2"] > Pa["Ta"] and Pa["V2"] > Pa["V3"]  # enfriamiento isobárico a profundidad


# ----------------------------------------------------------------------------- flujo de energía
@pytest.mark.parametrize("tw,ta", [(25.0, 25.0), (35.0, 15.0), (10.0, 30.0)])
def test_energy_flow_balance(tw, ta):
    p = dataclasses.replace(CycleParams(), T_w_C=tw, T_a_C=ta)
    r = cycle(p)
    E = energy_flow_params(p, r)
    losses = [E["Paux"], E["Pabis"] - E["Wc"], E["Wc"] - E["Wiso"], E["deficit"], E["Wb"] - E["Wmech"],
              E["Wmech"] - E["Wshaft"], E["Wshaft"] - E["Wgen"], E["Wgen"] - E["Wout"]]
    assert min(losses) >= -1e-9
    assert E["Pin"] + E["gain"] == pytest.approx(E["Wout"] + sum(losses), rel=1e-9)
    assert E["Wout"] == pytest.approx(r.P_out, rel=1e-9)
    assert E["Wiso"] + E["gain"] - E["deficit"] == pytest.approx(E["Wb"], rel=1e-9)


# ----------------------------------------------------------------------------- UCF en tiempo real
def test_ucf_stream_tables_reproduce_analytic_ucf():
    """Muestrear la tabla de cuantiles (como en el navegador) reproduce la UCF* analítica."""
    cu, co = 50.0, 300.0
    pay = ucf_stream_payload(STREAM_RES, cu, co)
    rng = np.random.default_rng(7)
    u = rng.uniform(0.0, 1.0, 400_000)
    for row in pay["res"]:
        w = sample_from_table(row, u, pay["qmin"], pay["qmax"])
        cost = np.where(w >= row["ws"], cu * (w - row["ws"]), co * (row["ws"] - w)).mean()
        assert cost == pytest.approx(row["ucf"], rel=0.03, abs=1.0), row["name"]
        assert w.mean() == pytest.approx(row["mean"], rel=0.01, abs=0.05), row["name"]


def test_ucf_stream_histograms_are_distributions():
    pay = ucf_stream_payload(STREAM_RES, 50.0, 300.0)
    assert pay["q"] == pytest.approx(50 / 350)
    assert (pay["qmin"], pay["qmax"]) == (QMIN, QMAX)
    for row in pay["res"]:
        assert sum(row["hist"]) == pytest.approx(1.0, abs=1e-4)
        assert min(row["hist"]) >= 0
        assert np.all(np.diff(row["qt"]) >= -1e-9)      # cuantiles no decrecientes
        assert 0 <= row["ws"] <= pay["cap"] + 1e-9


# ----------------------------------------------------------------------------- flota
def test_fleet_payload_theory():
    f = fleet_payload(100, 0.95, 50.0, 0.99)
    assert f["fc"] == pytest.approx(firm_capacity_identical(100, 0.95, 0.5, 0.99))
    assert f["assumed"] and f["mttr"] == 48.0
    assert f["mtbf"] / (f["mtbf"] + f["mttr"]) == pytest.approx(0.95)
    assert f["pM"] >= 0.99 - 1e-12                       # la definición de capacidad firme
    assert f["pO"] == pytest.approx(0.95)
    one = fleet_payload(1, 0.95, 50.0, 0.99)              # una unidad no garantiza nada al 99 %
    assert one["fc"] == 0 and one["pM"] == 1.0 and one["pO"] == 1.0
    g = fleet_payload(20, 0.9, 40.0, 0.95, mtbf=900.0, mttr=100.0)
    assert not g["assumed"] and g["mtbf"] == 900.0 and g["win"] == pytest.approx(20 * g["hps"])


# ----------------------------------------------------------------------------- saneamiento DOMPurify
def _all_html():
    p = CycleParams()
    r = cycle(p)
    return {
        "pv": pv_cycle_animation_html(pv_cycle_params(p, r)),
        "ef": energy_flow_animation_html(energy_flow_params(p, r)),
        "ucf": ucf_stream_animation_html(ucf_stream_payload(STREAM_RES, 50.0, 300.0)),
        "fleet": fleet_animation_html(fleet_payload(100, 0.95, 50.0, 0.99)),
        "demo": cycle_animation_html({"H": 8.0, "V0_L": 20.0, "f_ins": 1.0, "P_out": 681.0, "ERR": 0.363}),
    }


def test_scripts_survive_dompurify():
    """DOMPurify elimina un <script> cuyo texto contenga '<' seguido de letra o '/'."""
    for name, html in _all_html().items():
        js = _script(html)
        assert not re.search(r"<[\w/]", js), name
        assert not re.search(r"__(PARAMS|JSLIB|BOOT|CID|UID)__", html), name


def test_canvas_ids_unique_and_placeholders_replaced():
    htmls = _all_html()
    ids = []
    for name, html in htmls.items():
        if name == "demo":
            continue
        assert "__PARAMS__" not in html and "__JSLIB__" not in html and "__BOOT__" not in html and "__CID__" not in html
        m = re.search(r'<canvas id="([\w]+)"', html)
        assert m, name
        ids.append(m.group(1))
        assert f"getElementById('{m.group(1)}')" in html
    assert len(ids) == len(set(ids))
