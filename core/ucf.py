"""
core/ucf.py
===========
Funciones de Costo de Incertidumbre (UCF, *Uncertainty Cost Functions*).

Para un recurso con potencia disponible aleatoria W (PDF f_W) y potencia
programada W_s:

    C_u(W_s) = c_u · E[(W − W_s)⁺]   costo por SUBestimación (energía disponible no programada)
    C_o(W_s) = c_o · E[(W_s − W)⁺]   costo por SOBREestimación (energía programada no entregada)
    UCF(W_s) = C_u + C_o

Propiedades usadas en la demo:
    MUCF(W_s) = dUCF/dW_s = (c_u + c_o)·F_W(W_s) − c_u        (costo marginal de incertidumbre)
    d²UCF/dW_s² = (c_u + c_o)·f_W(W_s) ≥ 0                    (convexidad)
    W_s* = F_W⁻¹( c_u / (c_u + c_o) )                          (mínimo: cuantil crítico)

Se implementan expresiones ANALÍTICAS (momentos parciales en forma cerrada),
integración NUMÉRICA sobre la variable primaria y verificación por MONTE CARLO.

Modelos de recurso primario:
    FV   : irradiancia log-normal + curva de potencia cuadrática/lineal/saturada
    Eólica: velocidad Weibull (k = 2 ⇒ Rayleigh) + curva de potencia por tramos
    PCH  : caudal Gumbel (máximos) + P = ρ g h η Q saturada (filo de agua)
    VE / carga controlable: Normal
    Planta modular firme (IE): mezcla binomial (disponibilidad) × Normal recortada
    Uniforme: simplificación clásica
    Empírica: a partir de muestras medidas (p. ej. datos de MVP)
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np
from scipy import special, stats, integrate

SQRT2 = math.sqrt(2.0)
_trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")
EULER_GAMMA = 0.5772156649015329


def _Phi(x):
    return 0.5 * (1.0 + special.erf(np.asarray(x, float) / SQRT2))


def _phi(x):
    x = np.asarray(x, float)
    return np.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


# ----------------------------------------------------------------------------
# Clase base
# ----------------------------------------------------------------------------
class Resource:
    name: str = "Recurso"
    short: str = "R"
    w_max: float = 1.0
    w_min: float = 0.0

    # --- a implementar por cada recurso ---
    def partial_upper(self, w):           # E[(W − w)⁺] analítico
        raise NotImplementedError

    def cdf(self, w):                     # F_W(w) = P(W ≤ w)
        raise NotImplementedError

    def sample(self, n: int, rng: np.random.Generator):
        raise NotImplementedError

    def partial_upper_numeric(self, w):   # integración numérica sobre la variable primaria
        raise NotImplementedError

    # --- comunes ---
    def mean(self) -> float:
        # válido cuando W ≥ w_min casi seguramente: E[(W − w_min)⁺] = E[W] − w_min
        return float(self.partial_upper(np.array([self.w_min]))[0] + self.w_min)

    def ucf(self, w, cu: float, co: float):
        w = np.atleast_1d(np.asarray(w, float))
        Eu = self.partial_upper(w)
        El = w - self.mean() + Eu                     # (w−W)⁺ = (w−W) + (W−w)⁺
        return cu * Eu, co * El

    def ucf_total(self, w, cu, co):
        a, b = self.ucf(w, cu, co)
        return a + b

    def mucf(self, w, cu, co):
        return (cu + co) * self.cdf(np.atleast_1d(np.asarray(w, float))) - cu

    def grid(self, n: int = 1500):
        return np.linspace(self.w_min, self.w_max, n)

    def ppf(self, q):
        """Cuantil generalizado: min{w : F(w) ≥ q} (maneja masas puntuales)."""
        cache = getattr(self, "_ppf_cache", None)
        if cache is None:
            g = self.grid(4000)
            F = np.maximum.accumulate(self.cdf(g))
            self._ppf_cache = (g, F)
        else:
            g, F = cache
        q = np.atleast_1d(np.asarray(q, float))
        idx = np.searchsorted(F, np.clip(q, 0, 1) - 1e-12, side="left")
        idx = np.clip(idx, 0, len(g) - 1)
        return g[idx]

    def optimum(self, cu: float, co: float):
        q = cu / (cu + co)
        ws = float(self.ppf(q)[0])
        val = float(self.ucf_total(ws, cu, co)[0])
        return ws, val, q

    def ucf_mc(self, w, cu, co, n=100_000, seed=7):
        rng = np.random.default_rng(seed)
        s = self.sample(n, rng)
        w = np.atleast_1d(np.asarray(w, float))
        diff = s[None, :] - w[:, None]
        Eu = np.mean(np.maximum(diff, 0.0), axis=1)
        El = np.mean(np.maximum(-diff, 0.0), axis=1)
        return cu * Eu, co * El

    def ucf_numeric(self, w, cu, co):
        w = np.atleast_1d(np.asarray(w, float))
        Eu = np.array([self.partial_upper_numeric(x) for x in w])
        m = float(self.partial_upper_numeric(self.w_min - 1e-12) + self.w_min)
        return cu * Eu, co * (w - m + Eu)

    def describe(self) -> dict:
        return {"Recurso": self.name, "W_max [MW]": self.w_max, "E[W] [MW]": self.mean()}


# ----------------------------------------------------------------------------
# Momentos parciales en forma cerrada
# ----------------------------------------------------------------------------
def lognorm_partial_moment(k: int, a, b, mu: float, sigma: float):
    """∫_a^b x^k f_LN(x) dx  (a, b ≥ 0; b puede ser inf)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    with np.errstate(divide="ignore"):
        la = np.where(a > 0, np.log(np.maximum(a, 1e-300)), -np.inf)
        lb = np.where(np.isfinite(b), np.log(np.maximum(b, 1e-300)), np.inf)
    c = math.exp(k * mu + 0.5 * k * k * sigma * sigma)
    return c * (_Phi((lb - mu - k * sigma ** 2) / sigma) - _Phi((la - mu - k * sigma ** 2) / sigma))


def weibull_partial_moment(n: int, a, b, k: float, c: float):
    """∫_a^b x^n f_Weibull(x) dx con forma k y escala c."""
    a = np.maximum(np.asarray(a, float), 0.0)
    b = np.asarray(b, float)
    s = 1.0 + n / k
    Pb = special.gammainc(s, np.where(np.isfinite(b), (b / c) ** k, np.inf))
    Pa = special.gammainc(s, (a / c) ** k)
    return (c ** n) * special.gamma(s) * (Pb - Pa)


def gumbel_partial_moment(n: int, a, b, loc: float, scale: float):
    """∫_a^b x^n f_Gumbel(x) dx para n ∈ {0, 1} (Gumbel de máximos).

    Forma cerrada vía la integral exponencial E1 (relacionada con Ei).
    """
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ta = np.exp(np.clip(-(a - loc) / scale, -700, 700))
    tb = np.exp(np.clip(-(b - loc) / scale, -700, 700))
    Fa = np.exp(-ta)
    Fb = np.exp(-tb)
    if n == 0:
        return Fb - Fa

    def G(t):
        # g(t) = e^{-t} ln t + E1(t);  límite t→0: −γ ;  t→∞: 0
        t = np.asarray(t, float)
        out = np.empty_like(t)
        small = t < 1e-12
        big = t > 700
        mid = ~(small | big)
        out[small] = -EULER_GAMMA
        out[big] = 0.0
        tm = t[mid]
        out[mid] = np.exp(-tm) * np.log(tm) + special.exp1(tm)
        return out

    return loc * (Fb - Fa) + scale * (G(ta) - G(tb))


# ----------------------------------------------------------------------------
# Recursos
# ----------------------------------------------------------------------------
@dataclass
class PVResource(Resource):
    P_r: float = 50.0          # MW
    G_mean: float = 600.0      # W/m² (media de la hora analizada)
    G_cv: float = 0.45         # coeficiente de variación de la irradiancia
    G_std: float = 1000.0      # irradiancia estándar
    R_c: float = 150.0         # punto de cambio cuadrático→lineal
    name: str = "Solar FV"
    short: str = "FV"

    def __post_init__(self):
        self.sigma = math.sqrt(math.log(1.0 + self.G_cv ** 2))
        self.mu = math.log(self.G_mean) - 0.5 * self.sigma ** 2
        self.w_max = self.P_r
        self.w_min = 0.0
        self.P_Rc = self.P_r * self.R_c / self.G_std

    def power(self, G):
        G = np.asarray(G, float)
        return np.where(G < self.R_c, self.P_r * G ** 2 / (self.G_std * self.R_c),
                        np.where(G < self.G_std, self.P_r * G / self.G_std, self.P_r))

    def G_of_w(self, w):
        w = np.asarray(w, float)
        return np.where(w < self.P_Rc, np.sqrt(np.maximum(w, 0) * self.G_std * self.R_c / self.P_r),
                        w * self.G_std / self.P_r)

    def cdf(self, w):
        w = np.atleast_1d(np.asarray(w, float))
        Gw = self.G_of_w(np.clip(w, 0, self.P_r))
        with np.errstate(divide="ignore"):
            F = np.where(Gw > 0, _Phi((np.log(np.maximum(Gw, 1e-300)) - self.mu) / self.sigma), 0.0)
        F = np.where(w >= self.P_r, 1.0, F)
        return np.where(w < 0, 0.0, F)

    def partial_upper(self, w):
        w = np.atleast_1d(np.asarray(w, float))
        out = np.zeros_like(w)
        mu, s = self.mu, self.sigma
        neg = w < 0
        wc = np.clip(w, 0, self.P_r)
        Gw = self.G_of_w(wc)
        # tramo cuadrático
        lo1 = Gw
        hi1 = np.full_like(w, self.R_c)
        m1 = lo1 < hi1
        t1 = np.where(m1, (self.P_r / (self.G_std * self.R_c)) * lognorm_partial_moment(2, lo1, hi1, mu, s)
                      - wc * lognorm_partial_moment(0, lo1, hi1, mu, s), 0.0)
        # tramo lineal
        lo2 = np.maximum(Gw, self.R_c)
        hi2 = np.full_like(w, self.G_std)
        m2 = lo2 < hi2
        t2 = np.where(m2, (self.P_r / self.G_std) * lognorm_partial_moment(1, lo2, hi2, mu, s)
                      - wc * lognorm_partial_moment(0, lo2, hi2, mu, s), 0.0)
        # saturación
        t3 = (self.P_r - wc) * (1.0 - _Phi((math.log(self.G_std) - mu) / s))
        out = t1 + t2 + t3
        out = np.where(w >= self.P_r, 0.0, out)
        # para w<0: E[(W−w)+] = E[W] − w
        if np.any(neg):
            m0 = self.partial_upper(np.array([0.0]))[0]
            out = np.where(neg, m0 - w, out)
        return out

    def sample(self, n, rng):
        G = np.exp(self.mu + self.sigma * rng.standard_normal(n))
        return self.power(G)

    def partial_upper_numeric(self, w):
        f = lambda G: max(float(self.power(G)) - w, 0.0) * stats.lognorm.pdf(G, s=self.sigma, scale=math.exp(self.mu))
        a = 0.0
        pts = [self.R_c, self.G_std]
        v1, _ = integrate.quad(f, a, self.G_std, points=pts[:1], limit=200)
        tail = max(self.P_r - w, 0.0) * stats.lognorm.sf(self.G_std, s=self.sigma, scale=math.exp(self.mu))
        return v1 + tail


@dataclass
class WindResource(Resource):
    W_r: float = 50.0          # MW
    k: float = 2.0             # forma Weibull (2 = Rayleigh)
    c: float = 8.5             # escala [m/s]
    v_in: float = 3.0
    v_r: float = 12.5
    v_out: float = 25.0
    name: str = "Eólica"
    short: str = "EOL"

    def __post_init__(self):
        self.w_max = self.W_r
        self.w_min = 0.0

    def Fv(self, v):
        v = np.asarray(v, float)
        return 1.0 - np.exp(-np.power(np.maximum(v, 0) / self.c, self.k))

    def power(self, v):
        v = np.asarray(v, float)
        p = np.where((v >= self.v_in) & (v < self.v_r), self.W_r * (v - self.v_in) / (self.v_r - self.v_in), 0.0)
        return np.where((v >= self.v_r) & (v < self.v_out), self.W_r, p)

    def cdf(self, w):
        w = np.atleast_1d(np.asarray(w, float))
        P0 = self.Fv(self.v_in) + (1.0 - self.Fv(self.v_out))
        vw = self.v_in + np.clip(w, 0, self.W_r) / self.W_r * (self.v_r - self.v_in)
        F = P0 + self.Fv(vw) - self.Fv(self.v_in)
        F = np.where(w >= self.W_r, 1.0, F)
        return np.where(w < 0, 0.0, F)

    def partial_upper(self, w):
        w = np.atleast_1d(np.asarray(w, float))
        wc = np.clip(w, 0, self.W_r)
        vw = self.v_in + wc / self.W_r * (self.v_r - self.v_in)
        slope = self.W_r / (self.v_r - self.v_in)
        M1 = weibull_partial_moment(1, vw, self.v_r, self.k, self.c)
        M0 = weibull_partial_moment(0, vw, self.v_r, self.k, self.c)
        t_lin = slope * (M1 - self.v_in * M0) - wc * M0
        t_rat = (self.W_r - wc) * (self.Fv(self.v_out) - self.Fv(self.v_r))
        out = np.where(w >= self.W_r, 0.0, t_lin + t_rat)
        neg = w < 0
        if np.any(neg):
            m0 = self.partial_upper(np.array([0.0]))[0]
            out = np.where(neg, m0 - w, out)
        return out

    def sample(self, n, rng):
        v = self.c * rng.weibull(self.k, n)
        return self.power(v)

    def partial_upper_numeric(self, w):
        pdf = lambda v: stats.weibull_min.pdf(v, self.k, scale=self.c)
        f = lambda v: max(float(self.power(v)) - w, 0.0) * pdf(v)
        v1, _ = integrate.quad(f, self.v_in, self.v_r, limit=200)
        v2 = max(self.W_r - w, 0.0) * (self.Fv(self.v_out) - self.Fv(self.v_r))
        return v1 + float(v2)


@dataclass
class HydroRoRResource(Resource):
    P_max: float = 50.0        # MW
    Q_mean: float = 40.0       # m³/s
    Q_std: float = 12.0        # m³/s
    head: float = 120.0        # m
    eta_t: float = 0.90
    eta_g: float = 0.95
    eta_c: float = 0.98
    rho: float = 997.0
    name: str = "PCH filo de agua"
    short: str = "PCH"

    def __post_init__(self):
        self.scale = self.Q_std * math.sqrt(6.0) / math.pi
        self.loc = self.Q_mean - EULER_GAMMA * self.scale
        self.kq = self.rho * 9.80665 * self.head * self.eta_t * self.eta_g * self.eta_c / 1e6  # MW por m³/s
        self.Q_max = self.P_max / self.kq
        self.w_max = self.P_max
        self.w_min = 0.0

    def FQ(self, q):
        q = np.asarray(q, float)
        return np.exp(-np.exp(np.clip(-(q - self.loc) / self.scale, -700, 700)))

    def power(self, q):
        return np.clip(self.kq * np.asarray(q, float), 0.0, self.P_max)

    def cdf(self, w):
        w = np.atleast_1d(np.asarray(w, float))
        F = self.FQ(np.clip(w, 0, self.P_max) / self.kq)
        F = np.where(w >= self.P_max, 1.0, F)
        return np.where(w < 0, 0.0, F)

    def partial_upper(self, w):
        w = np.atleast_1d(np.asarray(w, float))
        wc = np.clip(w, 0, self.P_max)
        Qw = wc / self.kq
        M1 = gumbel_partial_moment(1, Qw, self.Q_max, self.loc, self.scale)
        M0 = gumbel_partial_moment(0, Qw, self.Q_max, self.loc, self.scale)
        t = self.kq * M1 - wc * M0 + (self.P_max - wc) * (1.0 - self.FQ(self.Q_max))
        out = np.where(w >= self.P_max, 0.0, t)
        neg = w < 0
        if np.any(neg):
            m0 = self.partial_upper(np.array([0.0]))[0]
            out = np.where(neg, m0 - w, out)
        return out

    def sample(self, n, rng):
        q = rng.gumbel(self.loc, self.scale, n)
        return self.power(q)

    def partial_upper_numeric(self, w):
        pdf = lambda q: stats.gumbel_r.pdf(q, loc=self.loc, scale=self.scale)
        f = lambda q: max(float(self.power(q)) - w, 0.0) * pdf(q)
        v1, _ = integrate.quad(f, max(w / self.kq, 0.0), self.Q_max, limit=200)
        v2 = max(self.P_max - w, 0.0) * (1.0 - float(self.FQ(self.Q_max)))
        return v1 + v2


@dataclass
class NormalResource(Resource):
    mu: float = 20.0
    sigma: float = 5.0
    name: str = "VE / carga controlable"
    short: str = "VE"

    def __post_init__(self):
        self.w_min = self.mu - 6 * self.sigma
        self.w_max = self.mu + 6 * self.sigma

    def mean(self):
        return self.mu

    def cdf(self, w):
        return _Phi((np.atleast_1d(np.asarray(w, float)) - self.mu) / self.sigma)

    def partial_upper(self, w):
        w = np.atleast_1d(np.asarray(w, float))
        a = (w - self.mu) / self.sigma
        return (self.mu - w) * (1.0 - _Phi(a)) + self.sigma * _phi(a)

    def sample(self, n, rng):
        return self.mu + self.sigma * rng.standard_normal(n)

    def partial_upper_numeric(self, w):
        f = lambda x: (x - w) * stats.norm.pdf(x, self.mu, self.sigma)
        v, _ = integrate.quad(f, w, self.mu + 12 * self.sigma, limit=200)
        return v


@dataclass
class UniformResource(Resource):
    a: float = 0.0
    b: float = 50.0
    name: str = "Uniforme (simplificada)"
    short: str = "UNI"

    def __post_init__(self):
        self.w_min, self.w_max = self.a, self.b

    def mean(self):
        return 0.5 * (self.a + self.b)

    def cdf(self, w):
        w = np.atleast_1d(np.asarray(w, float))
        return np.clip((w - self.a) / (self.b - self.a), 0, 1)

    def partial_upper(self, w):
        w = np.atleast_1d(np.asarray(w, float))
        wc = np.clip(w, self.a, self.b)
        out = (self.b - wc) ** 2 / (2 * (self.b - self.a))
        return np.where(w < self.a, self.mean() - w, out)

    def sample(self, n, rng):
        return rng.uniform(self.a, self.b, n)

    def partial_upper_numeric(self, w):
        f = lambda x: max(x - w, 0.0) / (self.b - self.a)
        v, _ = integrate.quad(f, self.a, self.b, limit=100)
        return v


def _clipped_normal_upper(w, mu, sigma, b):
    """E[(X − w)⁺] con X = clip(N(μ,σ²), 0, b), para 0 ≤ w ≤ b."""
    w = np.asarray(w, float)
    al = (w - mu) / sigma
    be = (b - mu) / sigma
    core = (mu - w) * (_Phi(be) - _Phi(al)) + sigma * (_phi(al) - _phi(be))
    return np.maximum(core + (b - w) * (1.0 - _Phi(be)), 0.0)


def _clipped_normal_moments(mu, sigma, b):
    z0, zb = (0 - mu) / sigma, (b - mu) / sigma
    P_in = _Phi(zb) - _Phi(z0)
    m1 = mu * P_in + sigma * (_phi(z0) - _phi(zb)) + b * (1 - _Phi(zb))
    m2 = ((mu ** 2 + sigma ** 2) * P_in + 2 * mu * sigma * (_phi(z0) - _phi(zb))
          - sigma ** 2 * (zb * _phi(zb) - z0 * _phi(z0)) + b ** 2 * (1 - _Phi(zb)))
    return float(m1), float(max(m2 - m1 ** 2, 1e-12))


@dataclass
class FirmModularResource(Resource):
    """Planta modular 'firme' (escenario IE): N módulos de P_m MW.

    Cada módulo está disponible con probabilidad A (modelo de Markov de 2 estados,
    A = MTBF/(MTBF+MTTR)); cuando está disponible entrega X ~ N(κ·P_m, (CV·κ·P_m)²)
    recortada a [0, P_m]. Los parámetros son SUPUESTOS DE ESCENARIO a validar en el MVP.
    """
    N: int = 100
    P_m: float = 0.5           # MW por módulo
    A: float = 0.95
    kappa: float = 0.95        # carga media relativa
    cv: float = 0.03
    name: str = "Planta modular firme (IE, escenario)"
    short: str = "IE"

    def __post_init__(self):
        self.N = int(max(1, self.N))
        self.w_max = self.N * self.P_m
        self.w_min = 0.0
        self.mu1 = self.kappa * self.P_m
        self.s1 = max(self.cv * self.mu1, 1e-6)
        self.m1, self.v1 = _clipped_normal_moments(self.mu1, self.s1, self.P_m)
        k = np.arange(self.N + 1)
        self.pk = stats.binom.pmf(k, self.N, self.A)
        self.k = k

    def mean(self):
        return self.N * self.A * self.m1

    def _components(self):
        keep = self.pk > 1e-14
        return self.k[keep], self.pk[keep]

    def cdf(self, w):
        w = np.atleast_1d(np.asarray(w, float))
        ks, ps = self._components()
        F = np.zeros_like(w)
        for k, pk in zip(ks, ps):
            if k == 0:
                F += pk * (w >= 0)
            elif self.N == 1:
                Fx = np.where(w >= self.P_m, 1.0, _Phi((w - self.mu1) / self.s1))
                F += pk * np.where(w < 0, 0.0, Fx)
            else:
                F += pk * _Phi((w - k * self.m1) / math.sqrt(k * self.v1))
        return np.clip(F, 0, 1)

    def partial_upper(self, w):
        w = np.atleast_1d(np.asarray(w, float))
        ks, ps = self._components()
        out = np.zeros_like(w)
        for k, pk in zip(ks, ps):
            if k == 0:
                out += pk * np.maximum(-w, 0.0)
            elif self.N == 1:
                wc = np.clip(w, 0, self.P_m)
                val = _clipped_normal_upper(wc, self.mu1, self.s1, self.P_m)
                val = np.where(w < 0, self.m1 - w, val)
                out += pk * val
            else:
                m, s = k * self.m1, math.sqrt(k * self.v1)
                a = (w - m) / s
                out += pk * ((m - w) * (1 - _Phi(a)) + s * _phi(a))
        return out

    def sample(self, n, rng):
        avail = rng.binomial(1, self.A, size=(n, self.N)) if self.N <= 60 else None
        if avail is not None:
            x = np.clip(self.mu1 + self.s1 * rng.standard_normal((n, self.N)), 0, self.P_m)
            return np.sum(avail * x, axis=1)
        k = rng.binomial(self.N, self.A, size=n)
        # suma de k módulos recortados ≈ N(k m1, k v1) (TLC) + corrección exacta del recorte
        return np.clip(k * self.m1 + np.sqrt(k * self.v1) * rng.standard_normal(n), 0, self.w_max)

    def partial_upper_numeric(self, w):
        g = np.linspace(0, self.w_max, 6001)
        F = self.cdf(g)
        # E[(W−w)+] = ∫_w^∞ (1 − F(x)) dx
        mask = g >= w
        if not np.any(mask):
            return 0.0
        xs = np.concatenate([[max(w, 0.0)], g[mask]])
        Fs = np.concatenate([self.cdf(np.array([max(w, 0.0)])), F[mask]])
        val = float(_trapz(1 - Fs, xs))
        if w < 0:
            val += -w
        return val


@dataclass
class EmpiricalResource(Resource):
    samples: np.ndarray = field(default_factory=lambda: np.array([0.0, 1.0]))
    name: str = "Empírica (datos)"
    short: str = "EMP"

    def __post_init__(self):
        self.samples = np.sort(np.asarray(self.samples, float))
        self.w_min = float(self.samples.min())
        self.w_max = float(self.samples.max())

    def mean(self):
        return float(self.samples.mean())

    def cdf(self, w):
        w = np.atleast_1d(np.asarray(w, float))
        return np.searchsorted(self.samples, w, side="right") / len(self.samples)

    def partial_upper(self, w):
        w = np.atleast_1d(np.asarray(w, float))
        return np.mean(np.maximum(self.samples[None, :] - w[:, None], 0.0), axis=1)

    def sample(self, n, rng):
        return rng.choice(self.samples, size=n, replace=True)

    def partial_upper_numeric(self, w):
        return float(self.partial_upper(np.array([w]))[0])


# ----------------------------------------------------------------------------
# Utilidades de análisis
# ----------------------------------------------------------------------------
def levelized_uncertainty_cost(res: Resource, cu: float, co: float) -> dict:
    """Costo de incertidumbre nivelado (USD/MWh) en el punto óptimo de programación."""
    ws, val, q = res.optimum(cu, co)
    m = res.mean()
    return {"W_s*": ws, "UCF*": val, "q*": q, "E[W]": m,
            "LUC": val / ws if ws > 1e-9 else float("nan"),
            "LUC_mean": val / m if m > 1e-9 else float("nan"),
            "W_s*/W_max": ws / res.w_max if res.w_max else float("nan")}


def method_comparison(res: Resource, cu: float, co: float, n_points: int = 60,
                      n_mc: int = 100_000, seed: int = 11) -> dict:
    """Compara analítico vs integración numérica vs Monte Carlo (error y tiempo)."""
    w = np.linspace(res.w_min, res.w_max, n_points)
    t0 = time.perf_counter(); A = res.ucf_total(w, cu, co); ta = time.perf_counter() - t0
    t0 = time.perf_counter(); u, o = res.ucf_numeric(w, cu, co); N = u + o; tn = time.perf_counter() - t0
    t0 = time.perf_counter(); u, o = res.ucf_mc(w, cu, co, n=n_mc, seed=seed); M = u + o; tm = time.perf_counter() - t0
    scale = max(np.max(np.abs(A)), 1e-9)
    return {
        "w": w, "analitico": A, "numerico": N, "montecarlo": M,
        "t_analitico_ms": 1e3 * ta, "t_numerico_ms": 1e3 * tn, "t_mc_ms": 1e3 * tm,
        "err_num_pct": 100 * float(np.max(np.abs(N - A)) / scale),
        "err_mc_pct": 100 * float(np.max(np.abs(M - A)) / scale),
    }


def quadratic_fit(res: Resource, cu: float, co: float, lo: float | None = None, hi: float | None = None, n: int = 200):
    """Aproximación cuadrática UCF ≈ α + β·W + γ·W² (para despacho económico clásico)."""
    lo = res.w_min if lo is None else lo
    hi = res.w_max if hi is None else hi
    w = np.linspace(lo, hi, n)
    y = res.ucf_total(w, cu, co)
    g, b, a = np.polyfit(w, y, 2)
    yhat = a + b * w + g * w * w
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1e-12
    return {"alpha": a, "beta": b, "gamma": g, "R2": 1 - ss_res / ss_tot, "w": w, "y": y, "yhat": yhat}


# ----------------------------------------------------------------------------
# Despacho económico con UCF (iteración lambda / costo marginal igualado)
# ----------------------------------------------------------------------------
@dataclass
class ThermalUnit:
    name: str
    Pmin: float
    Pmax: float
    a: float
    b: float
    c: float

    def P_of_lambda(self, lam):
        if self.c <= 0:
            return self.Pmax if lam >= self.b else self.Pmin
        return float(np.clip((lam - self.b) / (2 * self.c), self.Pmin, self.Pmax))

    def cost(self, P):
        return self.a + self.b * P + self.c * P * P


def economic_dispatch(demand: float, thermals: list[ThermalUnit], renewables: list[tuple[Resource, float]],
                      cu: float, co: float, voll: float = 1500.0) -> dict:
    """min Σ C_térmica(P) + Σ [d·W + UCF(W)]   s.a.  Σ P + Σ W = D.

    Condición de optimalidad (KKT) para un recurso con UCF:
        d + (c_u + c_o)·F(W) − c_u = λ   ⇒   W = F⁻¹((λ − d + c_u)/(c_u + c_o))
    """
    def supply(lam):
        Pt = [u.P_of_lambda(lam) for u in thermals]
        Wr = []
        for res, d in renewables:
            q = (lam - d + cu) / (cu + co)
            if q <= 0:
                Wr.append(0.0)
            elif q >= 1:
                Wr.append(res.w_max)
            else:
                Wr.append(float(res.ppf(q)[0]))
        return Pt, Wr, sum(Pt) + sum(Wr)

    lo, hi = -200.0, voll
    Pt, Wr, S_hi = supply(hi)
    ens = 0.0
    if S_hi < demand:           # demanda no atendida
        lam = voll
        ens = demand - S_hi
    else:
        Pt_lo, Wr_lo, S_lo = supply(lo)
        if S_lo > demand:       # exceso de mínimos técnicos
            lam, Pt, Wr = lo, Pt_lo, Wr_lo
        else:
            for _ in range(80):
                mid = 0.5 * (lo + hi)
                _, _, S = supply(mid)
                if S < demand:
                    lo = mid
                else:
                    hi = mid
            lam = hi
            Pt, Wr, S = supply(lam)
            # ajuste fino proporcional del desbalance residual en unidades no saturadas
            gap = demand - S
            if abs(gap) > 1e-6:
                flex = [i for i, u in enumerate(thermals) if u.Pmin < Pt[i] < u.Pmax]
                if flex:
                    for i in flex:
                        Pt[i] += gap / len(flex)
    thermal_cost = sum(u.cost(P) for u, P in zip(thermals, Pt))
    ucf_parts = []
    for (res, d), W in zip(renewables, Wr):
        cu_v, co_v = res.ucf(W, cu, co)
        ucf_parts.append({"recurso": res.name, "W_s": W, "costo_directo": d * W,
                          "C_u": float(cu_v[0]), "C_o": float(co_v[0]),
                          "UCF": float(cu_v[0] + co_v[0]), "E[W]": res.mean(), "W_max": res.w_max})
    total_ucf = sum(p["UCF"] for p in ucf_parts)
    direct = sum(p["costo_directo"] for p in ucf_parts)
    return {"lambda": lam, "thermal": [(u.name, P) for u, P in zip(thermals, Pt)],
            "renewables": ucf_parts, "thermal_cost": thermal_cost, "ucf_cost": total_ucf,
            "direct_cost": direct, "total_cost": thermal_cost + total_ucf + direct + voll * ens,
            "ens": ens}


# ----------------------------------------------------------------------------
# Subastas intradiarias: horizonte de pronóstico vs costo de incertidumbre
# ----------------------------------------------------------------------------
def ucf_vs_auctions(kind: str, w_max: float, cf_mean: float, cv_da: float, cu: float, co: float,
                    n_list=(1, 2, 3, 4, 6, 8, 12, 24), mtbf_h: float = 2000.0, mttr_h: float = 24.0,
                    n_modules: int = 100, sigma_floor: float = 0.02) -> list[dict]:
    """UCF* nivelado vs número de subastas diarias (horizonte τ = 24/n h).

    VRE: error de pronóstico σ(τ) = σ_DA·sqrt(τ/24) (con piso), alrededor del pronóstico.
    Firme modular: la incertidumbre proviene de fallas forzadas durante τ (Markov 2 estados):
        P_falla(τ) = λ/(λ+μ)·(1 − e^{−(λ+μ)τ})   para un módulo disponible al cierre.
    """
    out = []
    mu_w = cf_mean * w_max
    for n in n_list:
        tau = 24.0 / n
        if kind == "firme":
            lam_f, mu_r = 1.0 / mtbf_h, 1.0 / mttr_h
            p_fail = lam_f / (lam_f + mu_r) * (1 - math.exp(-(lam_f + mu_r) * tau))
            res = FirmModularResource(N=n_modules, P_m=w_max / n_modules, A=1 - p_fail,
                                      kappa=cf_mean, cv=max(cv_da, 0.005))
        else:
            sigma = max(cv_da * mu_w * math.sqrt(tau / 24.0), sigma_floor * w_max)
            res = FirmModularResource(N=1, P_m=w_max, A=1.0, kappa=min(cf_mean, 0.999),
                                      cv=sigma / max(mu_w, 1e-9))
        ws, val, q = res.optimum(cu, co)
        out.append({"subastas": n, "horizonte_h": tau, "UCF*": val,
                    "LUC": val / max(res.mean(), 1e-9), "W_s*": ws})
    return out
