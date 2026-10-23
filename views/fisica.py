import numpy as np
import plotly.graph_objects as go
import streamlit as st

from core import state, ui
from core.anim_physics import (energy_flow_animation_html, energy_flow_params, pv_cycle_animation_html,
                               pv_cycle_params)
from core.data import source_line
from core.physics import CycleParams, compression_work_ideal, cycle, err_map, sankey_data, sweep_height

ui.page_header(
    "1 · La tecnología",
    "Física y balance energético: lo que el MVP debe demostrar",
    "Cotas de primeros principios para un convertidor por flotabilidad, contabilidad de pérdidas y las condiciones "
    "físicas bajo las cuales un balance neto positivo sería posible.",
    [("Hidrostática", ""), ("Termodinámica de gases ideales", ""), ("Exergía", "mint"), ("Hipótesis falsables", "amber")],
)

PAGE = "fis"
with st.expander("⚙️ Parámetros del modelo (compartidos con la demo)", expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        state.slider("Altura H (m)", "H", PAGE, 2.0, 40.0, 0.5)
        state.slider("Aire por inserción V₀ (L)", "V0_L", PAGE, 2.0, 200.0, 1.0)
        state.slider("Frecuencia (Hz)", "f_ins", PAGE, 0.1, 4.0, 0.05)
    with c2:
        state.compression(PAGE, "Proceso de compresión")
        state.slider("η compresor", "eta_comp", PAGE, 0.40, 1.00, 0.01)
        state.slider("η motor ABIS", "eta_motor", PAGE, 0.70, 0.99, 0.01)
    with c3:
        state.slider("η captura (KEM)", "eta_cap", PAGE, 0.20, 0.98, 0.01)
        state.slider("η transmisión", "eta_gear", PAGE, 0.80, 0.995, 0.005)
        state.slider("η generador", "eta_gen", PAGE, 0.80, 0.99, 0.01)
    with c4:
        state.slider("η electrónica", "eta_pe", PAGE, 0.85, 0.995, 0.005)
        state.slider("Temperatura del agua (°C)", "T_w_C", PAGE, 5.0, 90.0, 0.5)
        state.slider("Temperatura del aire de admisión (°C)", "T_a_C", PAGE, 5.0, 45.0, 0.5)
    c5, c6, c7 = st.columns([1, 1, 2])
    with c5:
        state.slider("Altitud del sitio (m s. n. m.)", "altitude_m", PAGE, 0.0, 3000.0, 50.0)
    with c6:
        state.slider("Índice politrópico n", "n_poly", PAGE, 1.0, 1.4, 0.01)
    with c7:
        state.slider("Auxiliares (W)", "P_aux_W", PAGE, 0.0, 2000.0, 10.0)

p = state.params()
r = cycle(p)

ui.kpis([
    {"label": "Presión en la base", "value": f"{r.pH/1000:.1f} kPa", "sub": f"p_H/p₀ = {r.ratio:.3f} · ρ = {r.rho:.1f} kg/m³", "accent": ui.BRAND["navy"]},
    {"label": "Exergía del aire a profundidad", "value": f"{r.W_iso_ref:,.0f} J".replace(",", " "), "sub": "= inserción mínima reversible", "accent": ui.BRAND["blue"]},
    {"label": "Trabajo de flotación", "value": f"{r.W_buoy:,.0f} J".replace(",", " "), "sub": f"cuerpo rígido equivalente: {r.W_rigid:,.0f} J".replace(",", " "), "accent": ui.BRAND["teal"]},
    {"label": "Energía eléctrica por inserción", "value": f"{r.E_ins:,.0f} J".replace(",", " "), "sub": f"ideal ({p.compression}): {r.W_comp_ideal:,.0f} J".replace(",", " "), "accent": ui.BRAND["amber"]},
    {"label": "ERR del sistema", "value": f"{r.ERR:.3f}", "sub": f"ciclo ideal {r.ERR_ideal_cycle:.3f} · cota térmica {r.ERR_closed_bound:.3f}", "accent": ui.BRAND["green"] if r.ERR >= 1 else ui.BRAND["red"]},
])

st.html(pv_cycle_animation_html(pv_cycle_params(p, r)), unsafe_allow_javascript=True)
st.caption("Animación sincronizada con los parámetros de arriba: el punto recorre el ciclo ideal en el diagrama p–V mientras el cuerpo de aire se comprime, se inyecta a profundidad y asciende expandiéndose. Las áreas ∫V dp son el trabajo de compresión y el de flotación; las barras convierten ese balance ideal en energía eléctrica con las eficiencias elegidas.")

tab1, tab2, tab3, tab4 = st.tabs(["📐 Ecuaciones y cotas", "🔀 Flujo de energía (Sankey)", "🗺️ Mapas de diseño", "🌡️ Hipótesis de fuente adicional"])

with tab1:
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("**1. Hidrostática y expansión del aire**")
        st.latex(r"p(z)=p_0+\rho g z,\qquad V(z)=V_0\,\frac{p_0}{p(z)}\,\frac{T_w}{T_a}")
        st.markdown("**2. Trabajo de flotación (ascenso isotérmico a T_w)**")
        st.latex(r"W_{flot}=\int_0^H \rho g\,V(z)\,dz=\int_{p_0}^{p_H} V\,dp=\frac{T_w}{T_a}\,p_0V_0\ln\frac{p_H}{p_0}")
        st.markdown("**3. Trabajo de inserción (flujo estacionario)**")
        st.latex(r"W_{iso}=p_0V_0\ln\frac{p_H}{p_0}\qquad W_{n}=\frac{n}{n-1}\,p_0V_0\left[\left(\frac{p_H}{p_0}\right)^{\frac{n-1}{n}}-1\right]")
        st.markdown("**4. Indicador de balance en frontera completa**")
        st.latex(r"\mathrm{ERR}=\frac{E_{\text{salida útil}}}{E_{ABIS}+E_{aux}-\Delta E_{alm}}=\frac{\eta_{cap}\,\eta_t\,\eta_g\,\eta_{pe}\;W_{flot}\,f}{W_{n}f/(\eta_c\eta_m)+P_{aux}}")
    with c2:
        ui.callout("science", "Teorema de la frontera (ciclo cerrado, T_w = T_a)",
                   "Con compresión isotérmica reversible, <b>W<sub>flot</sub> = W<sub>iso</sub></b> exactamente, para cualquier "
                   "altura H y volumen V₀: el ascenso es una expansión que devuelve, como máximo, lo invertido en la compresión. "
                   "Toda irreversibilidad real (η &lt; 1, compresión no isotérmica, deslizamiento del aire, fricción, "
                   "auxiliares) reduce el ERR. Por tanto, en un ciclo cerrado <b>ERR ≤ 1</b> (1ª y 2ª ley).")
        ui.callout("info", "¿Y si el cuerpo fuera rígido?",
                   f"Un flotador rígido de volumen V₀ produciría ρgHV₀ = {r.W_rigid:,.0f} J al subir, pero introducirlo en la base "
                   "exige el mismo trabajo (ρgHV₀) contra la presión hidrostática. El aire, al ser compresible, rinde menos "
                   "flotación pero cuesta menos insertarlo: el cociente ideal sigue siendo 1.".replace(",", " "))
        ui.callout("warning", "Consecuencia para el programa MVP",
                   "Un ERR &gt; 1 medido de forma repetible solo puede explicarse por un flujo de energía adicional que cruza "
                   "la frontera (calor a mayor temperatura, caudal o columna de agua externa, energía almacenada que se descarga) "
                   "o por errores de medición. El protocolo debe <b>discriminar</b> entre estas hipótesis.")
        H_vals = np.linspace(1, 40, 80)
        sw = sweep_height(CycleParams(**{**p.as_dict(), "T_w_C": p.T_a_C}), H_vals)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=sw["H"], y=sw["W_rigid"], name="Cuerpo rígido: ρgHV₀", line=dict(color=ui.BRAND["gray"], dash="dot")))
        fig.add_trace(go.Scatter(x=sw["H"], y=sw["W_adiab"], name="Compresión adiabática ideal", line=dict(color=ui.BRAND["amber"], width=2)))
        fig.add_trace(go.Scatter(x=sw["H"], y=sw["W_iso"], name="Compresión isotérmica ideal", line=dict(color=ui.BRAND["red"], width=3)))
        fig.add_trace(go.Scatter(x=sw["H"], y=sw["W_buoy"], name="Trabajo de flotación", line=dict(color=ui.BRAND["teal"], width=2, dash="dash")))
        ui.style_fig(fig, height=340, title=f"Energía por inserción vs altura (V₀ = {p.V0_L:.0f} L, T_w = T_a)", yaxis_title="J", xaxis_title="H (m)")
        fig.update_layout(legend=dict(orientation="v", x=0.02, y=0.98, xanchor="left", yanchor="top", bgcolor="rgba(255,255,255,0.8)"))
        ui.show(fig, key="sweepH")
        st.caption("Las curvas de flotación e isotérmica se superponen: es la identidad W_flot = W_iso.")

with tab2:
    st.html(energy_flow_animation_html(energy_flow_params(p, r)), unsafe_allow_javascript=True)
    st.caption("Cada partícula transporta la misma potencia; en cada etapa se desvía hacia el colector de calor la fracción "
               "perdida (pérdida / potencia que llega), de modo que el flujo animado respeta el balance en promedio.")
    sk = sankey_data(p, r)
    node_colors = ["#F59E0B", "#FDBA74", "#FCD34D", "#60A5FA", "#0098D4", "#0FA99A", "#14B8A6", "#2DD4BF", "#16A34A",
                   "#CBD5E1", "#FCA5A5", "#CBD5E1", "#CBD5E1", "#CBD5E1", "#CBD5E1", "#E5484D", "#A78BFA", "#C4B5FD", "#94A3B8"]
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=[f"{n}" for n in sk["nodes"]], pad=16, thickness=16, color=node_colors,
                  line=dict(color="white", width=0.5)),
        link=dict(source=[a for a, b, v in sk["links"]], target=[b for a, b, v in sk["links"]],
                  value=[v for a, b, v in sk["links"]],
                  color=["rgba(148,163,184,0.35)"] * len(sk["links"]),
                  hovertemplate="%{source.label} → %{target.label}: %{value:.0f} W<extra></extra>"),
        valueformat=".0f", valuesuffix=" W"))
    ui.style_fig(fig, height=520, title=f"Flujo de potencia en régimen ({p.f_ins:.2f} inserciones/s)")
    ui.show(fig, key="sankey")
    losses = {k: v for k, v in r.losses.items() if v > 0.5}
    c1, c2 = st.columns([1.3, 1])
    with c1:
        fig = go.Figure(go.Bar(x=list(losses.values()), y=list(losses.keys()), orientation="h",
                               marker_color=[ui.BRAND["red"] if "Aporte" in k else ui.BRAND["gray"] for k in losses]))
        fig.update_yaxes(autorange="reversed")
        ui.style_fig(fig, height=360, title="Desglose de pérdidas y aportes (W)", xaxis_title="W")
        ui.show(fig, key="loss")
    with c2:
        st.metric("Potencia útil / potencia de entrada", ui.es_num(f"{r.ERR:.3f}"))
        st.metric("Potencia neta", ui.es_num(ui.fmt_power(r.P_net)))
        st.metric("Calor tomado del agua por inserción", f"{r.Q_water:,.0f} J".replace(",", " "))
        st.caption("En régimen, el agua devuelve como calor la mayor parte de la energía disipada; su temperatura se "
                   "estabiliza intercambiando calor con el ambiente.")

with tab3:
    c1, c2 = st.columns(2, gap="large")
    with c1:
        ek = np.linspace(0.4, 1.0, 31)
        ec = np.linspace(0.2, 1.0, 33)
        Z = err_map(p, ek, ec)
        fig = go.Figure(go.Contour(x=ek, y=ec, z=Z, colorscale=[[0, "#EAF2FB"], [0.5, "#5DB8EC"], [1, "#0B2A5B"]],
                                   contours=dict(showlabels=True, labelfont=dict(size=10, color="white")),
                                   colorbar=dict(title="ERR"), hovertemplate="η_c=%{x:.2f}<br>η_cap=%{y:.2f}<br>ERR=%{z:.3f}<extra></extra>"))
        fig.add_trace(go.Scatter(x=[p.eta_comp], y=[p.eta_cap], mode="markers", marker=dict(size=12, color=ui.BRAND["amber"], line=dict(color="white", width=2)), name="punto actual"))
        ui.style_fig(fig, height=430, title="ERR vs eficiencia del compresor y de la captura", xaxis_title="η compresor", yaxis_title="η captura (KEM)")
        ui.show(fig, key="errmap")
    with c2:
        st.markdown("**Cadena de eficiencias: ¿qué se necesitaría?**")
        best = CycleParams(**{**p.as_dict(), "compression": "isotérmica", "eta_comp": 0.95, "eta_motor": 0.97,
                              "eta_cap": 0.95, "eta_gear": 0.98, "eta_gen": 0.97, "eta_pe": 0.985})
        rb = cycle(best)
        chain = [("Compresor (vs isotérmico)", p.eta_comp if p.compression == "isotérmica" else r.W_iso_ref / r.W_comp),
                 ("Motor ABIS", p.eta_motor), ("Captura KEM", p.eta_cap), ("Transmisión", p.eta_gear),
                 ("Generador", p.eta_gen), ("Electrónica", p.eta_pe)]
        prod = np.cumprod([c[1] for c in chain])
        fig = go.Figure(go.Bar(x=[c[0] for c in chain], y=prod, marker_color=ui.BRAND["blue"], text=[ui.es_num(f"{v:.2f}") for v in prod], textposition="outside"))
        fig.add_hline(y=1, line=dict(color=ui.BRAND["red"], dash="dash"))
        ui.style_fig(fig, height=300, title="Producto acumulado de eficiencias (sin auxiliares, T_w = T_a)", yaxis_title="η acumulada")
        fig.update_yaxes(range=[0, 1.15])
        ui.show(fig, key="chain")
        ui.callout("science", "Escenario de «componentes de clase mundial»",
                   f"Aun con compresión isotérmica al 95 %, motor 97 %, captura 95 %, transmisión 98 %, generador 97 % y "
                   f"electrónica 98,5 %, el ERR sería <b>{rb.ERR:.3f}</b> con estos auxiliares. Superar 1 exige un aporte "
                   "energético adicional, no solo optimización.")

with tab4:
    st.markdown("Si el agua de la columna se mantiene a mayor temperatura que el aire de admisión (calor residual, solar térmica, "
                "geotermia de baja entalpía), el aire se calienta y se expande más durante el ascenso: el sistema se comporta como "
                "un **motor térmico de burbujas** limitado por Carnot.")
    st.latex(r"\frac{W_{flot}}{W_{iso}}=\frac{T_w}{T_a}\quad\Rightarrow\quad \mathrm{ERR}_{ideal}=\frac{T_w}{T_a},\qquad \eta_{térmica}\le 1-\frac{T_a}{T_w}")
    dT = np.linspace(0, 70, 71)
    Ta = p.T_a_C + 273.15
    ideal = (Ta + dT) / Ta
    real_chain = (r.W_iso_ref / r.W_comp) * p.eta_motor * p.eta_cap * p.eta_gear * p.eta_gen * p.eta_pe
    real = ideal * real_chain
    best_chain = 0.95 * 0.97 * 0.95 * 0.98 * 0.97 * 0.985
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dT, y=ideal, name="Ideal reversible (T_w/T_a)", line=dict(color=ui.BRAND["navy"], width=3)))
    fig.add_trace(go.Scatter(x=dT, y=ideal * best_chain, name="Componentes de clase mundial", line=dict(color=ui.BRAND["teal"], width=2)))
    fig.add_trace(go.Scatter(x=dT, y=real, name="Cadena actual (parámetros arriba)", line=dict(color=ui.BRAND["amber"], width=2, dash="dash")))
    fig.add_hline(y=1, line=dict(color=ui.BRAND["red"], dash="dot"))
    ui.style_fig(fig, height=380, title="ERR alcanzable con aporte térmico (sin auxiliares)", xaxis_title="ΔT = T_agua − T_aire (K)", yaxis_title="ERR")
    ui.show(fig, key="dT")
    dT_need = Ta * (1 / best_chain - 1)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        ui.callout("info", "Lectura cuantitativa",
                   f"Con componentes de clase mundial, el equilibrio ERR = 1 requeriría ΔT ≈ <b>{dT_need:.0f} K</b> "
                   f"(p. ej., agua a {p.T_a_C + dT_need:.0f} °C con aire a {p.T_a_C:.0f} °C), y el calor aportado sería "
                   "muchas veces mayor que la electricidad neta. Diferencias ambientales de 2–5 K no bastan.")
    with c2:
        ui.callout("eoi", "Hipótesis a discriminar en el MVP",
                   "<ol style='margin:0;padding-left:18px'><li><b>Térmica:</b> registrar T del agua, del aire y flujos de calor.</li>"
                   "<li><b>Hidráulica externa:</b> verificar que no existan aportes de caudal ni cambios de nivel.</li>"
                   "<li><b>Almacenamiento:</b> medir depósitos, volantes, baterías al inicio y al final.</li>"
                   "<li><b>Metrología:</b> potencia activa verdadera, sincronización, frontera completa.</li></ol>")
    ui.callout("science", "Opcionalidad tecnológica: almacenamiento por flotabilidad",
               "Los mismos subsistemas (inserción de gas, captura mecánica, PDU, control) son la base de tecnologías de "
               "<b>almacenamiento</b> —por flotabilidad (BEST) o aire comprimido subacuático— con eficiencias de ida y vuelta "
               "reportadas de 50–80 %. Si el MVP confirmara ERR &lt; 1, el conocimiento y la PI desarrollados conservan valor en "
               "servicios de firmeza, donde las UCF y el ELCC cuantifican su aporte.")
    ui.source(source_line("S13"))

ui.footer()
