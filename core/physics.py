"""
core/physics.py
================
Modelo físico GENÉRICO de un convertidor por flotabilidad: inserción de cuerpos
de aire en una columna de agua -> trabajo de flotación -> eje -> generador.

IMPORTANTE: este modelo NO representa el diseño patentado de Infinity Energy.
Es un modelo de primeros principios (hidrostática + termodinámica de gases
ideales + electromecánica) para fijar cotas de referencia, entender pérdidas y
diseñar el protocolo de validación del MVP.

Resultado central (ciclo cerrado, sin fuente térmica externa):
    W_flotación,max = p0·V0·ln(pH/p0) = W_inserción,min (compresión isotérmica reversible)
=> ERR_max = 1. Cualquier ERR > 1 medido de forma repetible implicaría un flujo
de energía adicional que debe ser identificado y caracterizado.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
import math
import numpy as np

_trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")

G0 = 9.80665          # m/s²
P_ATM = 101_325.0     # Pa
R_AIR = 287.05        # J/(kg·K)
GAMMA = 1.4           # cp/cv aire
CP_AIR = 1005.0       # J/(kg·K)


# ----------------------------------------------------------------------------
# Propiedades
# ----------------------------------------------------------------------------
def water_density(T_c: float) -> float:
    """Densidad del agua dulce [kg/m³] (fórmula tipo Thiesen, 0–40 °C)."""
    return 1000.0 * (1.0 - (T_c + 288.9414) / (508_929.2 * (T_c + 68.12963)) * (T_c - 3.9863) ** 2)


def p_atm_altitude(z_m: float) -> float:
    """Presión atmosférica estándar (ISA) a la altitud z [m]."""
    return P_ATM * (1.0 - 2.25577e-5 * z_m) ** 5.25588


# ----------------------------------------------------------------------------
# Modelo de ciclo (estado estacionario, por inserción)
# ----------------------------------------------------------------------------
COMPRESSION_MODES = ("isotérmica", "politrópica", "adiabática")


@dataclass
class CycleParams:
    H: float = 8.0               # altura de la columna de agua [m]
    V0_L: float = 20.0           # aire por inserción, a p0 y T_aire (FAD) [L]
    f_ins: float = 1.0           # frecuencia de inserción [Hz]
    T_w_C: float = 25.0          # temperatura del agua [°C]
    T_a_C: float = 25.0          # temperatura del aire de admisión [°C]
    altitude_m: float = 0.0      # altitud del sitio [m]
    compression: str = "adiabática"
    n_poly: float = 1.25         # índice politrópico (si aplica)
    eta_comp: float = 0.75       # eficiencia del compresor respecto al proceso ideal elegido
    eta_motor: float = 0.92      # motor eléctrico del ABIS
    eta_cap: float = 0.70        # captura hidrodinámica del trabajo de flotación (KEM)
    eta_gear: float = 0.95       # transmisión mecánica
    eta_gen: float = 0.92        # generador eléctrico
    eta_pe: float = 0.96         # electrónica de potencia (PDU)
    P_aux_W: float = 50.0        # auxiliares (CMS, sensores, bombas, refrigeración) [W]

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class CycleResult:
    p0: float
    rho: float
    pH: float
    ratio: float
    V0: float
    VH: float
    W_rigid: float          # flotación de un cuerpo rígido de volumen V0 (referencia)
    W_iso_ref: float        # exergía del aire a profundidad = inserción mínima reversible [J]
    W_comp_ideal: float     # trabajo ideal del proceso de compresión elegido [J]
    W_comp: float           # trabajo real en el eje del compresor [J]
    E_ins: float            # energía eléctrica por inserción [J]
    W_buoy: float           # trabajo de flotación disponible (expansión isotérmica a T_agua) [J]
    W_mech: float           # trabajo capturado por el KEM [J]
    W_shaft: float          # tras transmisión [J]
    W_gen: float            # tras generador [J]
    W_out: float            # salida eléctrica útil por inserción [J]
    Q_water: float          # calor tomado del agua por inserción [J]
    T_out_comp: float       # temperatura de descarga del compresor [K]
    P_in: float             # potencia eléctrica de entrada total (ABIS + aux) [W]
    P_abis: float
    P_aux: float
    P_buoy: float
    P_out: float
    P_net: float
    ERR: float              # E_out / E_in (frontera completa)
    ERR_ideal_cycle: float  # W_buoy / W_comp_ideal (todas las η = 1)
    ERR_closed_bound: float # cota del ciclo cerrado: (T_w/T_a) (compresión isotérmica ideal)
    carnot: float           # eficiencia de Carnot entre T_w y T_a (si ΔT>0)
    losses: dict = field(default_factory=dict)


def compression_work_ideal(p0: float, V0: float, ratio: float, mode: str, n_poly: float = 1.25) -> float:
    """Trabajo técnico ideal (flujo estacionario) para comprimir V0 (a p0) hasta p0·ratio."""
    if ratio <= 1.0:
        return 0.0
    if mode == "isotérmica":
        return p0 * V0 * math.log(ratio)
    k = GAMMA if mode == "adiabática" else max(1.0001, n_poly)
    return (k / (k - 1.0)) * p0 * V0 * (ratio ** ((k - 1.0) / k) - 1.0)


def buoyancy_work(p0: float, V0: float, ratio: float, T_w: float, T_a: float) -> float:
    """Trabajo de flotación de un cuerpo de aire que asciende con expansión isotérmica a T_w.

    W = ∫ρ g V(z) dz = ∫ V dp = (T_w/T_a)·p0·V0·ln(pH/p0)
    (el aire, admitido a T_a, se equilibra térmicamente con el agua a profundidad).
    """
    if ratio <= 1.0:
        return 0.0
    return (T_w / T_a) * p0 * V0 * math.log(ratio)


def cycle(params: CycleParams) -> CycleResult:
    p = params
    T_w = p.T_w_C + 273.15
    T_a = p.T_a_C + 273.15
    p0 = p_atm_altitude(p.altitude_m)
    rho = water_density(p.T_w_C)
    pH = p0 + rho * G0 * p.H
    ratio = pH / p0
    V0 = p.V0_L / 1000.0
    VH = V0 * (p0 / pH) * (T_w / T_a)

    W_rigid = rho * G0 * p.H * V0
    W_iso_ref = p0 * V0 * math.log(ratio)
    W_ci = compression_work_ideal(p0, V0, ratio, p.compression, p.n_poly)
    W_c = W_ci / max(p.eta_comp, 1e-6)
    E_ins = W_c / max(p.eta_motor, 1e-6)

    if p.compression == "isotérmica":
        T_out = T_a
    else:
        k = GAMMA if p.compression == "adiabática" else max(1.0001, p.n_poly)
        T_out = T_a * (1.0 + (ratio ** ((k - 1.0) / k) - 1.0) / max(p.eta_comp, 1e-6))

    W_b = buoyancy_work(p0, V0, ratio, T_w, T_a)
    W_mech = p.eta_cap * W_b
    W_shaft = p.eta_gear * W_mech
    W_gen = p.eta_gen * W_shaft
    W_out = p.eta_pe * W_gen

    m_air = p0 * V0 / (R_AIR * T_a)
    Q_water = m_air * CP_AIR * (T_w - T_a) + W_b

    f = p.f_ins
    P_abis = f * E_ins
    P_aux = p.P_aux_W
    P_in = P_abis + P_aux
    P_out = f * W_out
    P_net = P_out - P_in
    ERR = P_out / P_in if P_in > 0 else float("nan")
    ERR_ideal = W_b / W_ci if W_ci > 0 else float("nan")
    carnot = max(0.0, 1.0 - min(T_a, T_w) / max(T_a, T_w))

    thermal_gain = max(0.0, W_b - W_iso_ref)
    thermal_deficit = max(0.0, W_iso_ref - W_b)  # si el agua está más fría que el aire
    losses = {
        "Pérdidas motor ABIS": f * (E_ins - W_c),
        "Irreversibilidad de compresión (calor al agua/ambiente)": f * (W_c - W_iso_ref),
        "Aporte térmico del agua (ΔT>0)": f * thermal_gain,
        "Déficit térmico (agua más fría que el aire)": f * thermal_deficit,
        "Pérdidas hidrodinámicas (deslizamiento, arrastre, turbulencia)": f * (W_b - W_mech),
        "Pérdidas mecánicas (transmisión, fricción)": f * (W_mech - W_shaft),
        "Pérdidas generador": f * (W_shaft - W_gen),
        "Pérdidas electrónica de potencia": f * (W_gen - W_out),
        "Auxiliares (CMS, sensores, bombas)": P_aux,
    }
    return CycleResult(
        p0=p0, rho=rho, pH=pH, ratio=ratio, V0=V0, VH=VH, W_rigid=W_rigid,
        W_iso_ref=W_iso_ref, W_comp_ideal=W_ci, W_comp=W_c, E_ins=E_ins,
        W_buoy=W_b, W_mech=W_mech, W_shaft=W_shaft, W_gen=W_gen, W_out=W_out,
        Q_water=Q_water, T_out_comp=T_out, P_in=P_in, P_abis=P_abis, P_aux=P_aux,
        P_buoy=f * W_b, P_out=P_out, P_net=P_net, ERR=ERR, ERR_ideal_cycle=ERR_ideal,
        ERR_closed_bound=T_w / T_a, carnot=carnot, losses=losses,
    )


def sankey_data(params: CycleParams, res: CycleResult) -> dict:
    """Nodos y enlaces para un diagrama de Sankey del flujo de energía [W]."""
    f = params.f_ins
    nodes = [
        "Entrada eléctrica ABIS",            # 0
        "Motor ABIS",                         # 1
        "Compresión / inserción",            # 2
        "Exergía del aire a profundidad",    # 3
        "Trabajo de flotación",              # 4
        "Eje KEM",                            # 5
        "Generador",                          # 6
        "Electrónica PDU",                    # 7
        "Salida eléctrica útil",             # 8
        "Pérdidas motor",                     # 9
        "Calor de compresión (irreversib.)", # 10
        "Pérdidas hidrodinámicas",           # 11
        "Pérdidas mecánicas",                # 12
        "Pérdidas generador",                # 13
        "Pérdidas electrónica",              # 14
        "Aporte térmico del agua (ΔT)",      # 15
        "Entrada auxiliares",                # 16
        "Consumo auxiliares (CMS)",          # 17
        "Déficit térmico (ΔT<0)",            # 18
    ]
    gain = max(0.0, res.W_buoy - res.W_iso_ref) * f
    deficit = max(0.0, res.W_iso_ref - res.W_buoy) * f
    links = [
        (0, 1, f * res.E_ins),
        (1, 9, f * (res.E_ins - res.W_comp)),
        (1, 2, f * res.W_comp),
        (2, 10, f * (res.W_comp - res.W_iso_ref)),
        (2, 3, f * res.W_iso_ref),
        (3, 4, f * res.W_iso_ref - deficit),
        (3, 18, deficit),
        (15, 4, gain),
        (4, 11, f * (res.W_buoy - res.W_mech)),
        (4, 5, f * res.W_mech),
        (5, 12, f * (res.W_mech - res.W_shaft)),
        (5, 6, f * res.W_shaft),
        (6, 13, f * (res.W_shaft - res.W_gen)),
        (6, 7, f * res.W_gen),
        (7, 14, f * (res.W_gen - res.W_out)),
        (7, 8, f * res.W_out),
        (16, 17, res.P_aux),
    ]
    links = [(s, t, v) for (s, t, v) in links if v > 1e-9]
    return {"nodes": nodes, "links": links}


def sweep_height(params: CycleParams, H_values: np.ndarray) -> dict:
    """Curvas de trabajo por inserción vs altura de columna."""
    out = {k: [] for k in ("H", "W_buoy", "W_iso", "W_adiab", "W_rigid", "ERR", "ERR_ideal")}
    for H in H_values:
        q = CycleParams(**{**params.as_dict(), "H": float(H)})
        r = cycle(q)
        out["H"].append(H)
        out["W_buoy"].append(r.W_buoy)
        out["W_iso"].append(r.W_iso_ref)
        out["W_adiab"].append(compression_work_ideal(r.p0, r.V0, r.ratio, "adiabática"))
        out["W_rigid"].append(r.W_rigid)
        out["ERR"].append(r.ERR)
        out["ERR_ideal"].append(r.ERR_ideal_cycle)
    return {k: np.asarray(v) for k, v in out.items()}


def err_map(params: CycleParams, eta_comp_grid: np.ndarray, eta_cap_grid: np.ndarray) -> np.ndarray:
    """ERR en función de η_compresor (eje x) y η_captura (eje y)."""
    Z = np.zeros((len(eta_cap_grid), len(eta_comp_grid)))
    base = params.as_dict()
    for i, ec in enumerate(eta_cap_grid):
        for j, ek in enumerate(eta_comp_grid):
            Z[i, j] = cycle(CycleParams(**{**base, "eta_comp": float(ek), "eta_cap": float(ec)})).ERR
    return Z


def bubble_terminal_velocity(V_m3: float) -> float:
    """Velocidad terminal de una burbuja grande de casquete esférico (Davies–Taylor)."""
    d_e = (6.0 * V_m3 / math.pi) ** (1.0 / 3.0)
    return 0.711 * math.sqrt(G0 * d_e)


# ----------------------------------------------------------------------------
# Modelo dinámico electromecánico (dominio del tiempo)
# ----------------------------------------------------------------------------
@dataclass
class DynParams:
    H: float = 8.0
    V0_L: float = 20.0           # aire por cangilón a p0 [L]
    s_bucket: float = 0.5        # paso entre cangilones [m]
    Vb_L: float = 22.0           # capacidad del cangilón [L]
    r_sprocket: float = 0.25     # radio de la rueda motriz [m]
    eta_cap: float = 0.85        # fracción del aire efectivamente capturado
    Cd: float = 1.2              # coeficiente de arrastre del cangilón
    A_bucket: float = 0.03       # área frontal del cangilón [m²]
    T_coul: float = 15.0         # fricción de Coulomb [N·m]
    b_visc: float = 5.0          # fricción viscosa [N·m·s/rad]
    J_main: float = 40.0         # inercia en el eje principal [kg·m²]
    J_gen: float = 0.05          # inercia del rotor del generador [kg·m²]
    J_fly: float = 0.0           # volante de inercia en eje rápido [kg·m²]
    G_ratio: float = 60.0        # relación de multiplicación
    eta_gear: float = 0.95
    K_e: float = 1.2             # constante de FEM [V·s/rad]
    R_s: float = 0.6             # resistencia del estator [Ω]
    R_load: float = 25.0         # resistencia de carga equivalente [Ω]
    eta_pe: float = 0.96
    E_ins_J: float = 1826.0      # energía eléctrica por inserción (del modelo de ciclo) [J]
    P_aux_W: float = 50.0
    T_w_C: float = 25.0
    altitude_m: float = 0.0
    preload: bool = True         # cangilones ascendentes precargados al inicio (energía almacenada)
    T_sim: float = 40.0          # [s]
    dt: float = 0.004            # [s]

    def as_dict(self) -> dict:
        return asdict(self)


def simulate_dynamics(p: DynParams, decim: int = 5) -> dict:
    """Simulación del arranque y régimen del sistema cadena–cangilones–generador.

    Ecuación de movimiento (referida al eje principal):
        J_eq dω/dt = T_flot − T_arrastre − T_fricción − T_e(ω)
    con J_eq = J_main + G²·(J_gen + J_fly).
    Cada vez que un cangilón pasa por el punto de inserción se inyecta V0 y se
    contabiliza la energía E_ins del ABIS. La energía de los cangilones precargados
    se reporta como energía almacenada inicial (sesgo típico de ensayos cortos).
    """
    rho = water_density(p.T_w_C)
    p0 = p_atm_altitude(p.altitude_m)
    H = p.H
    rs = p.r_sprocket
    L_loop = 2.0 * H + 2.0 * math.pi * rs
    n_b = max(4, int(round(L_loop / p.s_bucket)))
    spacing = L_loop / n_b
    xi = np.arange(n_b) * spacing                 # posición sobre el lazo [m]
    Vb = p.Vb_L / 1000.0
    V0c = p.eta_cap * p.V0_L / 1000.0

    # contenido de aire de cada cangilón expresado como volumen a p0
    n_air = np.zeros(n_b)
    if p.preload:
        asc = xi < H
        n_air[asc] = V0c
    def depth(x):
        return np.clip(H - x, 0.0, H)

    def stored_buoy_energy(x, nair):
        """Trabajo de flotación remanente de los cangilones cargados (isotérmico)."""
        asc = (x < H) & (nair > 0)
        z = depth(x[asc])
        pz = p0 + rho * G0 * z
        return float(np.sum(nair[asc] * p0 * np.log(pz / p0)))

    E_stored0 = stored_buoy_energy(xi, n_air)
    J_eq = p.J_main + p.G_ratio ** 2 * (p.J_gen + p.J_fly)
    w = 0.0
    n_sub = 2.0 * H / spacing
    steps = int(p.T_sim / p.dt)
    rec = {k: [] for k in ("t", "omega", "u", "rpm_gen", "T_b", "T_e", "P_mech", "P_abis",
                           "P_out", "E_in", "E_out", "ERR_cum", "n_filled")}
    E_in = 0.0
    E_out = 0.0
    E_abis = 0.0
    pulse_queue = []          # (t_end, power) para representar el pulso del ABIS
    tau_ins = 0.25
    x_disp = 0.0
    for i in range(steps):
        t = i * p.dt
        # fuerzas de flotación
        asc = (xi < H) & (n_air > 0)
        z = depth(xi[asc])
        pz = p0 + rho * G0 * z
        Vz = n_air[asc] * p0 / pz
        over = Vz > Vb
        if np.any(over):  # derrame: el aire que excede la capacidad se pierde
            idx = np.where(asc)[0][over]
            n_air[idx] = Vb * pz[over] / p0
            Vz = np.minimum(Vz, Vb)
        F_b = rho * G0 * float(np.sum(Vz))
        T_b = rs * F_b
        u = w * rs
        T_d = rs * 0.5 * rho * p.Cd * p.A_bucket * u * abs(u) * n_sub
        T_f = p.T_coul * math.tanh(w / 0.05) + p.b_visc * w
        wg = p.G_ratio * w
        Emf = p.K_e * wg
        I = Emf / (p.R_s + p.R_load)
        T_eg = p.K_e * I
        T_e = p.G_ratio * T_eg / p.eta_gear
        dw = (T_b - T_d - T_f - T_e) / J_eq
        w = max(0.0, w + dw * p.dt)
        # avance de la cadena
        dx = w * rs * p.dt
        x_disp += dx
        xi_new = (xi + dx) % L_loop
        wrapped = xi_new < xi                       # cruzó el punto de inserción (ξ = 0)
        topped = (xi < H) & (xi_new >= H)           # llegó a la superficie: se vacía
        n_air[topped] = 0.0
        n_ins = int(np.count_nonzero(wrapped))
        if n_ins:
            n_air[wrapped] = V0c
            E_abis += n_ins * p.E_ins_J
            pulse_queue.append((t + tau_ins, n_ins * p.E_ins_J / tau_ins))
        xi = xi_new
        P_abis = sum(pw for (te, pw) in pulse_queue if te > t)
        pulse_queue = [(te, pw) for (te, pw) in pulse_queue if te > t]
        P_out = p.eta_pe * I * I * p.R_load
        E_in += (P_abis + p.P_aux_W) * p.dt
        E_out += P_out * p.dt
        if i % decim == 0:
            rec["t"].append(t)
            rec["omega"].append(w)
            rec["u"].append(u)
            rec["rpm_gen"].append(wg * 60.0 / (2.0 * math.pi))
            rec["T_b"].append(T_b)
            rec["T_e"].append(T_e)
            rec["P_mech"].append(T_b * w)
            rec["P_abis"].append(P_abis)
            rec["P_out"].append(P_out)
            rec["E_in"].append(E_in)
            rec["E_out"].append(E_out)
            rec["ERR_cum"].append(E_out / E_in if E_in > 0 else np.nan)
            rec["n_filled"].append(int(np.count_nonzero(asc)))
    out = {k: np.asarray(v) for k, v in rec.items()}
    # métricas de régimen (último 35 % de la simulación)
    t = out["t"]
    mask = t >= 0.65 * p.T_sim
    if mask.sum() > 10:
        Pin_ss = float(np.mean(out["P_abis"][mask]) + p.P_aux_W)
        # energía ABIS en régimen calculada con eventos, más robusta que la media de pulsos
        dE_in = out["E_in"][mask][-1] - out["E_in"][mask][0]
        dE_out = out["E_out"][mask][-1] - out["E_out"][mask][0]
        dT = t[mask][-1] - t[mask][0]
        Pin_ss = dE_in / dT if dT > 0 else Pin_ss
        Pout_ss = dE_out / dT if dT > 0 else float(np.mean(out["P_out"][mask]))
        om = out["omega"][mask]
        po = out["P_out"][mask]
        metrics = dict(
            omega_ss=float(np.mean(om)),
            u_ss=float(np.mean(out["u"][mask])),
            rpm_gen_ss=float(np.mean(out["rpm_gen"][mask])),
            f_ins_ss=float(np.mean(out["u"][mask]) / spacing),
            P_in_ss=Pin_ss,
            P_out_ss=Pout_ss,
            ERR_ss=Pout_ss / Pin_ss if Pin_ss > 0 else float("nan"),
            ripple_speed=float((om.max() - om.min()) / max(np.mean(om), 1e-9)),
            ripple_power=float((po.max() - po.min()) / max(np.mean(po), 1e-9)),
            T_b_ss=float(np.mean(out["T_b"][mask])),
        )
    else:
        metrics = {}
    metrics.update(dict(E_stored0=E_stored0, n_buckets=n_b, spacing=spacing, J_eq=J_eq,
                        E_in_total=E_in, E_out_total=E_out))
    return {"series": out, "metrics": metrics}


def steady_state_vs_load(p: DynParams, R_values: np.ndarray) -> dict:
    """Punto de operación en régimen (balance de pares) para distintas cargas.

    Con todos los cangilones ascendentes llenos, T_flot es ~constante; se resuelve
    T_flot = T_arrastre(ω) + T_fricción(ω) + T_e(ω, R).
    """
    rho = water_density(p.T_w_C)
    p0 = p_atm_altitude(p.altitude_m)
    H, rs = p.H, p.r_sprocket
    L_loop = 2.0 * H + 2.0 * math.pi * rs
    n_b = max(4, int(round(L_loop / p.s_bucket)))
    spacing = L_loop / n_b
    V0c = p.eta_cap * p.V0_L / 1000.0
    Vb = p.Vb_L / 1000.0
    # fuerza media de flotación (integral continua, con derrame)
    zz = np.linspace(0.0, H, 400)
    pz = p0 + rho * G0 * zz
    Vz = np.minimum(V0c * p0 / pz, Vb)
    F_b = rho * G0 * _trapz(Vz, zz) / spacing
    W_buoy_per_bucket = rho * G0 * _trapz(Vz, zz)
    T_b = rs * F_b
    n_sub = 2.0 * H / spacing
    out = {k: [] for k in ("R", "omega", "f_ins", "P_out", "P_in", "ERR", "rpm_gen")}
    for R in R_values:
        kd = rs * 0.5 * rho * p.Cd * p.A_bucket * n_sub * rs ** 2   # T_d = kd·ω²
        ke = p.G_ratio * (p.K_e ** 2) * p.G_ratio / ((p.R_s + R) * p.eta_gear)  # T_e = ke·ω
        a, b, c = kd, p.b_visc + ke, p.T_coul - T_b
        if c >= 0:
            w = 0.0
        else:
            w = (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a) if a > 0 else -c / b
        u = w * rs
        f = u / spacing
        I = p.K_e * p.G_ratio * w / (p.R_s + R)
        P_out = p.eta_pe * I * I * R
        P_in = f * p.E_ins_J + p.P_aux_W
        out["R"].append(R)
        out["omega"].append(w)
        out["f_ins"].append(f)
        out["P_out"].append(P_out)
        out["P_in"].append(P_in)
        out["ERR"].append(P_out / P_in if P_in > 0 else np.nan)
        out["rpm_gen"].append(p.G_ratio * w * 60 / (2 * math.pi))
    res = {k: np.asarray(v) for k, v in out.items()}
    res["T_b"] = T_b
    res["W_buoy_per_bucket"] = W_buoy_per_bucket
    return res
