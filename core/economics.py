"""
core/economics.py
=================
Tecno-economía paramétrica: LCOE, LCOE firme (FV + BESS), costo de incertidumbre
nivelado (desde las UCF), CAPEX de equilibrio y emisiones evitadas.

Todos los parámetros de Infinity Energy son SUPUESTOS DE ESCENARIO: la empresa
indica que capacidades, costos y precios se definirán tras validar los MVP.
"""
from __future__ import annotations

import math
import numpy as np

from .reliability import pv_profile


def crf(r: float, n: int) -> float:
    """Factor de recuperación de capital."""
    if r <= 0:
        return 1.0 / n
    return r * (1 + r) ** n / ((1 + r) ** n - 1)


def lcoe(capex_kw: float, fom_kw_yr: float, vom_mwh: float, cf: float, r: float, n: int,
         fuel_mwh: float = 0.0) -> float:
    """LCOE [USD/MWh]."""
    mwh_per_kw = 8.76 * max(cf, 1e-6)
    return (capex_kw * crf(r, n) + fom_kw_yr) / mwh_per_kw + vom_mwh + fuel_mwh


def breakeven_capex(target_mwh: float, fom_kw_yr: float, vom_mwh: float, cf: float, r: float, n: int,
                    adders_mwh: float = 0.0) -> float:
    """CAPEX [USD/kW] para el cual LCOE + adders = objetivo."""
    margin = target_mwh - vom_mwh - adders_mwh
    return (margin * 8.76 * cf - fom_kw_yr) / crf(r, n)


# Referencias públicas (valores globales promedio ponderado, USD 2024; IRENA 2025 / 2026)
BENCHMARKS = [
    {"tecnologia": "Eólica terrestre", "capex": 1041, "cf": 0.34, "lcoe": 34, "firme": False,
     "fuente": "IRENA, Renewable Power Generation Costs in 2024 (2025)"},
    {"tecnologia": "Solar FV (escala red)", "capex": 691, "cf": 0.17, "lcoe": 43, "firme": False,
     "fuente": "IRENA, Renewable Power Generation Costs in 2024 (2025)"},
    {"tecnologia": "Hidroeléctrica", "capex": 2267, "cf": 0.48, "lcoe": 57, "firme": True,
     "fuente": "IRENA, Renewable Power Generation Costs in 2024 (2025)"},
    {"tecnologia": "Geotermia", "capex": 4015, "cf": 0.88, "lcoe": 60, "firme": True,
     "fuente": "IRENA, Renewable Power Generation Costs in 2024 (2025)"},
    {"tecnologia": "FV + BESS firme 24/7 (95 %) — mejores sitios", "capex": None, "cf": None, "lcoe": 54,
     "lcoe_hi": 82, "firme": True, "fuente": "IRENA, 24/7 renewables: the economics of firm solar and wind (2026)"},
]

# Térmica de alquiler en Costa Rica (contrato 2027–2029: ~USD 320 M, 273 MW, 30 meses de operación)
CR_RENTAL = {"usd": 320e6, "mw": 273.0, "years": 2.5}


def cr_rental_capacity_cost() -> float:
    """USD/kW-año implícito del arrendamiento térmico (sin combustible)."""
    return CR_RENTAL["usd"] / (CR_RENTAL["mw"] * 1000 * CR_RENTAL["years"])


def thermal_cost_mwh(cf: float, capacity_kw_yr: float, fuel_mwh: float) -> float:
    return capacity_kw_yr / (8.76 * max(cf, 1e-6)) + fuel_mwh


def firm_pv_bess(load_MW: float, pv_capex_kw: float, bess_capex_kwh: float, bess_power_kw: float,
                 eta_rt: float, dod: float, autonomy_days: float, yield_kwh_kwp_day: float,
                 r: float, n_pv: int = 25, n_bess: int = 15, fom_pct: float = 0.015,
                 dt_h: float = 0.25) -> dict:
    """Dimensionamiento simplificado FV+BESS para suministro plano 24/7 (régimen diario periódico).

    - El perfil FV sintético se escala al rendimiento diario indicado (kWh/kWp·día).
    - Se elige la potencia FV mínima que, con el excedente almacenado (η_rt), cubre la noche.
    - Se añade energía de autonomía para días nublados (autonomy_days × consumo diario).
    Es una cota de referencia; IRENA (2026) reporta LCOE firme 54–82 USD/MWh en sitios de alto recurso.
    """
    h = np.arange(0, 24, dt_h)
    prof = pv_profile(h)
    prof = prof / (prof.sum() * dt_h) * yield_kwh_kwp_day       # kW por kWp
    L = load_MW

    def balance(P):
        gen = P * prof
        direct = np.minimum(gen, L).sum() * dt_h
        surplus = np.maximum(gen - L, 0).sum() * dt_h
        need = L * 24 - direct
        return surplus * eta_rt - need, need

    lo, hi = 0.0, L * 40
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        b, _ = balance(mid)
        if b < 0:
            lo = mid
        else:
            hi = mid
    P_pv = hi
    _, night_need = balance(P_pv)
    E_bess = (night_need / math.sqrt(eta_rt) + autonomy_days * L * 24) / dod     # MWh
    # sobredimensionamiento FV para recargar la autonomía en ~5 días
    extra_pv = (autonomy_days * L * 24 / eta_rt) / (5 * yield_kwh_kwp_day) if autonomy_days > 0 else 0.0
    P_pv_tot = P_pv + extra_pv
    capex_pv = P_pv_tot * 1000 * pv_capex_kw
    capex_bess = E_bess * 1000 * bess_capex_kwh + L * 1000 * bess_power_kw
    ann = capex_pv * (crf(r, n_pv) + fom_pct) + capex_bess * (crf(r, n_bess) + fom_pct)
    E_year = L * 8760
    return {"P_pv_MW": P_pv_tot, "E_bess_MWh": E_bess, "capex_total_musd": (capex_pv + capex_bess) / 1e6,
            "lcoe_firm": ann / E_year, "ratio_pv_load": P_pv_tot / L, "hours_storage": E_bess / L}


def co2_avoided_t(mwh: float, ef_t_mwh: float = 0.70) -> float:
    return mwh * ef_t_mwh
