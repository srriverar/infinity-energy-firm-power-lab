"""
core/reliability.py
===================
Suficiencia (adequacy) y firmeza:
  * Tabla de probabilidades de capacidad (COPT) para N módulos idénticos (binomial)
    o un conjunto heterogéneo (convolución recursiva).
  * Capacidad firme a un nivel de confianza α: max{c : P(C_disp ≥ c) ≥ α}.
  * ELCC por la aproximación exponencial de Garver (IEEE Trans. PAS, 1966):
        ELCC = m · ln( Σ_t e^{(L_t−L_p)/m} / Σ_t e^{(L_t−L_p)/m} · E[e^{−X_t/m}] )
  * Disponibilidad de Markov de 2 estados: A = MTBF / (MTBF + MTTR).
"""
from __future__ import annotations

import math
import numpy as np
from scipy import stats


def availability(mtbf_h: float, mttr_h: float) -> float:
    return mtbf_h / (mtbf_h + mttr_h)


def copt_identical(N: int, A: float, P_m: float) -> dict:
    k = np.arange(N + 1)
    pk = stats.binom.pmf(k, N, A)
    cap = k * P_m
    exceed = stats.binom.sf(k - 1, N, A)   # P(K ≥ k)
    return {"k": k, "cap": cap, "p": pk, "p_exceed": exceed}


def copt_units(caps: list[float], fors: list[float], step: float = 1.0) -> dict:
    """COPT por convolución recursiva (unidades heterogéneas de 2 estados)."""
    n = int(round(sum(caps) / step)) + 1
    prob = np.zeros(n)
    prob[0] = 1.0                          # prob de capacidad DISPONIBLE = 0 al inicio
    total = 0
    for c, q in zip(caps, fors):
        ci = int(round(c / step))
        new = prob * q
        new[ci:] += prob[: n - ci] * (1 - q)
        prob = new
        total += ci
    cap = np.arange(n) * step
    exceed = prob[::-1].cumsum()[::-1]
    return {"cap": cap, "p": prob, "p_exceed": exceed}


def firm_capacity_identical(N: int, A: float, P_m: float, alpha: float) -> float:
    """Mayor capacidad c = k·P_m tal que P(K ≥ k) ≥ α."""
    k = np.arange(N + 1)
    ex = stats.binom.sf(k - 1, N, A)
    ok = k[ex >= alpha]
    return float(ok.max() * P_m) if ok.size else 0.0


def modules_needed(target_MW: float, P_m: float, A: float, alpha: float, n_max: int = 20000) -> int:
    """Mínimo N tal que P(capacidad disponible ≥ target) ≥ α."""
    k_req = int(math.ceil(target_MW / P_m - 1e-9))
    if k_req <= 0:
        return 0
    lo = k_req
    hi = max(k_req + 1, int(k_req / max(A, 1e-6) * 1.5) + 50)
    while stats.binom.sf(k_req - 1, hi, A) < alpha and hi < n_max:
        hi *= 2
    if stats.binom.sf(k_req - 1, hi, A) < alpha:
        return -1
    while lo < hi:
        mid = (lo + hi) // 2
        if stats.binom.sf(k_req - 1, mid, A) >= alpha:
            hi = mid
        else:
            lo = mid + 1
    return int(lo)


def garver_elcc(load: np.ndarray, m: float, exp_term: np.ndarray) -> float:
    """ELCC (MW) con la aproximación de Garver.

    load     : perfil de carga L_t (MW)
    m        : característica de riesgo de Garver (MW por e-veces de LOLE)
    exp_term : E[e^{−X_t/m}] del recurso en cada intervalo
    """
    L = np.asarray(load, float)
    Lp = L.max()
    w = np.exp((L - Lp) / m)
    num = np.sum(w)
    den = np.sum(w * np.asarray(exp_term, float))
    return float(m * math.log(num / den))


def exp_term_profile(profile_MW: np.ndarray, m: float) -> np.ndarray:
    return np.exp(-np.asarray(profile_MW, float) / m)


def exp_term_modular(N: int, P_m: float, A: float, m: float, n_t: int) -> np.ndarray:
    v = ((1 - A) + A * math.exp(-P_m / m)) ** N
    return np.full(n_t, v)


def elcc_single_unit(C: float, q: float, m: float) -> float:
    """Fórmula clásica de Garver para una unidad de capacidad C y FOR q."""
    return C - m * math.log((1 - q) + q * math.exp(C / m))


def pv_profile(h: np.ndarray, sunrise: float = 5.35, sunset: float = 17.9, cloud_pm: float = 0.25) -> np.ndarray:
    """Perfil FV normalizado sintético (por MW instalado) para Costa Rica en estación lluviosa.

    Campana senoidal entre salida y puesta del sol, con atenuación vespertina por nubosidad.
    """
    h = np.asarray(h, float)
    x = np.clip((h - sunrise) / (sunset - sunrise), 0, 1)
    base = np.sin(np.pi * x) ** 1.25
    att = 1 - cloud_pm * np.clip((h - 12.5) / 4.0, 0, 1)
    out = 0.82 * base * att
    out[(h <= sunrise) | (h >= sunset)] = 0
    return out
