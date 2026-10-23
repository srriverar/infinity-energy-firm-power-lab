import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core import ui
from core.anim_value import ucf_stream_animation_html, ucf_stream_payload
from core.ucf import (FirmModularResource, HydroRoRResource, NormalResource, PVResource, ThermalUnit,
                      UniformResource, WindResource, economic_dispatch, levelized_uncertainty_cost,
                      method_comparison, quadratic_fit, ucf_vs_auctions)

ui.page_header(
    "3 · Valor sistémico",
    "Funciones de costo de incertidumbre (UCF): el valor económico de la firmeza",
    "Las UCF cuantifican el costo esperado de programar un recurso estocástico: penalización por subestimar "
    "(energía disponible no programada) y por sobreestimar (energía programada no entregada que debe reponerse). "
    "Permiten comparar tecnologías en la misma moneda e incorporarlas al despacho económico y al flujo óptimo.",
    [("Marco UCF / MUCF", ""), ("Analítico + numérico + Monte Carlo", "mint"), ("Despacho económico", ""), ("IE como escenario", "amber")],
)

# ----------------------------------------------------------------------------- controles globales
c1, c2, c3 = st.columns([1, 1, 1.4], gap="large")
with c1:
    cu = st.slider("c_u · penalización por subestimación (USD/MWh)", 1.0, 200.0, 50.0, 1.0,
                   help="Costo de oportunidad de energía disponible no programada (vertimiento, recorte).")
with c2:
    co = st.slider("c_o · penalización por sobreestimación (USD/MWh)", 10.0, 600.0, 300.0, 5.0,
                   help="Costo de reponer energía programada no entregada (reserva, térmica, importación).")
with c3:
    q = cu / (cu + co)
    ui.kpis([{"label": "Cuantil crítico q* = c_u/(c_u+c_o)", "value": f"{q:.3f}",
              "sub": "W_s* es el cuantil q* de la potencia disponible", "accent": ui.BRAND["navy"]}])

with st.expander("🔧 Parámetros de los recursos (capacidad común para comparar)", expanded=False):
    cap = st.slider("Capacidad nominal común (MW)", 5.0, 200.0, 50.0, 5.0)
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        st.markdown("**Solar FV** · irradiancia log-normal")
        G_mean = st.slider("Irradiancia media de la hora (W/m²)", 100.0, 950.0, 600.0, 10.0)
        G_cv = st.slider("Coef. de variación irradiancia", 0.05, 1.0, 0.45, 0.01)
    with a2:
        st.markdown("**Eólica** · Weibull (k=2 → Rayleigh)")
        wk = st.slider("Forma k", 1.2, 3.5, 2.0, 0.1)
        wc = st.slider("Escala c (m/s)", 3.0, 14.0, 8.5, 0.1)
    with a3:
        st.markdown("**PCH filo de agua** · caudal Gumbel")
        Qm = st.slider("Caudal medio (m³/s)", 5.0, 80.0, 40.0, 1.0)
        Qs = st.slider("Desviación del caudal (m³/s)", 1.0, 40.0, 12.0, 0.5)
        head = st.slider("Salto neto (m)", 20.0, 400.0, 120.0, 5.0)
    with a4:
        st.markdown("**Planta modular firme (IE)** · supuestos")
        Nm = st.select_slider("Número de módulos", [1, 2, 5, 10, 20, 50, 100, 200, 500], value=100)
        Am = st.slider("Disponibilidad por módulo A", 0.80, 0.999, 0.95, 0.001)
        cvm = st.slider("Variabilidad de salida (CV)", 0.0, 0.20, 0.03, 0.005)

P = dict(cap=cap, G_mean=G_mean, G_cv=G_cv, wk=wk, wc=wc, Qm=Qm, Qs=Qs, head=head, Nm=Nm, Am=Am, cvm=cvm)


def build(kind: str, P: dict):
    if kind == "Solar FV":
        return PVResource(P_r=P["cap"], G_mean=P["G_mean"], G_cv=P["G_cv"])
    if kind == "Eólica":
        return WindResource(W_r=P["cap"], k=P["wk"], c=P["wc"])
    if kind == "PCH filo de agua":
        return HydroRoRResource(P_max=P["cap"], Q_mean=P["Qm"], Q_std=P["Qs"], head=P["head"])
    if kind == "IE (escenario)":
        return FirmModularResource(N=int(P["Nm"]), P_m=P["cap"] / int(P["Nm"]), A=P["Am"], cv=max(P["cvm"], 1e-4))
    if kind == "VE / carga controlable":
        return NormalResource(mu=0.5 * P["cap"], sigma=0.12 * P["cap"])
    return UniformResource(a=0.0, b=P["cap"])


KINDS = ["Solar FV", "Eólica", "PCH filo de agua", "IE (escenario)", "VE / carga controlable", "Uniforme (simplificada)"]
MAIN = ["Solar FV", "Eólica", "PCH filo de agua", "IE (escenario)"]
COL = {"Solar FV": ui.TECH_COLORS["Solar FV"], "Eólica": "#64748B", "PCH filo de agua": ui.TECH_COLORS["PCH filo de agua"],
       "IE (escenario)": ui.TECH_COLORS["IE (escenario)"], "VE / carga controlable": ui.BRAND["violet"],
       "Uniforme (simplificada)": ui.BRAND["gray"]}



@st.cache_data(show_spinner=False)
def stream_payload(P: dict, cu: float, co: float) -> dict:
    return ucf_stream_payload([(k, COL[k], build(k, P)) for k in MAIN], cu, co)


st.html(ucf_stream_animation_html(stream_payload(P, cu, co)), unsafe_allow_javascript=True)
st.caption("Cada recurso se programa en su óptimo W_s* = F⁻¹(q*) y en cada intervalo se liquida la desviación: c_u por la "
           "energía disponible no programada y c_o por la energía programada no entregada. Las series son sintéticas pero "
           "siguen exactamente la distribución de cada modelo (parámetros arriba), por lo que el costo medio realizado converge "
           "a la UCF* analítica. La planta IE es un escenario a validar en el MVP.")

@st.cache_data(show_spinner=False)
def summary_table(P: dict, cu: float, co: float):
    rows = []
    curves = {}
    for k in MAIN:
        res = build(k, P)
        L = levelized_uncertainty_cost(res, cu, co)
        w = res.grid(300)
        curves[k] = (w / res.w_max, res.ucf_total(w, cu, co))
        rows.append({"Tecnología": k, "E[W] (MW)": L["E[W]"], "Factor de capacidad": L["E[W]"] / res.w_max,
                     "W_s* (MW)": L["W_s*"], "W_s*/W_max": L["W_s*/W_max"], "UCF* (USD/h)": L["UCF*"],
                     "UCF*/E[W] (USD/MWh)": L["LUC_mean"]})
    return pd.DataFrame(rows), curves


tabs = st.tabs(["📘 Fundamentos", "⚖️ Comparación", "✅ Verificación", "🧱 Modularidad", "🏭 Despacho con UCF",
                "📈 Cuadrática", "⏱️ Subastas intradiarias"])

# ----------------------------------------------------------------------------- Fundamentos
with tabs[0]:
    c1, c2 = st.columns([1, 1.6], gap="large")
    with c1:
        st.markdown("**Definiciones** (W: potencia disponible; W_s: potencia programada)")
        st.latex(r"C_u(W_s)=c_u\!\int_{W_s}^{W_{max}}\!(w-W_s)\,f_W(w)\,dw")
        st.latex(r"C_o(W_s)=c_o\!\int_{W_{min}}^{W_s}\!(W_s-w)\,f_W(w)\,dw")
        st.latex(r"\mathrm{UCF}(W_s)=C_u(W_s)+C_o(W_s)")
        st.markdown("**Costo marginal de incertidumbre (MUCF) y convexidad**")
        st.latex(r"\mathrm{MUCF}(W_s)=\frac{d\,\mathrm{UCF}}{dW_s}=(c_u+c_o)\,F_W(W_s)-c_u")
        st.latex(r"\frac{d^2\mathrm{UCF}}{dW_s^2}=(c_u+c_o)\,f_W(W_s)\ge 0\quad\text{(convexa)}")
        st.latex(r"W_s^{*}=F_W^{-1}\!\left(\frac{c_u}{c_u+c_o}\right)")
        st.caption("Modelos primarios: irradiancia log-normal (FV), viento Weibull/Rayleigh, caudal Gumbel (PCH), "
                   "Normal (VE / carga controlable), Uniforme (simplificación) y mezcla binomial–normal (planta modular).")
    with c2:
        SHORT = {"Solar FV": "Solar FV", "Eólica": "Eólica", "PCH filo de agua": "PCH", "IE (escenario)": "IE",
                 "VE / carga controlable": "VE / carga", "Uniforme (simplificada)": "Uniforme"}
        kind = st.pills("Recurso", KINDS, default="Solar FV", key="fund_kind", format_func=lambda k: SHORT[k]) or "Solar FV"
        res = build(kind, P)
        ws_star, ucf_star, _ = res.optimum(cu, co)
        frac = st.slider("Potencia programada W_s (fracción del rango)", 0.0, 1.0,
                         float(np.clip((ws_star - res.w_min) / (res.w_max - res.w_min), 0, 1)), 0.01, key="fund_ws")
        ws = res.w_min + frac * (res.w_max - res.w_min)
        rng = np.random.default_rng(1)
        smp = res.sample(60_000, rng)
        bins = np.linspace(res.w_min, res.w_max, 61)
        hist, edges = np.histogram(smp, bins=bins, density=True)
        mids = 0.5 * (edges[1:] + edges[:-1])
        w = res.grid(400)
        Cu, Co = res.ucf(w, cu, co)
        mu = res.mucf(w, cu, co)
        fig = make_subplots(rows=1, cols=2, subplot_titles=("Distribución de la potencia disponible", "UCF y sus componentes"),
                            horizontal_spacing=0.1)
        fig.add_trace(go.Bar(x=mids, y=hist, marker_color=[ui.BRAND["red"] if m < ws else ui.BRAND["blue"] for m in mids],
                             opacity=0.75, name="f_W (Monte Carlo)", showlegend=False), 1, 1)
        fig.add_vline(x=ws, line=dict(color=ui.BRAND["navy"], width=2), row=1, col=1)
        fig.add_annotation(x=ws, y=float(hist.max()) * 0.95, text=" W_s", showarrow=False, xanchor="left", row=1, col=1)
        fig.add_trace(go.Scatter(x=w, y=Cu, name="C_u (subestimación)", line=dict(color=ui.BRAND["blue"], width=2)), 1, 2)
        fig.add_trace(go.Scatter(x=w, y=Co, name="C_o (sobreestimación)", line=dict(color=ui.BRAND["red"], width=2)), 1, 2)
        fig.add_trace(go.Scatter(x=w, y=Cu + Co, name="UCF", line=dict(color=ui.BRAND["navy"], width=3)), 1, 2)
        fig.add_trace(go.Scatter(x=[ws_star], y=[ucf_star], mode="markers", marker=dict(size=12, color=ui.BRAND["mint"], line=dict(color="#0B2A5B", width=2)), name="mínimo W_s*"), 1, 2)
        fig.add_trace(go.Scatter(x=[ws], y=[float(res.ucf_total(ws, cu, co)[0])], mode="markers", marker=dict(size=10, color=ui.BRAND["amber"]), name="W_s elegido"), 1, 2)
        fig.update_xaxes(title_text="MW", row=1, col=1)
        fig.update_xaxes(title_text="W_s (MW)", row=1, col=2)
        fig.update_yaxes(title_text="densidad", row=1, col=1)
        fig.update_yaxes(title_text="USD/h", row=1, col=2)
        ui.style_fig(fig, height=420)
        ui.show(fig, key="fund1")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=w, y=mu, name="MUCF", line=dict(color=ui.BRAND["violet"], width=3)))
        fig.add_hline(y=0, line=dict(color="#94A3B8"))
        fig.add_vline(x=ws_star, line=dict(color=ui.BRAND["mint"], dash="dash"))
        ui.style_fig(fig, height=250, title="Costo marginal de incertidumbre: cruza cero en W_s* (saltos = masas de probabilidad)",
                     yaxis_title="USD/MWh", xaxis_title="W_s (MW)")
        ui.show(fig, key="fund2")
        ui.kpis([
            {"label": "E[W]", "value": f"{res.mean():.2f} MW", "accent": ui.BRAND["blue"]},
            {"label": "W_s* (óptimo)", "value": f"{ws_star:.2f} MW", "sub": f"F(W_s*) = {float(res.cdf(ws_star)[0]):.3f} ≥ q* = {q:.3f}", "accent": ui.BRAND["mint"]},
            {"label": "UCF mínima", "value": f"{ucf_star:,.1f} USD/h".replace(",", " "), "accent": ui.BRAND["navy"]},
            {"label": "UCF en W_s elegido", "value": f"{float(res.ucf_total(ws, cu, co)[0]):,.1f} USD/h".replace(",", " "), "accent": ui.BRAND["amber"]},
        ])

# ----------------------------------------------------------------------------- Comparación
with tabs[1]:
    df, curves = summary_table(P, cu, co)
    c1, c2 = st.columns([1.5, 1], gap="large")
    with c1:
        fig = go.Figure()
        for k, (x, y) in curves.items():
            fig.add_trace(go.Scatter(x=x, y=y, name=k, line=dict(color=COL[k], width=3 if k.startswith("IE") else 2)))
        ui.style_fig(fig, height=420, title=f"UCF vs potencia programada (todas con {cap:.0f} MW nominales)",
                     xaxis_title="W_s / W_max", yaxis_title="USD/h")
        ui.show(fig, key="cmp1")
    with c2:
        fig = go.Figure(go.Bar(x=df["Tecnología"], y=df["UCF*/E[W] (USD/MWh)"], marker_color=[COL[k] for k in df["Tecnología"]],
                               text=[ui.es_num(f"{v:.1f}") for v in df["UCF*/E[W] (USD/MWh)"]], textposition="outside"))
        ui.style_fig(fig, height=420, title="Costo de incertidumbre nivelado en el óptimo", yaxis_title="USD por MWh esperado")
        ui.show(fig, key="cmp2")
    st.dataframe(ui.sfmt(df, {"E[W] (MW)": "{:.2f}", "Factor de capacidad": "{:.1%}", "W_s* (MW)": "{:.2f}",
                                  "W_s*/W_max": "{:.1%}", "UCF* (USD/h)": "{:,.1f}", "UCF*/E[W] (USD/MWh)": "{:.2f}"}),
                 width="stretch", hide_index=True)
    ie = df[df["Tecnología"] == "IE (escenario)"].iloc[0]
    best_vre = df[df["Tecnología"] != "IE (escenario)"]["UCF*/E[W] (USD/MWh)"].min()
    ui.callout("eoi", "Lectura para la convocatoria",
               f"Con los supuestos de escenario (N = {Nm} módulos, A = {Am:.3f}, CV = {cvm:.1%}), la planta modular tendría un "
               f"costo de incertidumbre de <b>{ie['UCF*/E[W] (USD/MWh)']:.2f} USD/MWh</b> frente a {best_vre:.2f} USD/MWh del "
               "mejor recurso variable. Este diferencial es parte del <b>valor de la firmeza</b> que un MVP validado podría "
               "capturar, y define especificaciones objetivo: disponibilidad, variabilidad y tamaño de módulo.")

# ----------------------------------------------------------------------------- Verificación
with tabs[2]:
    c1, c2 = st.columns([1, 2.2], gap="large")
    with c1:
        kv = st.radio("Recurso a verificar", KINDS, index=0, key="ver_kind")
        n_mc = st.select_slider("Muestras Monte Carlo", [10_000, 50_000, 100_000, 200_000, 400_000], value=100_000)
        st.caption("El método analítico usa momentos parciales en forma cerrada (Φ para log-normal/normal, función gamma "
                   "incompleta para Weibull, integral exponencial E₁ para Gumbel). La integración numérica usa cuadratura "
                   "adaptativa sobre la variable primaria.")

    @st.cache_data(show_spinner="Comparando métodos…")
    def _cmp(kind, P, cu, co, n_mc):
        res = build(kind, P)
        return method_comparison(res, cu, co, n_points=25, n_mc=n_mc)

    mc = _cmp(kv, P, cu, co, n_mc)
    with c2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=mc["w"], y=mc["analitico"], name="Analítico", line=dict(color=ui.BRAND["navy"], width=3)))
        fig.add_trace(go.Scatter(x=mc["w"], y=mc["numerico"], name="Integración numérica", mode="markers", marker=dict(symbol="circle-open", size=10, color=ui.BRAND["teal"], line=dict(width=2))))
        fig.add_trace(go.Scatter(x=mc["w"], y=mc["montecarlo"], name="Monte Carlo", mode="markers", marker=dict(symbol="x", size=8, color=ui.BRAND["amber"])))
        ui.style_fig(fig, height=380, title=f"UCF de «{kv}»: tres métodos", xaxis_title="W_s (MW)", yaxis_title="USD/h")
        ui.show(fig, key="ver")
    ui.kpis([
        {"label": "Tiempo analítico (25 pts)", "value": f"{mc['t_analitico_ms']:.1f} ms", "accent": ui.BRAND["navy"]},
        {"label": "Tiempo integración numérica", "value": f"{mc['t_numerico_ms']:.0f} ms", "sub": f"error máx. {mc['err_num_pct']:.4f} %", "accent": ui.BRAND["teal"]},
        {"label": "Tiempo Monte Carlo", "value": f"{mc['t_mc_ms']:.0f} ms", "sub": f"error máx. {mc['err_mc_pct']:.3f} %", "accent": ui.BRAND["amber"]},
        {"label": "Aceleración analítica", "value": f"×{mc['t_mc_ms'] / max(mc['t_analitico_ms'], 1e-3):,.0f}".replace(",", " "), "sub": "vs Monte Carlo", "accent": ui.BRAND["green"]},
    ])
    ui.callout("science", "Por qué importa",
               "Las expresiones analíticas permiten evaluar UCF y MUCF miles de veces por segundo: viable dentro de "
               "despachos económicos, flujos óptimos de potencia y metaheurísticas. Monte Carlo sirve como verificación "
               "independiente y para distribuciones empíricas (p. ej., datos de los MVP).")

# ----------------------------------------------------------------------------- Firmeza modular
with tabs[3]:
    @st.cache_data(show_spinner="Calculando mapa de firmeza…")
    def _heat(cvv, cap, cu, co):
        A_vals = np.round(np.linspace(0.70, 0.995, 21), 4)
        N_vals = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500]
        Z = np.zeros((len(N_vals), len(A_vals)))
        for i, n in enumerate(N_vals):
            for j, a in enumerate(A_vals):
                r_ = FirmModularResource(N=n, P_m=cap / n, A=float(a), cv=max(float(cvv), 1e-4))
                Z[i, j] = levelized_uncertainty_cost(r_, cu, co)["LUC_mean"]
        return A_vals, N_vals, Z

    @st.cache_data(show_spinner=False)
    def _vsN(A, cvv, cap, cu, co):
        Ns = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500, 1000]
        out = []
        for n in Ns:
            r_ = FirmModularResource(N=n, P_m=cap / n, A=A, cv=max(cvv, 1e-4))
            L = levelized_uncertainty_cost(r_, cu, co)
            out.append((n, L["LUC_mean"], L["W_s*/W_max"]))
        return out

    df_cmp, _ = summary_table(P, cu, co)
    A_vals, N_vals, Z = _heat(cvm, cap, cu, co)
    c1, c2 = st.columns([1.3, 1], gap="large")
    with c1:
        ylab = [str(n) for n in N_vals]
        fig = go.Figure(go.Heatmap(x=A_vals, y=ylab, z=Z, colorscale="Tealgrn", reversescale=True, zmin=0,
                                   zmax=float(np.nanpercentile(Z, 95)), colorbar=dict(title="USD/MWh"),
                                   hovertemplate="A=%{x:.3f}<br>N=%{y}<br>UCF*/E[W]=%{z:.2f} USD/MWh<extra></extra>"))
        for _, row in df_cmp[df_cmp["Tecnología"] != "IE (escenario)"].iterrows():
            lvl = float(row["UCF*/E[W] (USD/MWh)"])
            fig.add_trace(go.Contour(x=A_vals, y=ylab, z=Z, showscale=False,
                                     contours=dict(start=lvl, end=lvl, size=1, coloring="none", showlabels=False),
                                     line=dict(color=COL[row["Tecnología"]], width=3, dash="dash"),
                                     name=f"= {row['Tecnología']} ({lvl:.1f})".replace(".", ","), hoverinfo="skip", showlegend=True))
        fig.add_trace(go.Scatter(x=[Am], y=[str(Nm)], mode="markers", marker=dict(size=13, color="white", line=dict(color="#0B2A5B", width=3)), name="escenario"))
        ui.style_fig(fig, height=460, title=f"Costo de incertidumbre de la planta modular (CV = {cvm:.1%}, {cap:.0f} MW)",
                     xaxis_title="Disponibilidad por módulo A", yaxis_title="Número de módulos N")
        ui.show(fig, key="heat")
        st.caption("Líneas discontinuas: nivel de costo de incertidumbre de cada recurso variable. A la derecha y por encima de "
                   "cada línea (más módulos, mayor disponibilidad) la planta firme supera a ese recurso: zona objetivo de "
                   "especificación del MVP.")
    with c2:
        vs = _vsN(Am, cvm, cap, cu, co)
        fig = go.Figure(go.Scatter(x=[v[0] for v in vs], y=[v[1] for v in vs], mode="lines+markers", line=dict(color=ui.BRAND["teal"], width=3)))
        fig.update_xaxes(type="log")
        ui.style_fig(fig, height=300, title="Efecto de la modularidad (misma capacidad total)", xaxis_title="Número de módulos (log)", yaxis_title="USD/MWh")
        ui.show(fig, key="vsN")
        ui.callout("science", "Ley de los grandes números",
                   f"Una sola unidad de {cap:.0f} MW con A = {Am:.3f} concentra el riesgo: su falla elimina toda la potencia. "
                   "Con muchos módulos independientes la potencia disponible se concentra alrededor de N·A·P_m y el costo de "
                   "incertidumbre cae drásticamente. La modularidad es una <b>ventaja de diseño medible</b>.")

# ----------------------------------------------------------------------------- Despacho económico
with tabs[4]:
    st.markdown("Despacho de un periodo con unidades térmicas cuadráticas y recursos con UCF. Condición de optimalidad (KKT):")
    st.latex(r"\frac{dC_i}{dP_i}=b_i+2c_iP_i=\lambda\quad;\quad d_j+(c_u+c_o)F_j(W_j)-c_u=\lambda\;\Rightarrow\;W_j=F_j^{-1}\!\left(\frac{\lambda-d_j+c_u}{c_u+c_o}\right)")
    default_th = pd.DataFrame([
        {"Unidad": "T1 búnker", "Pmin": 20.0, "Pmax": 150.0, "a": 500.0, "b": 150.0, "c": 0.05},
        {"Unidad": "T2 diésel", "Pmin": 10.0, "Pmax": 120.0, "a": 300.0, "b": 190.0, "c": 0.08},
        {"Unidad": "T3 alquiler", "Pmin": 0.0, "Pmax": 273.0, "a": 200.0, "b": 230.0, "c": 0.10},
    ])
    c1, c2 = st.columns([1.4, 1], gap="large")
    with c1:
        th_df = st.data_editor(default_th, num_rows="dynamic", width="stretch", key="th_editor")
    with c2:
        demand = st.slider("Demanda del periodo (MW)", 100.0, 900.0, 450.0, 10.0)
        d_var = st.slider("Costo directo recursos renovables d (USD/MWh)", 0.0, 40.0, 5.0, 1.0)
        d_ie = st.slider("Costo directo planta IE d (USD/MWh, supuesto)", 0.0, 120.0, 10.0, 1.0)
    thermals = [ThermalUnit(str(r_["Unidad"]), float(r_["Pmin"]), float(r_["Pmax"]), float(r_["a"]), float(r_["b"]), float(r_["c"]))
                for _, r_ in th_df.dropna().iterrows()]

    @st.cache_data(show_spinner="Resolviendo despachos…")
    def _ed(th_records, demand, P, cu, co, d_var, d_ie):
        ths = [ThermalUnit(**t) for t in th_records]
        base = [(build("Solar FV", P), d_var), (build("Eólica", P), d_var), (build("PCH filo de agua", P), d_var)]
        out = {}
        for opt in ["Ninguno", "Solar FV", "Eólica", "PCH filo de agua", "IE (escenario)"]:
            ren = list(base)
            if opt != "Ninguno":
                ren.append((build(opt, P), d_ie if opt.startswith("IE") else d_var))
            out[opt] = economic_dispatch(demand, ths, ren, cu, co)
        return out

    th_records = [dict(name=t.name, Pmin=t.Pmin, Pmax=t.Pmax, a=t.a, b=t.b, c=t.c) for t in thermals]
    eds = _ed(th_records, demand, P, cu, co, d_var, d_ie)
    rows = []
    for opt, ed in eds.items():
        rows.append({"Recurso adicional": opt if opt != "Ninguno" else "— (base: FV + eólica + PCH)",
                     "λ (USD/MWh)": ed["lambda"], "Costo total (USD/h)": ed["total_cost"], "Costo térmico (USD/h)": ed["thermal_cost"],
                     "Costo de incertidumbre (USD/h)": ed["ucf_cost"], "Térmica (MW)": sum(P_ for _, P_ in ed["thermal"]),
                     "ENS (MW)": ed["ens"]})
    tab = pd.DataFrame(rows)
    base_cost = tab.iloc[0]["Costo total (USD/h)"]
    tab["Ahorro vs base (USD/h)"] = base_cost - tab["Costo total (USD/h)"]
    c1, c2 = st.columns([1.2, 1], gap="large")
    with c1:
        fig = go.Figure()
        labels = [r_.replace("— (base: FV + eólica + PCH)", "Base") for r_ in tab["Recurso adicional"]]
        fig.add_trace(go.Bar(x=labels, y=tab["Costo térmico (USD/h)"], name="Costo térmico", marker_color=ui.BRAND["red"]))
        fig.add_trace(go.Bar(x=labels, y=tab["Costo de incertidumbre (USD/h)"], name="Costo de incertidumbre (UCF)", marker_color=ui.BRAND["navy"]))
        fig.update_layout(barmode="stack")
        ui.style_fig(fig, height=400, title=f"Costo del sistema al añadir {cap:.0f} MW de cada tecnología", yaxis_title="USD/h")
        ui.show(fig, key="edbar")
    with c2:
        fig = go.Figure(go.Bar(x=labels[1:], y=tab["Ahorro vs base (USD/h)"].iloc[1:], marker_color=[COL[k] for k in list(eds)[1:]],
                               text=[ui.es_num(f"{v:,.0f}") for v in tab["Ahorro vs base (USD/h)"].iloc[1:]], textposition="outside"))
        ui.style_fig(fig, height=400, title="Ahorro horario frente al caso base", yaxis_title="USD/h")
        ui.show(fig, key="edsav")
    st.dataframe(ui.sfmt(tab, {c: "{:,.1f}" for c in tab.columns if c != "Recurso adicional"}), width="stretch", hide_index=True)
    sel = st.selectbox("Detalle del despacho", list(eds), index=4)
    ed = eds[sel]
    det = [{"Unidad / recurso": n, "Potencia (MW)": P_, "Tipo": "térmica"} for n, P_ in ed["thermal"]]
    det += [{"Unidad / recurso": d_["recurso"], "Potencia (MW)": d_["W_s"], "Tipo": ui.es_num(f"UCF = {d_['UCF']:,.0f} USD/h · E[W] = {d_['E[W]']:.1f} MW")} for d_ in ed["renewables"]]
    st.dataframe(ui.sfmt(pd.DataFrame(det), {"Potencia (MW)": "{:.1f}"}), width="stretch", hide_index=True)
    ui.callout("science", "Interpretación",
               "Con UCF, los recursos variables se programan en un cuantil conservador que depende de λ y de las penalizaciones; "
               "la planta firme se programa cerca de su potencia disponible esperada y desplaza más generación térmica por MW "
               "instalado. El ahorro horario es una medida directa del <b>valor sistémico</b> de cada tecnología.")

# ----------------------------------------------------------------------------- Cuadrática
with tabs[5]:
    @st.cache_data(show_spinner=False)
    def _quad(P, cu, co):
        out = []
        fits = {}
        for k in MAIN:
            res = build(k, P)
            qf = quadratic_fit(res, cu, co)
            fits[k] = qf
            out.append({"Recurso": k, "α (USD/h)": qf["alpha"], "β (USD/MWh)": qf["beta"], "γ (USD/MW²h)": qf["gamma"], "R²": qf["R2"]})
        return pd.DataFrame(out), fits

    qdf, fits = _quad(P, cu, co)
    c1, c2 = st.columns([1, 1.3], gap="large")
    with c1:
        st.markdown("Aproximación **UCF(W) ≈ α + β·W + γ·W²**, compatible con despachos económicos clásicos (costos cuadráticos) "
                    "y con solvers QP.")
        st.dataframe(ui.sfmt(qdf, {"α (USD/h)": "{:,.2f}", "β (USD/MWh)": "{:,.3f}", "γ (USD/MW²h)": "{:,.4f}", "R²": "{:.4f}"}),
                     width="stretch", hide_index=True)
        kq = st.radio("Mostrar ajuste de", MAIN, horizontal=True)
    with c2:
        qf = fits[kq]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=qf["w"], y=qf["y"], name="UCF exacta", line=dict(color=COL[kq], width=3)))
        fig.add_trace(go.Scatter(x=qf["w"], y=qf["yhat"], name="Ajuste cuadrático", line=dict(color=ui.BRAND["navy"], dash="dash")))
        ui.style_fig(fig, height=380, title=f"Ajuste cuadrático · {kq} (R² = {qf['R2']:.4f})", xaxis_title="W (MW)", yaxis_title="USD/h")
        ui.show(fig, key="quad")

# ----------------------------------------------------------------------------- Horizonte
with tabs[6]:
    c1, c2 = st.columns([1, 2], gap="large")
    with c1:
        cv_pv = st.slider("Error de pronóstico día-antes FV (CV)", 0.05, 0.6, 0.30, 0.01)
        cv_w = st.slider("Error de pronóstico día-antes eólica (CV)", 0.05, 0.8, 0.40, 0.01)
        mtbf = st.slider("MTBF por módulo IE (h)", 200, 20000, 2000, 100)
        mttr = st.slider("MTTR por módulo IE (h)", 1, 240, 24, 1)
        st.caption("Modelo: σ(τ) = σ_DA·√(τ/24) para recursos variables; para la planta modular, probabilidad de falla dentro "
                   "del horizonte τ con un modelo de Markov de dos estados.")

    @st.cache_data(show_spinner=False)
    def _auc(cap, cu, co, cv_pv, cv_w, mtbf, mttr, Nm, cvm):
        return {
            "Solar FV": ucf_vs_auctions("vre", cap, 0.55, cv_pv, cu, co),
            "Eólica": ucf_vs_auctions("vre", cap, 0.40, cv_w, cu, co),
            "IE (escenario)": ucf_vs_auctions("firme", cap, 0.95, cvm, cu, co, mtbf_h=mtbf, mttr_h=mttr, n_modules=int(Nm)),
        }

    auc = _auc(cap, cu, co, cv_pv, cv_w, mtbf, mttr, Nm, max(cvm, 0.005))
    with c2:
        fig = go.Figure()
        for k, v in auc.items():
            fig.add_trace(go.Scatter(x=[d["subastas"] for d in v], y=[d["LUC"] for d in v], name=k, mode="lines+markers",
                                     line=dict(color=COL[k], width=3 if k.startswith("IE") else 2)))
        fig.update_xaxes(type="log", tickvals=[1, 2, 3, 4, 6, 8, 12, 24])
        ui.style_fig(fig, height=400, title="Costo de incertidumbre vs número de subastas intradiarias", xaxis_title="subastas por día (horizonte = 24/n h)", yaxis_title="USD por MWh esperado")
        ui.show(fig, key="auc")
    ui.callout("eoi", "Implicación",
               "Los recursos variables reducen su costo de incertidumbre con mercados más frecuentes (mejores pronósticos); una "
               "fuente firme lo mantiene bajo con independencia del horizonte. Para usuarios 24/7 (centros de datos, industria) "
               "y sistemas aislados sin mercados intradiarios, esa diferencia es valor directo.")

ui.callout("info", "Nota metodológica",
           "El marco de funciones de costo de incertidumbre (UCF) y sus expresiones marginales proviene de la literatura de "
           "despacho económico estocástico con fuentes renovables, vehículos eléctricos y cargas controlables. La implementación "
           "de esta demo es propia (analítica, numérica y Monte Carlo) y sus parámetros son ilustrativos.")
ui.footer()
