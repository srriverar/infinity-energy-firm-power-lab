"""Pruebas de los modelos científicos (ejecutar con:  pytest -q)."""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.economics import breakeven_capex, crf, firm_pv_bess, lcoe  # noqa: E402
from core.metrology import (analyze_timeseries, air_tank_exergy, decision, ratio_uncertainty,  # noqa: E402
                            required_windows, synthetic_test_dataset)
from core.physics import (COMPRESSION_MODES, CycleParams, DynParams, compression_work_ideal, cycle,  # noqa: E402
                          simulate_dynamics)
from core.reliability import (copt_identical, elcc_single_unit, exp_term_modular, exp_term_profile,  # noqa: E402
                              firm_capacity_identical, garver_elcc, modules_needed)
from core.ucf import (FirmModularResource, HydroRoRResource, NormalResource, PVResource, ThermalUnit,  # noqa: E402
                      UniformResource, WindResource, economic_dispatch)

RESOURCES = [PVResource(), WindResource(), HydroRoRResource(), NormalResource(), UniformResource(),
             FirmModularResource(N=1, P_m=50), FirmModularResource(N=20, P_m=2.5, A=0.9, cv=0.08)]


# ----------------------------------------------------------------------------- física
def test_buoyancy_equals_isothermal_work():
    for H in (1.0, 8.0, 30.0):
        r = cycle(CycleParams(H=H, T_w_C=25, T_a_C=25))
        assert math.isclose(r.W_buoy, r.W_iso_ref, rel_tol=1e-12)


def test_ideal_reversible_cycle_is_unity():
    p = CycleParams(compression="isotérmica", eta_comp=1, eta_motor=1, eta_cap=1, eta_gear=1, eta_gen=1, eta_pe=1, P_aux_W=0)
    assert math.isclose(cycle(p).ERR, 1.0, rel_tol=1e-12)


def test_closed_cycle_never_exceeds_one():
    rng = np.random.default_rng(0)
    for _ in range(2000):
        p = CycleParams(H=rng.uniform(0.5, 60), V0_L=rng.uniform(1, 200), f_ins=rng.uniform(0.1, 5),
                        compression=str(rng.choice(COMPRESSION_MODES)), n_poly=rng.uniform(1.0, 1.4),
                        eta_comp=rng.uniform(0.3, 1), eta_motor=rng.uniform(0.5, 1), eta_cap=rng.uniform(0.1, 1),
                        eta_gear=rng.uniform(0.5, 1), eta_gen=rng.uniform(0.5, 1), eta_pe=rng.uniform(0.5, 1),
                        P_aux_W=rng.uniform(0, 100))
        assert cycle(p).ERR <= 1.0 + 1e-12


def test_compression_ordering():
    # isotérmica ≤ politrópica ≤ adiabática
    w_iso = compression_work_ideal(1e5, 0.02, 2.0, "isotérmica")
    w_pol = compression_work_ideal(1e5, 0.02, 2.0, "politrópica", 1.2)
    w_ad = compression_work_ideal(1e5, 0.02, 2.0, "adiabática")
    assert w_iso < w_pol < w_ad


def test_thermal_hypothesis_bound():
    p = CycleParams(compression="isotérmica", eta_comp=1, eta_motor=1, eta_cap=1, eta_gear=1, eta_gen=1, eta_pe=1,
                    P_aux_W=0, T_w_C=60, T_a_C=25)
    r = cycle(p)
    assert math.isclose(r.ERR, (60 + 273.15) / (25 + 273.15), rel_tol=1e-9)


def test_dynamics_reach_steady_state_and_bound():
    r = cycle(CycleParams())
    out = simulate_dynamics(DynParams(E_ins_J=r.E_ins, T_sim=30.0))
    m = out["metrics"]
    assert 0 < m["omega_ss"] < 20
    assert 0 < m["ERR_ss"] < 1.0


# ----------------------------------------------------------------------------- UCF
@pytest.mark.parametrize("res", RESOURCES, ids=lambda r: f"{r.short}")
def test_ucf_analytic_matches_numeric(res):
    w = np.linspace(res.w_min, res.w_max, 15)
    a = res.ucf_total(w, 50.0, 300.0)
    u, o = res.ucf_numeric(w, 50.0, 300.0)
    assert np.max(np.abs(a - (u + o))) / max(np.max(np.abs(a)), 1e-9) < 1e-4


@pytest.mark.parametrize("res", RESOURCES, ids=lambda r: f"{r.short}")
def test_ucf_analytic_matches_monte_carlo(res):
    w = np.linspace(res.w_min, res.w_max, 9)
    a = res.ucf_total(w, 50.0, 300.0)
    u, o = res.ucf_mc(w, 50.0, 300.0, n=200_000, seed=3)
    assert np.max(np.abs(a - (u + o))) / max(np.max(np.abs(a)), 1e-9) < 0.02


@pytest.mark.parametrize("res", RESOURCES, ids=lambda r: f"{r.short}")
def test_optimum_is_critical_fractile_and_convex(res):
    cu, co = 50.0, 300.0
    ws, val, q = res.optimum(cu, co)
    assert res.cdf(ws)[0] >= q - 1e-6
    g = res.grid(600)
    U = res.ucf_total(g, cu, co)
    assert val <= U.min() + 1e-6 * max(1.0, abs(U.min())) + (g[1] - g[0]) * (cu + co)
    assert np.min(np.diff(U, 2)) > -1e-6 * max(1.0, np.max(np.abs(U)))


def test_modularity_reduces_uncertainty_cost():
    one = FirmModularResource(N=1, P_m=50, A=0.95, cv=0.03).optimum(50, 300)[1]
    many = FirmModularResource(N=100, P_m=0.5, A=0.95, cv=0.03).optimum(50, 300)[1]
    assert many < one


def test_economic_dispatch_balances_demand():
    th = [ThermalUnit("T1", 20, 150, 500, 150, 0.05), ThermalUnit("T2", 10, 120, 300, 190, 0.08),
          ThermalUnit("T3", 0, 273, 200, 230, 0.10)]
    ed = economic_dispatch(400, th, [(PVResource(), 5), (WindResource(), 5)], 50, 300)
    total = sum(P for _, P in ed["thermal"]) + sum(r["W_s"] for r in ed["renewables"])
    assert abs(total - 400) < 0.5
    assert ed["ens"] == 0


# ----------------------------------------------------------------------------- confiabilidad
def test_copt_sums_to_one():
    c = copt_identical(50, 0.93, 1.0)
    assert math.isclose(c["p"].sum(), 1.0, rel_tol=1e-12)


def test_firm_capacity_increases_with_modularity():
    assert firm_capacity_identical(100, 0.95, 0.5, 0.99) > firm_capacity_identical(1, 0.95, 50, 0.99)


def test_modules_needed_meets_target():
    n = modules_needed(100, 0.5, 0.95, 0.999)
    assert n >= 200


def test_garver_flat_perfect_unit_equals_capacity():
    load = 1000 + 300 * np.sin(np.linspace(0, 2 * np.pi, 96))
    m = 50.0
    assert math.isclose(garver_elcc(load, m, exp_term_profile(np.full(96, 80.0), m)), 80.0, rel_tol=1e-9)
    # unidad con FOR: coincide con la fórmula clásica
    e1 = garver_elcc(load, m, exp_term_modular(1, 80.0, 0.9, m, 96))
    assert math.isclose(e1, elcc_single_unit(80.0, 0.1, m), rel_tol=1e-9)


# ----------------------------------------------------------------------------- metrología
def test_ratio_uncertainty_correlation():
    assert ratio_uncertainty(0.2, 0.2, 1.0) == pytest.approx(0.0, abs=1e-12)
    assert ratio_uncertainty(0.3, 0.4, 0.0) == pytest.approx(0.5)


def test_decision_rule():
    assert decision(1.05, 0.01)["level"] == "success"
    assert decision(1.01, 0.01)["level"] == "warning"
    assert decision(0.90, 0.01)["level"] == "info"
    assert math.isinf(required_windows(0.01, 0.05, 0.01))


def test_constant_power_integration_and_storage_correction():
    t = np.arange(0, 3601, 1.0)
    df = pd.DataFrame({"t_s": t, "p_abis_w": 1000.0, "p_aux_w": 0.0, "p_out_w": 500.0})
    res = analyze_timeseries(df)
    assert res["E_in_kWh"] == pytest.approx(1.0, rel=1e-9)
    assert res["ERR_raw"] == pytest.approx(0.5, rel=1e-9)
    syn = synthetic_test_dataset()
    r2 = analyze_timeseries(syn, tank_L=500)
    assert r2["dE_stored_kWh"] < 0 and r2["ERR_corr"] < r2["ERR_raw"]
    assert air_tank_exergy(np.array([1.01325]), 500)[0] == pytest.approx(0.0, abs=1e-6)


# ----------------------------------------------------------------------------- economía
def test_crf_and_lcoe():
    assert crf(0.08, 25) == pytest.approx(0.093679, rel=1e-4)
    l = lcoe(691, 12, 0, 0.17, 0.06, 25)
    assert 35 < l < 55
    be = breakeven_capex(l, 12, 0, 0.17, 0.06, 25)
    assert be == pytest.approx(691, rel=1e-6)


def test_firm_pv_bess_overbuild():
    r = firm_pv_bess(100, 708, 150, 150, 0.88, 0.9, 0.0, 4.5, 0.08)
    assert 3.0 < r["ratio_pv_load"] < 8.0
    assert r["lcoe_firm"] > 40
