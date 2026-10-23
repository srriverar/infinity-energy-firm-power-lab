"""
core/metrology.py
=================
Metrología del balance energético del MVP (enfoque GUM, JCGM 100:2008).

Magnitud de interés (frontera completa):
    ERR = E_salida_útil / (E_ABIS + E_aux − ΔE_almacenada)
    con ΔE_almacenada = E_alm(fin) − E_alm(inicio)  (tanques de aire, volantes,
    baterías, niveles de agua...). La energía extraída de almacenamientos se
    contabiliza como ENTRADA.

Incertidumbre relativa combinada del cociente:
    (u_ERR/ERR)² = u_o² + u_i² − 2·r·u_o·u_i   (r: correlación entre canales)
Incertidumbre expandida: U = k·u_c (k = 2 ≈ 95 %).
Regla de decisión (aceptación protegida): se declara ERR > 1 solo si ERR − U > 1.
"""
from __future__ import annotations

import io
import math
import numpy as np
import pandas as pd
from scipy import stats

_trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")

# Especificaciones típicas (límites de error; se asume distribución rectangular → u = a/√3)
METERS = {
    "Analizador de potencia de precisión (±0,05 %)": 0.05,
    "Analizador de potencia (±0,1 %)": 0.10,
    "Medidor de energía clase 0,2S (IEC 62053-22)": 0.20,
    "Medidor de energía clase 0,5S (IEC 62053-22)": 0.50,
    "Medidor clase 1 (IEC 62053-21)": 1.00,
    "Vatímetro/pinza portátil (±2,5 %)": 2.50,
}
# Transformadores de corriente IEC 61869-2 (error de relación %, desplazamiento de fase en minutos, a In)
CTS = {
    "Sin TC (medición directa / shunt calibrado)": (0.0, 0.0),
    "TC clase 0,1": (0.1, 5.0),
    "TC clase 0,2S": (0.2, 10.0),
    "TC clase 0,5": (0.5, 30.0),
    "TC clase 1": (1.0, 60.0),
}
VTS = {
    "Sin TT (medición directa)": (0.0, 0.0),
    "TT clase 0,2": (0.2, 10.0),
    "TT clase 0,5": (0.5, 20.0),
}


def channel_uncertainty(meter: str, ct: str, vt: str, pf: float, extra_pct: float = 0.0) -> dict:
    """Incertidumbre estándar relativa (%) de la energía medida en un canal."""
    a_m = METERS[meter]
    a_ct, ph_ct = CTS[ct]
    a_vt, ph_vt = VTS[vt]
    pf = float(np.clip(pf, 0.05, 1.0))
    tanphi = math.sqrt(max(1 - pf * pf, 0)) / pf
    ph_err = (ph_ct + ph_vt) / 60.0 * math.pi / 180.0 * tanphi * 100.0   # % de P
    comps = {
        "Medidor": a_m / math.sqrt(3),
        "TC (relación)": a_ct / math.sqrt(3),
        "TT (relación)": a_vt / math.sqrt(3),
        "Desfase TC/TT × tanφ": ph_err / math.sqrt(3),
        "Armónicos / ancho de banda / otros": extra_pct / math.sqrt(3),
    }
    u = math.sqrt(sum(v * v for v in comps.values()))
    return {"u_pct": u, "components": comps}


def ratio_uncertainty(u_out_pct: float, u_in_pct: float, corr: float = 0.0) -> float:
    v = u_out_pct ** 2 + u_in_pct ** 2 - 2 * corr * u_out_pct * u_in_pct
    return math.sqrt(max(v, 0.0))


def n_effective(x: np.ndarray) -> float:
    """Tamaño de muestra efectivo con autocorrelación de orden 1."""
    x = np.asarray(x, float)
    n = len(x)
    if n < 4:
        return float(n)
    xc = x - x.mean()
    den = float(np.sum(xc * xc))
    if den <= 0:
        return float(n)
    r1 = float(np.sum(xc[1:] * xc[:-1]) / den)
    r1 = min(max(r1, -0.95), 0.95)
    return float(max(2.0, n * (1 - r1) / (1 + r1)))


def decision(err: float, u_c_abs: float, k: float = 2.0, threshold: float = 1.0) -> dict:
    U = k * u_c_abs
    p_gt = float(stats.norm.sf((threshold - err) / u_c_abs)) if u_c_abs > 0 else float(err > threshold)
    if err - U > threshold:
        verdict = "ERR > 1 demostrado con la confianza elegida (requiere réplica independiente)"
        level = "success"
    elif err + U < threshold:
        verdict = "ERR < 1 con la confianza elegida (sin excedente neto en la frontera medida)"
        level = "info"
    else:
        verdict = "No concluyente: el intervalo de incertidumbre contiene ERR = 1"
        level = "warning"
    return {"U": U, "lower": err - U, "upper": err + U, "P(ERR>1)": p_gt, "verdict": verdict, "level": level}


def required_windows(delta: float, sigma_w: float, u_b: float, alpha: float = 0.05, power: float = 0.8) -> float:
    """Ventanas necesarias para detectar ERR = 1 + δ (δ absoluto) frente a H0: ERR ≤ 1.

    u(n) = sqrt(σ_w²/n + u_B²) ;  se requiere δ ≥ (z_{1−α} + z_{1−β})·u(n).
    Devuelve inf si la incertidumbre tipo B por sí sola impide la detección.
    """
    z = stats.norm.ppf(1 - alpha) + stats.norm.ppf(power)
    lim = (delta / z) ** 2 - u_b ** 2
    if lim <= 0:
        return float("inf")
    return float(math.ceil(sigma_w ** 2 / lim))


def air_tank_exergy(p_bar_abs: np.ndarray, V_L: float, p0_bar: float = 1.01325) -> np.ndarray:
    """Exergía isotérmica de un depósito de aire comprimido [J]: V·[p·ln(p/p0) − (p − p0)]."""
    p = np.maximum(np.asarray(p_bar_abs, float), p0_bar) * 1e5
    p0 = p0_bar * 1e5
    return (V_L / 1000.0) * (p * np.log(p / p0) - (p - p0))


def flywheel_energy(rpm: np.ndarray, J: float) -> np.ndarray:
    w = np.asarray(rpm, float) * 2 * math.pi / 60.0
    return 0.5 * J * w * w


# ----------------------------------------------------------------------------
# Simulación de campañas (diseño del ensayo)
# ----------------------------------------------------------------------------
def simulate_campaign(true_err: float, P_in_W: float, hours: float, window_min: float,
                      sigma_w_pct: float, u_in_pct: float, u_out_pct: float, corr: float,
                      E_stored_kWh: float, tau_min: float, measure_storage: bool, seed: int = 3) -> pd.DataFrame:
    """Campaña sintética por ventanas: sesgos de instrumento fijos + variabilidad de proceso
    + liberación de energía almacenada (decaimiento exponencial) no medida o medida."""
    rng = np.random.default_rng(seed)
    n = max(3, int(hours * 60 / window_min))
    dt_h = window_min / 60.0
    t_end = (np.arange(n) + 1) * window_min
    E_in_true = P_in_W * dt_h / 1000.0 * (1 + 0.01 * rng.standard_normal(n))       # kWh
    E_out_true = true_err * E_in_true * (1 + sigma_w_pct / 100.0 * rng.standard_normal(n))
    # sesgos sistemáticos (rectangulares dentro de ±√3·u), correlacionados
    z1, z2 = rng.uniform(-1, 1, 2)
    z2 = corr * z1 + math.sqrt(max(1 - corr * corr, 0)) * z2
    b_in = math.sqrt(3) * u_in_pct / 100.0 * z1
    b_out = math.sqrt(3) * u_out_pct / 100.0 * z2
    # energía almacenada liberada hacia la salida
    t0 = t_end - window_min
    released = E_stored_kWh * (np.exp(-t0 / tau_min) - np.exp(-t_end / tau_min)) if tau_min > 0 else np.zeros(n)
    E_in_m = E_in_true * (1 + b_in)
    E_out_m = (E_out_true + released) * (1 + b_out)
    E_in_corr = E_in_m + (released if measure_storage else 0.0)
    df = pd.DataFrame({
        "t_min": t_end,
        "E_in_kWh": E_in_m,
        "E_out_kWh": E_out_m,
        "E_liberada_kWh": released,
        "ERR_ventana": E_out_m / E_in_m,
    })
    df["ERR_acum_bruto"] = df["E_out_kWh"].cumsum() / df["E_in_kWh"].cumsum()
    df["ERR_acum_corr"] = df["E_out_kWh"].cumsum() / np.cumsum(E_in_corr)
    # incertidumbre acumulada (tipo A de ventanas + tipo B)
    errs = (df["E_out_kWh"] / E_in_corr).to_numpy()
    lo, hi = [], []
    for i in range(n):
        x = errs[: i + 1]
        m = float(df["ERR_acum_corr"].iloc[i])
        if i >= 2:
            neff = n_effective(x)
            uA = float(np.std(x, ddof=1)) / math.sqrt(neff)
        else:
            uA = abs(m) * sigma_w_pct / 100.0
        uB = abs(m) * ratio_uncertainty(u_out_pct, u_in_pct, corr) / 100.0
        uc = math.sqrt(uA * uA + uB * uB)
        lo.append(m - 2 * uc)
        hi.append(m + 2 * uc)
    df["IC95_inf"] = lo
    df["IC95_sup"] = hi
    return df


# ----------------------------------------------------------------------------
# Análisis de datos medidos (CSV)
# ----------------------------------------------------------------------------
TEMPLATE_COLUMNS = {
    "t_s": "tiempo [s] desde el inicio (o use 'timestamp' ISO 8601)",
    "p_abis_w": "potencia activa de entrada al ABIS [W] (obligatoria)",
    "p_aux_w": "potencia activa de auxiliares: CMS, sensores, bombas [W] (opcional)",
    "p_out_w": "potencia activa útil entregada por la PDU [W] (obligatoria)",
    "p_tank_bar_abs": "presión absoluta del depósito de aire [bar] (opcional)",
    "omega_rpm": "velocidad del volante/rotor [rpm] (opcional)",
    "soc_pct": "estado de carga de baterías internas [%] (opcional)",
    "e_stored_j": "otra energía almacenada estimada [J] (opcional)",
}


def template_csv() -> str:
    t = np.arange(0, 60, 2)
    df = pd.DataFrame({
        "t_s": t,
        "p_abis_w": np.round(1800 + 50 * np.sin(t), 1),
        "p_aux_w": 55.0,
        "p_out_w": np.round(700 + 15 * np.sin(t + 0.5), 1),
        "p_tank_bar_abs": np.round(8.0 - 0.001 * t, 4),
        "omega_rpm": 1150.0,
        "soc_pct": 80.0,
        "e_stored_j": 0.0,
    })
    return df.to_csv(index=False)


def synthetic_test_dataset(hours: float = 2.0, dt_s: float = 2.0, true_err: float = 0.85,
                           P_in_W: float = 2000.0, tank_L: float = 500.0, p_tank0: float = 10.0,
                           tau_tank_min: float = 12.0, seed: int = 5) -> pd.DataFrame:
    """Datos sintéticos DIDÁCTICOS: depósito precargado que se descarga al inicio del ensayo.

    La energía del depósito se transfiere a la salida sin pasar por el medidor de entrada,
    lo que infla el ERR aparente en ventanas cortas. No son datos de Infinity Energy.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(0, hours * 3600 + dt_s, dt_s)
    # ABIS con ciclos de compresión (on/off) — media P_in_W
    duty = 0.8
    period = 30.0
    on = ((t % period) < duty * period).astype(float)
    p_abis = P_in_W / duty * on * (1 + 0.02 * rng.standard_normal(len(t)))
    p_aux = 55 + 3 * rng.standard_normal(len(t))
    # descarga del depósito: p(t) desde p_tank0 hacia 1.2 bar
    p_tank = 1.2 + (p_tank0 - 1.2) * np.exp(-t / (tau_tank_min * 60))
    X = air_tank_exergy(p_tank, tank_L)
    p_release = np.maximum(-np.gradient(X, t), 0) * 0.55          # parte convertida a salida
    base_out = true_err * (P_in_W + 55)
    p_out = base_out * (1 + 0.03 * np.sin(2 * np.pi * t / 3.0) + 0.015 * rng.standard_normal(len(t))) + p_release
    rpm = 1150 + 20 * np.sin(2 * np.pi * t / 600) + 2 * rng.standard_normal(len(t))
    return pd.DataFrame({
        "t_s": t, "p_abis_w": np.round(p_abis, 1), "p_aux_w": np.round(p_aux, 1),
        "p_out_w": np.round(p_out, 1), "p_tank_bar_abs": np.round(p_tank, 4),
        "omega_rpm": np.round(rpm, 2),
    })


def parse_time(df: pd.DataFrame) -> np.ndarray:
    if "t_s" in df.columns:
        return pd.to_numeric(df["t_s"], errors="coerce").to_numpy(float)
    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"], errors="coerce")
        return (ts - ts.iloc[0]).dt.total_seconds().to_numpy(float)
    raise ValueError("El archivo debe contener la columna 't_s' (segundos) o 'timestamp' (ISO 8601).")


def analyze_timeseries(df: pd.DataFrame, tank_L: float = 0.0, J_fly: float = 0.0, batt_Wh: float = 0.0,
                       window_min: float = 10.0) -> dict:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    for req in ("p_abis_w", "p_out_w"):
        if req not in df.columns:
            raise ValueError(f"Falta la columna obligatoria '{req}'.")
    t = parse_time(df)
    ok = np.isfinite(t)
    df = df.loc[ok].reset_index(drop=True)
    t = t[ok]
    order = np.argsort(t)
    df = df.iloc[order].reset_index(drop=True)
    t = t[order]
    p_abis = pd.to_numeric(df["p_abis_w"], errors="coerce").fillna(0).to_numpy(float)
    p_aux = pd.to_numeric(df.get("p_aux_w", 0.0), errors="coerce")
    p_aux = (p_aux.fillna(0).to_numpy(float) if hasattr(p_aux, "to_numpy") else np.zeros_like(t))
    if np.ndim(p_aux) == 0 or len(np.atleast_1d(p_aux)) != len(t):
        p_aux = np.zeros_like(t)
    p_out = pd.to_numeric(df["p_out_w"], errors="coerce").fillna(0).to_numpy(float)

    E_abis = float(_trapz(p_abis, t))
    E_aux = float(_trapz(p_aux, t))
    E_out = float(_trapz(p_out, t))
    E_in = E_abis + E_aux

    stored = np.zeros_like(t)
    parts = {}
    if tank_L > 0 and "p_tank_bar_abs" in df.columns:
        e = air_tank_exergy(pd.to_numeric(df["p_tank_bar_abs"], errors="coerce").ffill().bfill().to_numpy(float), tank_L)
        stored += e
        parts["Depósito de aire"] = float(e[-1] - e[0])
    if J_fly > 0 and "omega_rpm" in df.columns:
        e = flywheel_energy(pd.to_numeric(df["omega_rpm"], errors="coerce").ffill().bfill().to_numpy(float), J_fly)
        stored += e
        parts["Volante / rotor"] = float(e[-1] - e[0])
    if batt_Wh > 0 and "soc_pct" in df.columns:
        e = pd.to_numeric(df["soc_pct"], errors="coerce").ffill().bfill().to_numpy(float) / 100.0 * batt_Wh * 3600
        stored += e
        parts["Baterías"] = float(e[-1] - e[0])
    if "e_stored_j" in df.columns:
        e = pd.to_numeric(df["e_stored_j"], errors="coerce").ffill().bfill().fillna(0).to_numpy(float)
        stored += e
        parts["Otra energía almacenada"] = float(e[-1] - e[0])
    dE = float(stored[-1] - stored[0])
    ERR_raw = E_out / E_in if E_in > 0 else float("nan")
    denom = E_in - dE
    ERR_corr = E_out / denom if denom > 0 else float("nan")

    # ventanas
    W = window_min * 60.0
    edges = np.arange(t[0], t[-1] + 1e-9, W)
    rows = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (t >= a) & (t <= b)
        if m.sum() < 3:
            continue
        ein = float(_trapz(p_abis[m] + p_aux[m], t[m]))
        eout = float(_trapz(p_out[m], t[m]))
        ds = float(stored[m][-1] - stored[m][0])
        rows.append({"t_ini_min": a / 60, "t_fin_min": b / 60, "E_in_Wh": ein / 3600, "E_out_Wh": eout / 3600,
                     "dE_alm_Wh": ds / 3600, "ERR_bruto": eout / ein if ein > 0 else np.nan,
                     "ERR_corr": eout / (ein - ds) if (ein - ds) > 0 else np.nan})
    win = pd.DataFrame(rows)
    cum_in = np.concatenate([[0], np.cumsum(np.diff(t) * 0.5 * ((p_abis + p_aux)[1:] + (p_abis + p_aux)[:-1]))])
    cum_out = np.concatenate([[0], np.cumsum(np.diff(t) * 0.5 * (p_out[1:] + p_out[:-1]))])
    with np.errstate(divide="ignore", invalid="ignore"):
        err_cum_raw = np.where(cum_in > 0, cum_out / cum_in, np.nan)
        err_cum_corr = np.where((cum_in - (stored - stored[0])) > 0, cum_out / (cum_in - (stored - stored[0])), np.nan)
    return {
        "t": t, "p_abis": p_abis, "p_aux": p_aux, "p_out": p_out, "stored": stored,
        "duration_h": (t[-1] - t[0]) / 3600.0,
        "E_abis_kWh": E_abis / 3.6e6, "E_aux_kWh": E_aux / 3.6e6, "E_in_kWh": E_in / 3.6e6,
        "E_out_kWh": E_out / 3.6e6, "dE_stored_kWh": dE / 3.6e6, "stored_parts_kWh": {k: v / 3.6e6 for k, v in parts.items()},
        "ERR_raw": ERR_raw, "ERR_corr": ERR_corr, "windows": win,
        "err_cum_raw": err_cum_raw, "err_cum_corr": err_cum_corr,
    }


def report_markdown(res: dict, unc: dict, dec: dict, meta: dict) -> str:
    lines = [
        "# Informe de análisis de ensayo — balance energético (frontera completa)",
        "",
        f"*Generado con la plataforma demo de evaluación científica. Archivo: {meta.get('file', '—')}*",
        "",
        "## Resultados",
        f"- Duración analizada: **{res['duration_h']:.2f} h**",
        f"- Energía de entrada ABIS: {res['E_abis_kWh']:.4f} kWh · Auxiliares: {res['E_aux_kWh']:.4f} kWh",
        f"- Energía de salida útil: {res['E_out_kWh']:.4f} kWh",
        f"- Variación de energía almacenada (fin − inicio): {res['dE_stored_kWh']:+.4f} kWh",
        f"- ERR bruto: **{res['ERR_raw']:.4f}** · ERR corregido por almacenamiento: **{res['ERR_corr']:.4f}**",
        "",
        "## Incertidumbre (GUM)",
        f"- u tipo A (ventanas, n_eff={unc.get('n_eff', float('nan')):.1f}): {unc.get('uA', float('nan')):.4f}",
        f"- u tipo B (instrumentación): {unc.get('uB', float('nan')):.4f}",
        f"- u combinada: {unc.get('uc', float('nan')):.4f} · U (k=2): {dec['U']:.4f}",
        f"- Intervalo ~95 %: [{dec['lower']:.4f}; {dec['upper']:.4f}] · P(ERR>1) ≈ {dec['P(ERR>1)']:.3f}",
        "",
        f"**Dictamen:** {dec['verdict']}",
        "",
        "## Advertencias",
        "- Este informe no sustituye una validación independiente por un laboratorio acreditado (ISO/IEC 17025).",
        "- Verifique trazabilidad de calibración, sincronización de canales y que la frontera incluya TODAS las entradas.",
    ]
    return "\n".join(lines)
