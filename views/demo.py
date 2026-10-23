import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core import state, ui
from core.anim import cycle_animation_html
from core.physics import DynParams, cycle, simulate_dynamics, steady_state_vs_load

ui.page_header(
    "1 · La tecnología",
    "Demo interactiva del ciclo de flotabilidad",
    "Ajuste la columna de agua, el volumen de aire por inserción y las eficiencias: la animación y las lecturas se "
    "recalculan con un modelo físico abierto (hidrostática + gas ideal + electromecánica).",
    [("Esquema genérico, no el diseño patentado", "amber"), ("Modelo de primeros principios", ""), ("Lazo cerrado opcional", "mint")],
)

PAGE = "demo"
with st.container(border=True):
    k1, k2, k3, k4 = st.columns(4, gap="medium")
    with k1:
        state.slider("Altura de la columna H (m)", "H", PAGE, 2.0, 40.0, 0.5)
        state.slider("Aire por inserción V₀ (L, a p₀)", "V0_L", PAGE, 2.0, 200.0, 1.0)
    with k2:
        state.slider("Frecuencia de inserción (Hz)", "f_ins", PAGE, 0.1, 4.0, 0.05)
        state.slider("Captura hidrodinámica η_cap (KEM)", "eta_cap", PAGE, 0.20, 0.98, 0.01,
                     help="Fracción del trabajo de flotación que el KEM convierte en trabajo de eje (deslizamiento, arrastre, turbulencia).")
    with k3:
        state.compression(PAGE)
        state.slider("Eficiencia del compresor η_c", "eta_comp", PAGE, 0.40, 1.00, 0.01,
                     help="Respecto del proceso ideal seleccionado (isotérmico, politrópico o adiabático).")
    with k4:
        closed = st.toggle("Ensayo en lazo cerrado", value=True, help="La salida eléctrica alimenta el ABIS; la red suple el déficit o recibe el excedente.")
        labels = st.toggle("Etiquetas didácticas", value=True)
        speed = st.slider("Velocidad de animación", 0.5, 4.0, 1.5, 0.5)
    with st.expander("Más parámetros (motor, transmisión, generador, electrónica, auxiliares)"):
        e1, e2, e3, e4, e5, e6 = st.columns(6)
        with e1:
            state.slider("Motor ABIS η_m", "eta_motor", PAGE, 0.70, 0.99, 0.01)
        with e2:
            state.slider("Transmisión η_t", "eta_gear", PAGE, 0.80, 0.995, 0.005)
        with e3:
            state.slider("Generador η_g", "eta_gen", PAGE, 0.80, 0.99, 0.01)
        with e4:
            state.slider("Electrónica η_pe", "eta_pe", PAGE, 0.85, 0.995, 0.005)
        with e5:
            state.slider("Auxiliares (W)", "P_aux_W", PAGE, 0.0, 2000.0, 10.0)
        with e6:
            st.write("")
            if st.button("Restablecer", icon=":material/restart_alt:"):
                state.reset()
                st.rerun()

p = state.params()
r = cycle(p)
anim = {
    "title": "Convertidor por flotabilidad — modelo genérico",
    "H": p.H, "V0_L": p.V0_L, "f_ins": p.f_ins, "ratio": r.ratio, "p0": r.p0, "eta_cap": p.eta_cap,
    "P_in": r.P_in, "P_abis": r.P_abis, "P_aux": r.P_aux, "P_out": r.P_out, "P_net": r.P_net, "ERR": r.ERR,
    "W_b": r.W_buoy, "rpm_gen": 1150.0, "speed": speed, "closed_loop": closed, "labels": labels,
    "dT": p.T_w_C - p.T_a_C,
}
st.html(cycle_animation_html(anim), unsafe_allow_javascript=True)

ui.kpis([
    {"label": "Entrada eléctrica (ABIS + aux)", "value": ui.fmt_power(r.P_in), "sub": f"{r.E_ins:,.0f} J por inserción".replace(",", " "), "accent": ui.BRAND["amber"]},
    {"label": "Trabajo de flotación disponible", "value": ui.fmt_power(r.P_buoy), "sub": f"{r.W_buoy:,.0f} J por inserción".replace(",", " "), "accent": ui.BRAND["blue"]},
    {"label": "Salida eléctrica útil", "value": ui.fmt_power(r.P_out), "sub": f"cadena η = {r.W_out / max(r.W_buoy,1e-9):.2f} desde flotación", "accent": ui.BRAND["teal"]},
    {"label": "Balance neto", "value": ui.fmt_power(r.P_net), "sub": "salida − entrada total", "accent": ui.BRAND["green"] if r.P_net >= 0 else ui.BRAND["red"]},
    {"label": "ERR (frontera completa)", "value": f"{r.ERR:.3f}", "sub": f"cota del ciclo ideal: {r.ERR_ideal_cycle:.3f}", "accent": ui.BRAND["navy"]},
])

tab1, tab2, tab3 = st.tabs(["🧭 Paso a paso", "⚙️ Dinámica electromecánica", "🧩 Arquitectura y variables medidas"])

with tab1:
    c1, c2 = st.columns([1.2, 1], gap="large")
    with c1:
        ui.steps([
            ("ABIS: inserción a profundidad",
             f"Se introducen {p.V0_L:.0f} L de aire (medidos a p₀) en la base, donde la presión es "
             f"{r.pH/1000:.1f} kPa (p_H/p₀ = {r.ratio:.3f}). El trabajo mínimo reversible es p₀V₀·ln(p_H/p₀) = {r.W_iso_ref:,.0f} J; "
             f"el compresor real consume {r.E_ins:,.0f} J eléctricos (descarga a {r.T_out_comp-273.15:.0f} °C).".replace(",", " ")),
            ("Ascenso y expansión (Boyle)",
             f"El volumen crece de {r.VH*1000:.1f} L en el fondo a ~{p.V0_L*(p.T_w_C+273.15)/(p.T_a_C+273.15):.1f} L en superficie. "
             f"La fuerza de flotación ρ·g·V(z) integrada en la altura da W = ∫V dp = {r.W_buoy:,.0f} J.".replace(",", " ")),
            ("KEM: captura del trabajo",
             f"Los cangilones atrapan el aire y transmiten par a la rueda motriz. Con η_cap = {p.eta_cap:.2f} se recuperan "
             f"{r.W_mech:,.0f} J; el resto se disipa por deslizamiento, arrastre y turbulencia.".replace(",", " ")),
            ("PDU: conversión eléctrica",
             f"Transmisión, generador y electrónica (η = {p.eta_gear*p.eta_gen*p.eta_pe:.3f}) entregan {r.W_out:,.0f} J útiles por inserción.".replace(",", " ")),
            ("CMS: balance en la frontera",
             f"A {p.f_ins:.2f} Hz: entrada {ui.fmt_power(r.P_in)} vs salida {ui.fmt_power(r.P_out)} → ERR = {r.ERR:.3f}. "
             "En lazo cerrado, la salida recircula al ABIS y la red suple el déficit (o recibe el excedente)."),
        ])
    with c2:
        ui.callout("science", "Idea física clave",
                   "El ascenso de un cuerpo de aire es termodinámicamente equivalente a una <b>expansión</b> entre p_H y p₀, "
                   "y la inserción a una <b>compresión</b> entre p₀ y p_H. Por eso, sin un aporte de energía adicional "
                   "(p. ej., calor a mayor temperatura), el trabajo recuperable no puede superar al invertido: "
                   "<b>ERR ≤ 1</b> en el límite reversible. Ver «Física y balance energético».")
        ui.callout("warning", "Qué debe aclarar el MVP",
                   "Si los ensayos de la empresa muestran ERR &gt; 1, el protocolo del MVP debe identificar y medir el flujo "
                   "energético responsable (térmico, hidráulico externo, almacenamiento) en una frontera completa. "
                   "Esa identificación es, en sí misma, el resultado científico más valioso del programa.")

with tab2:
    st.markdown("Simulación en el dominio del tiempo del arranque y régimen de un sistema cadena–cangilones–generador. "
                "Ecuación de movimiento referida al eje principal:")
    st.latex(r"J_{eq}\,\frac{d\omega}{dt}=T_{flot}(t)-T_{arr}(\omega)-T_{fric}(\omega)-T_e(\omega),\qquad J_{eq}=J_m+G^2\,(J_g+J_{vol})")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        R_load = st.slider("Carga equivalente R (Ω)", 2.0, 150.0, 25.0, 1.0)
        preload = st.toggle("Cangilones precargados al inicio", value=True,
                            help="Representa energía almacenada inicial (sesgo típico de ensayos cortos).")
    with c2:
        J_fly = st.slider("Volante de inercia (kg·m², eje rápido)", 0.0, 1.0, 0.0, 0.05)
        T_sim = st.slider("Duración simulada (s)", 10, 90, 40, 5)
    with c3:
        s_b = st.slider("Paso entre cangilones (m)", 0.2, 1.5, 0.5, 0.05)
        G = st.slider("Relación de multiplicación G", 10, 150, 60, 5)
    with c4:
        eta_cap_dyn = st.slider("Captura de aire en cangilones", 0.3, 1.0, 0.85, 0.01)
        Cd = st.slider("Coef. de arrastre Cd", 0.3, 2.0, 1.2, 0.05)

    dp = DynParams(H=p.H, V0_L=p.V0_L, s_bucket=s_b, Vb_L=1.1 * p.V0_L, eta_cap=eta_cap_dyn, Cd=Cd, J_fly=J_fly,
                   G_ratio=float(G), R_load=R_load, eta_pe=p.eta_pe, eta_gear=p.eta_gear, E_ins_J=r.E_ins,
                   P_aux_W=p.P_aux_W, T_w_C=p.T_w_C, altitude_m=p.altitude_m, preload=preload, T_sim=float(T_sim))

    @st.cache_data(show_spinner="Simulando dinámica…")
    def _sim(d: dict):
        return simulate_dynamics(DynParams(**d))

    @st.cache_data(show_spinner=False)
    def _ss(d: dict):
        return steady_state_vs_load(DynParams(**d), np.linspace(2, 150, 75))

    out = _sim(dp.as_dict())
    s, m = out["series"], out["metrics"]
    ss = _ss(dp.as_dict())

    ui.kpis([
        {"label": "Velocidad en régimen", "value": f"{m.get('omega_ss', 0)*60/(2*np.pi):.1f} rpm", "sub": f"cadena {m.get('u_ss',0):.2f} m/s · generador {m.get('rpm_gen_ss',0):.0f} rpm", "accent": ui.BRAND["blue"]},
        {"label": "Inserciones en régimen", "value": f"{m.get('f_ins_ss',0):.2f} Hz", "sub": f"{m.get('n_buckets',0)} cangilones en el lazo", "accent": ui.BRAND["amber"]},
        {"label": "Potencia útil (régimen)", "value": ui.fmt_power(m.get("P_out_ss", 0)), "sub": f"entrada {ui.fmt_power(m.get('P_in_ss', 0))}", "accent": ui.BRAND["teal"]},
        {"label": "ERR en régimen", "value": f"{m.get('ERR_ss', float('nan')):.3f}", "sub": "últimos 35 % de la simulación", "accent": ui.BRAND["navy"]},
        {"label": "Rizado de potencia", "value": f"{100*m.get('ripple_power',0):.1f} %", "sub": f"velocidad {100*m.get('ripple_speed',0):.2f} % · J_eq {m.get('J_eq',0):.0f} kg·m²", "accent": ui.BRAND["violet"]},
    ])

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.07,
                        subplot_titles=("Velocidad del eje principal", "Potencias: pulsos del ABIS vs salida eléctrica",
                                        "ERR acumulado = E_salida(t) / E_entrada(t)"))
    fig.add_trace(go.Scatter(x=s["t"], y=s["omega"] * 60 / (2 * np.pi), name="rpm eje principal", line=dict(color=ui.BRAND["blue"])), 1, 1)
    fig.add_trace(go.Scatter(x=s["t"], y=s["P_abis"], name="P ABIS (pulsos)", line=dict(color=ui.BRAND["amber"], width=1)), 2, 1)
    fig.add_trace(go.Scatter(x=s["t"], y=s["P_out"], name="P salida útil", line=dict(color=ui.BRAND["teal"], width=2)), 2, 1)
    fig.add_trace(go.Scatter(x=s["t"], y=s["ERR_cum"], name="ERR acumulado", line=dict(color=ui.BRAND["navy"], width=2)), 3, 1)
    fig.add_hline(y=1.0, line=dict(color=ui.BRAND["red"], dash="dash"), row=3, col=1)
    if preload:
        early = s["t"] <= min(6.0, float(T_sim) / 3)
        if early.any():
            k = int(np.nanargmax(np.where(early, s["ERR_cum"], np.nan)))
            y_pk = float(min(s["ERR_cum"][k], 3.8))
            fig.add_annotation(x=float(s["t"][k]), y=y_pk, row=3, col=1, ax=110, ay=10, showarrow=True, arrowcolor=ui.BRAND["red"],
                               text="sesgo por energía almacenada inicial", font=dict(size=11, color=ui.BRAND["red"]), xanchor="left")
    fig.update_yaxes(title_text="rpm", row=1, col=1)
    fig.update_yaxes(title_text="W", row=2, col=1)
    fig.update_yaxes(title_text="ERR", row=3, col=1, range=[0, max(1.6, float(np.nanmin([np.nanmax(s["ERR_cum"]), 4.0])) * 1.05)])
    fig.update_xaxes(title_text="tiempo (s)", row=3, col=1)
    fig.update_xaxes(range=[0, float(T_sim)])
    ui.style_fig(fig, height=720)
    ui.show(fig, key="dyn")

    c1, c2 = st.columns([1.3, 1], gap="large")
    with c1:
        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig2.add_trace(go.Scatter(x=ss["R"], y=ss["P_out"], name="P salida (W)", line=dict(color=ui.BRAND["teal"], width=3)), secondary_y=False)
        fig2.add_trace(go.Scatter(x=ss["R"], y=ss["ERR"], name="ERR", line=dict(color=ui.BRAND["navy"], width=2, dash="dot")), secondary_y=True)
        fig2.add_vline(x=R_load, line=dict(color=ui.BRAND["amber"], dash="dash"))
        fig2.update_yaxes(title_text="W", secondary_y=False)
        fig2.update_yaxes(title_text="ERR", secondary_y=True, tickformat=".2f", showgrid=False)
        ui.style_fig(fig2, height=360, title="Punto de operación: potencia vs eficiencia según la carga (CMS)", xaxis_title="R de carga (Ω)")
        ui.show(fig2, key="ss")
    with c2:
        ui.callout("science", "Lectura para ingeniería eléctrica",
                   "<ul style='margin:0;padding-left:18px'>"
                   "<li>El par de flotación es casi constante; la carga eléctrica fija la velocidad y, con ella, la tasa de "
                   "inserción y el consumo del ABIS. Existe un compromiso <b>potencia–eficiencia</b>: el arrastre crece con ω² "
                   "y la fricción de Coulomb pesa a baja velocidad.</li>"
                   "<li>El rizado a la frecuencia de inserción exige inercia (volante), control del convertidor y filtrado "
                   "para entregar potencia de calidad (IEEE 519 / códigos de red).</li>"
                   "<li>Los cangilones precargados inflan el ERR de los primeros segundos: un ensayo corto puede sugerir "
                   "ERR &gt; 1 sin que exista excedente en régimen.</li></ul>")

with tab3:
    ui.cards([
        {"num": "ABIS", "title": "Air Body Insertion System",
         "body": "<ul><li>Compresor/inserción, válvulas, depósito pulmón.</li><li><b>Medir:</b> P activa (clase 0,2S), p y T de descarga, caudal FAD, energía por inserción.</li><li><b>Riesgo:</b> energía almacenada en el depósito; fugas.</li></ul>"},
        {"num": "KEM", "title": "Mechanical Generation System",
         "body": "<ul><li>Cadena/cangilones o equivalente, rueda motriz, caja multiplicadora.</li><li><b>Medir:</b> par y velocidad (torquímetro), fracción de aire capturado, pérdidas.</li><li><b>Riesgo:</b> fatiga, corrosión, sincronización con el ABIS.</li></ul>"},
        {"num": "PDU", "title": "Power Delivery Unit",
         "body": "<ul><li>Generador (p. ej., PMSG de baja velocidad), rectificador, bus DC, inversor.</li><li><b>Medir:</b> P, Q, THD, f, V (IEC 61000-4-30 clase A), eficiencia (IEC 60034-2-1).</li><li><b>Riesgo:</b> calidad de potencia, protecciones, conexión a red.</li></ul>"},
        {"num": "CMS", "title": "Control & Management System",
         "body": "<ul><li>PLC/SCADA, sincronización inserción–cangilón, control de par/velocidad (MPPT-like).</li><li><b>Medir:</b> marcas de tiempo sincronizadas, consumo propio, registro auditable.</li><li><b>Riesgo:</b> ciberseguridad, integridad de datos.</li></ul>"},
    ], min_width=230)

ui.footer()
