import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import ui
from core.anim_value import fleet_animation_html, fleet_payload
from core.data import load_dispatch, source_line
from core.reliability import (availability, copt_identical, elcc_single_unit, exp_term_modular, exp_term_profile,
                              firm_capacity_identical, garver_elcc, modules_needed, pv_profile)

ui.page_header(
    "3 · Valor sistémico",
    "Firmeza y confiabilidad: cuánta potencia se puede garantizar",
    "Capacidad firme por modularidad (tabla de probabilidades de capacidad, COPT) y crédito de capacidad (ELCC) "
    "sobre el perfil real de Costa Rica. Los parámetros de los módulos IE son supuestos de escenario.",
    [("COPT binomial", ""), ("ELCC — método de Garver", ""), ("Markov de 2 estados", "mint")],
)

tab1, tab2, tab3 = st.tabs(["🧱 Modularidad y capacidad firme", "📊 Crédito de capacidad (ELCC) en Costa Rica", "🏭 Módulos para una carga 24/7"])

with tab1:
    c1, c2 = st.columns([1, 2.2], gap="large")
    with c1:
        total = st.slider("Capacidad total instalada (MW)", 1.0, 200.0, 50.0, 1.0)
        mode = st.radio("Disponibilidad del módulo", ["Directa", "MTBF / MTTR"], horizontal=True)
        mtbf = mttr = None
        if mode == "Directa":
            A = st.slider("A por módulo", 0.80, 0.999, 0.95, 0.001)
        else:
            mtbf = st.number_input("MTBF (h)", 50, 100000, 2000, 50)
            mttr = st.number_input("MTTR (h)", 1, 2000, 48, 1)
            A = availability(mtbf, mttr)
            st.caption(f"A = MTBF/(MTBF+MTTR) = {A:.4f}")
        alpha = st.select_slider("Confianza exigida α", [0.90, 0.95, 0.99, 0.999, 0.9999], value=0.99,
                                 format_func=lambda x: f"{x*100:g} %")
        N = st.select_slider("Número de módulos (para el histograma)", [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000], value=100)
    with c2:
        Pm = total / N
        cp = copt_identical(N, A, Pm)
        fc = firm_capacity_identical(N, A, Pm, alpha)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=cp["cap"], y=cp["p"], marker_color=ui.BRAND["blue"], name="P(capacidad disponible)",
                             width=max(Pm * 0.8, total / 400)))
        fig.add_vline(x=fc, line=dict(color=ui.BRAND["teal"], width=3, dash="dash"))
        fig.add_annotation(x=fc, y=float(cp["p"].max()), text=f"capacidad firme @ {alpha*100:g} %: {fc:.1f} MW", showarrow=True, ay=-30, ax=-60,
                           font=dict(color=ui.BRAND["teal"]))
        lo = max(0.0, N * A * Pm - 6 * np.sqrt(N * A * (1 - A)) * Pm - Pm) if N > 20 else -Pm
        fig.update_xaxes(range=[lo, total + Pm])
        ui.style_fig(fig, height=380, title=f"Distribución de la capacidad disponible · {N} × {Pm*1000:,.0f} kW".replace(",", " "),
                     xaxis_title="MW disponibles", yaxis_title="probabilidad")
        ui.show(fig, key="copt")
    st.html(fleet_animation_html(fleet_payload(N, A, total, alpha, mtbf, mttr)), unsafe_allow_javascript=True)
    st.caption("Misma capacidad instalada y misma disponibilidad por unidad: la planta modular se mantiene cerca de N·A·P_m y casi nunca cae por debajo del compromiso firme C_f, mientras que la unidad única alterna entre todo y nada. Simulación de Monte Carlo en tiempo continuo (Markov de 2 estados); los parámetros de los módulos IE son supuestos de escenario.")
    sizes = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]
    tbl = pd.DataFrame([{"Módulos": n, "kW por módulo": 1000 * total / n,
                         "Firme (MW)": firm_capacity_identical(n, A, total / n, alpha),
                         "Firme / instalada": firm_capacity_identical(n, A, total / n, alpha) / total} for n in sizes])
    c1, c2 = st.columns([1.3, 1], gap="large")
    with c1:
        fig = go.Figure(go.Scatter(x=tbl["Módulos"], y=100 * tbl["Firme / instalada"], mode="lines+markers",
                                   line=dict(color=ui.BRAND["teal"], width=3), marker=dict(size=8)))
        fig.add_hline(y=100 * A, line=dict(color=ui.BRAND["gray"], dash="dot"), annotation_text="disponibilidad media A")
        fig.update_xaxes(type="log")
        ui.style_fig(fig, height=330, title=f"Capacidad firme garantizada al {alpha*100:g} % vs modularidad", xaxis_title="número de módulos (log)",
                     yaxis_title="% de la capacidad instalada")
        ui.show(fig, key="mod")
    with c2:
        st.dataframe(ui.sfmt(tbl, {"kW por módulo": "{:,.0f}", "Firme (MW)": "{:.2f}", "Firme / instalada": "{:.1%}"}),
                     width="stretch", hide_index=True, height=330)
    ui.callout("science", "Resultado",
               "Con la misma disponibilidad por módulo, fraccionar la planta convierte una potencia «todo o nada» en una "
               "potencia casi determinista. La capacidad firme tiende a N·A·P_m: la arquitectura modular propuesta por "
               "Infinity Energy es coherente con los criterios de suficiencia de un operador de red.")

with tab2:
    df = load_dispatch()
    h = df["h"].to_numpy()[:-1]
    L = df["demanda_total_MW"].to_numpy()[:-1]
    c1, c2 = st.columns([1, 2.2], gap="large")
    with c1:
        m_pct = st.slider("Característica de riesgo de Garver m (% del pico)", 1.0, 10.0, 4.0, 0.5,
                          help="Capacidad adicional que multiplica la LOLE por e. Típicamente 3–6 % del pico.")
        add = st.slider("Capacidad añadida de cada recurso (MW)", 10.0, 500.0, 100.0, 10.0)
        cloud = st.slider("Atenuación FV vespertina por nubosidad", 0.0, 0.8, 0.25, 0.05)
        A_ie = st.slider("Disponibilidad módulo IE", 0.80, 0.999, 0.95, 0.001, key="elcc_A")
        pm_ie = st.select_slider("Tamaño de módulo IE (kW)", [100, 250, 500, 1000, 5000, 20000], value=500)
        q_th = st.slider("FOR de una unidad térmica equivalente", 0.01, 0.20, 0.07, 0.01)
    m = m_pct / 100 * L.max()
    prof_pv = pv_profile(h, cloud_pm=cloud) * add
    prof_w = df["eolica_MW"].to_numpy()[:-1] / 436.7 * add
    n_ie = max(1, int(round(add * 1000 / pm_ie)))
    el = {
        "Solar FV": garver_elcc(L, m, exp_term_profile(prof_pv, m)),
        "Eólica (perfil del día)": garver_elcc(L, m, exp_term_profile(prof_w, m)),
        "Térmica (1 unidad)": elcc_single_unit(add, q_th, m),
        "IE modular (escenario)": garver_elcc(L, m, exp_term_modular(n_ie, add / n_ie, A_ie, m, len(L))),
    }
    with c2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=h, y=L, name="Demanda 14-jun-2026", line=dict(color=ui.BRAND["navy"], width=3), yaxis="y1"))
        fig.add_trace(go.Scatter(x=h, y=prof_pv, name=f"FV {add:.0f} MW", line=dict(color=ui.TECH_COLORS["Solar FV"], width=2), yaxis="y2"))
        fig.add_trace(go.Scatter(x=h, y=prof_w, name=f"Eólica {add:.0f} MW", line=dict(color="#64748B", width=2), yaxis="y2"))
        fig.add_trace(go.Scatter(x=h, y=np.full_like(h, add * A_ie), name=f"IE {add:.0f} MW (esperado)", line=dict(color=ui.TECH_COLORS["IE (escenario)"], width=2, dash="dash"), yaxis="y2"))
        w = np.exp((L - L.max()) / m)
        fig.add_trace(go.Bar(x=h, y=w / w.max() * add, name="Peso de riesgo (relativo)", marker_color="rgba(229,72,77,0.18)", yaxis="y2"))
        fig.update_layout(yaxis=dict(title="Demanda (MW)"), yaxis2=dict(title="Recurso (MW)", overlaying="y", side="right", showgrid=False))
        fig.update_xaxes(tickvals=list(range(0, 25, 2)), ticktext=[f"{i}:00" for i in range(0, 25, 2)])
        ui.style_fig(fig, height=380, title="Coincidencia de cada recurso con las horas de riesgo", xaxis_title="hora")
        ui.show(fig, key="elccprof")
    names = list(el)
    vals = [100 * el[k] / add for k in names]
    fig = go.Figure(go.Bar(x=names, y=vals, text=[ui.es_num(f"{v:.0f} %") for v in vals], textposition="outside",
                           marker_color=[ui.TECH_COLORS["Solar FV"], "#64748B", ui.BRAND["red"], ui.TECH_COLORS["IE (escenario)"]]))
    fig.update_yaxes(range=[0, 110])
    ui.style_fig(fig, height=330, title="Crédito de capacidad (ELCC / capacidad instalada)", yaxis_title="%")
    ui.show(fig, key="elccbar")
    st.latex(r"\mathrm{ELCC}=m\,\ln\frac{\sum_t e^{(L_t-L_p)/m}}{\sum_t e^{(L_t-L_p)/m}\;\mathbb{E}\!\left[e^{-X_t/m}\right]},\qquad \mathbb{E}\!\left[e^{-X/m}\right]_{IE}=\left[(1-A)+A\,e^{-P_m/m}\right]^{N}")
    ui.callout("warning", "Alcance",
               "ELCC ilustrativo con un único día (domingo de junio). Un estudio formal requiere años de datos horarios, "
               "modelos de salidas forzadas del parque existente y la hidrología. Aun así, el patrón es robusto: la FV aporta "
               "poco al pico vespertino; un recurso firme modular aporta cerca de su disponibilidad.")
    ui.source(source_line("S11", "V1"))

with tab3:
    c1, c2 = st.columns([1, 1.6], gap="large")
    with c1:
        target = st.number_input("Carga 24/7 a respaldar (MW)", 1.0, 2000.0, 250.0, 10.0)
        pm = st.select_slider("Potencia neta por módulo (kW)", [50, 100, 250, 500, 1000, 2000, 5000], value=500, key="t3pm")
        A3 = st.slider("Disponibilidad por módulo", 0.80, 0.999, 0.95, 0.001, key="t3A")
    rows = []
    for a in [0.99, 0.999, 0.9999]:
        n = modules_needed(target, pm / 1000, A3, a)
        rows.append({"Confiabilidad": f"{a*100:g} %", "Módulos": n, "Instalado (MW)": n * pm / 1000,
                     "Reserva sobre la carga": n * pm / 1000 / target - 1})
    t3 = pd.DataFrame(rows)
    with c2:
        st.dataframe(ui.sfmt(t3, {"Instalado (MW)": "{:,.1f}", "Reserva sobre la carga": "{:.1%}"}), width="stretch", hide_index=True)
        fig = go.Figure(go.Bar(x=t3["Confiabilidad"], y=t3["Instalado (MW)"], marker_color=ui.BRAND["teal"],
                               text=[ui.es_num(f"{v:,.0f} MW") for v in t3["Instalado (MW)"]], textposition="outside"))
        fig.add_hline(y=target, line=dict(color=ui.BRAND["navy"], dash="dash"), annotation_text="carga")
        ui.style_fig(fig, height=300, title="Capacidad instalada necesaria", yaxis_title="MW")
        ui.show(fig, key="t3")
    ui.callout("eoi", "Especificación derivada del sistema",
               f"Para respaldar {target:,.0f} MW al 99,9 % con módulos de {pm} kW y A = {A3:.3f} se requieren "
               f"{t3.iloc[1]['Módulos']:,} módulos (reserva {t3.iloc[1]['Reserva sobre la carga']:.1%}). Estas cifras convierten "
               "objetivos comerciales en requisitos de ingeniería medibles en el MVP: MTBF, MTTR y potencia neta por módulo.".replace(",", " "))

ui.footer()
