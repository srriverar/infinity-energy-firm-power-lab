import base64
import json
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core import ui
from core.data import source_line
from core.metrology import (CTS, METERS, TEMPLATE_COLUMNS, VTS, analyze_timeseries, channel_uncertainty, decision,
                            n_effective, ratio_uncertainty, report_markdown, required_windows, simulate_campaign,
                            synthetic_test_dataset, template_csv)

ui.page_header(
    "4 · Validación",
    "Protocolo MVP: medir el balance energético sin ambigüedad",
    "Frontera completa, instrumentación trazable, presupuesto de incertidumbre (GUM), regla de decisión explícita y "
    "verificación independiente. Herramientas para diseñar el ensayo y analizar datos reales.",
    [("JCGM 100:2008 (GUM)", ""), ("IEC 62053-22 / 61869", ""), ("IEC 61000-4-30 clase A", ""), ("ISO/IEC 17025", "mint")],
)

tabs = st.tabs(["🧭 Frontera", "📏 Incertidumbre (GUM)", "🧪 Campañas", "⚠️ Errores típicos", "📂 Datos (CSV)", "🔁 Autosostenimiento"])

# ----------------------------------------------------------------------------- Frontera
with tabs[0]:
    svg = """
<svg viewBox="0 0 1000 430" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;font-family:Inter,Segoe UI,Arial">
 <defs><marker id="ar" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#0B2A5B"/></marker>
 <marker id="ao" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#F59E0B"/></marker>
 <marker id="ag" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#0FA99A"/></marker>
 <marker id="ap" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#7C3AED"/></marker>
 <marker id="ar2" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#E5484D"/></marker></defs>
 <rect x="230" y="40" width="520" height="350" rx="18" fill="#F7FBFE" stroke="#0098D4" stroke-width="3" stroke-dasharray="10 7"/>
 <text x="490" y="30" text-anchor="middle" font-size="15" font-weight="800" fill="#0098D4">FRONTERA DE BALANCE (volumen de control)</text>
 <rect x="260" y="80" width="120" height="270" rx="10" fill="#5DB8EC" opacity=".55"/><text x="320" y="215" text-anchor="middle" font-size="13" font-weight="700" fill="#0B2A5B">Columna</text><text x="320" y="233" text-anchor="middle" font-size="13" font-weight="700" fill="#0B2A5B">de agua</text>
 <rect x="410" y="80" width="130" height="58" rx="10" fill="#fff" stroke="#64748B"/><text x="475" y="114" text-anchor="middle" font-size="14" font-weight="800" fill="#0B2A5B">KEM</text>
 <rect x="570" y="80" width="150" height="58" rx="10" fill="#ECFDF5" stroke="#0FA99A"/><text x="645" y="107" text-anchor="middle" font-size="14" font-weight="800" fill="#0B2A5B">PDU</text><text x="645" y="125" text-anchor="middle" font-size="11" fill="#5B6B80">generador + conversión</text>
 <rect x="410" y="292" width="130" height="58" rx="10" fill="#FFF7ED" stroke="#F59E0B"/><text x="475" y="326" text-anchor="middle" font-size="14" font-weight="800" fill="#0B2A5B">ABIS</text>
 <rect x="570" y="292" width="150" height="58" rx="10" fill="#EEF2FF" stroke="#7C3AED"/><text x="645" y="319" text-anchor="middle" font-size="14" font-weight="800" fill="#0B2A5B">CMS + aux.</text><text x="645" y="336" text-anchor="middle" font-size="11" fill="#5B6B80">bombas · sensores</text>
 <rect x="410" y="170" width="310" height="95" rx="10" fill="#FFFFFF" stroke="#E5484D" stroke-dasharray="5 4"/>
 <text x="565" y="192" text-anchor="middle" font-size="13" font-weight="800" fill="#E5484D">ALMACENAMIENTOS INTERNOS (ΔE)</text>
 <text x="565" y="214" text-anchor="middle" font-size="12" fill="#334155">depósitos de aire (p, V) · volantes (ω, J)</text>
 <text x="565" y="233" text-anchor="middle" font-size="12" fill="#334155">baterías/supercaps (SoC) · nivel de agua (h)</text>
 <text x="565" y="252" text-anchor="middle" font-size="12" fill="#334155">energía térmica del agua (T)</text>
 <line x1="60" y1="321" x2="405" y2="321" stroke="#F59E0B" stroke-width="4" marker-end="url(#ao)"/><text x="70" y="310" font-size="13" font-weight="800" fill="#F59E0B">E_ABIS (M1)</text>
 <line x1="60" y1="360" x2="565" y2="360" stroke="#7C3AED" stroke-width="3" marker-end="url(#ap)"/><text x="70" y="378" font-size="13" font-weight="800" fill="#7C3AED">E_aux (M3)</text>
 <line x1="725" y1="109" x2="950" y2="109" stroke="#0FA99A" stroke-width="4" marker-end="url(#ag)"/><text x="800" y="98" font-size="13" font-weight="800" fill="#0FA99A">E_salida útil (M2)</text>
 <line x1="60" y1="150" x2="255" y2="150" stroke="#E5484D" stroke-width="3" stroke-dasharray="6 5" marker-end="url(#ar2)"/><text x="70" y="140" font-size="12.5" font-weight="700" fill="#E5484D">Q ambiente (T, flujo)</text>
 <line x1="60" y1="225" x2="255" y2="225" stroke="#0B2A5B" stroke-width="3" stroke-dasharray="6 5" marker-end="url(#ar)"/><text x="70" y="215" font-size="12.5" font-weight="700" fill="#0B2A5B">Agua de reposición</text>
 <line x1="755" y1="300" x2="950" y2="300" stroke="#94A3B8" stroke-width="3" marker-end="url(#ar)"/><text x="770" y="290" font-size="12.5" font-weight="700" fill="#64748B">Pérdidas térmicas</text>
 <text x="490" y="418" text-anchor="middle" font-size="13" font-weight="700" fill="#0B2A5B">E_ABIS + E_aux + Q_neto + E_hid = E_salida + ΔE_alm + pérdidas   ⇒   ERR = E_salida / (E_ABIS + E_aux − ΔE_alm)</text>
</svg>"""
    b64 = base64.b64encode(svg.strip().encode("utf-8")).decode()
    st.markdown(f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%;max-width:1100px;display:block;margin:0 auto 8px auto" '
                'alt="Frontera de balance energético">', unsafe_allow_html=True)
    checklist = pd.DataFrame([
        ["Potencia/energía activa ABIS, auxiliares y salida", "Analizador de potencia o medidor 0,2S con TC/TT de clase adecuada", "IEC 62053-22 · IEC 61869-2/-3", "≥ 1 s (energía) · forma de onda ≥ 10 kHz"],
        ["Calidad de potencia (V, f, THD, flicker)", "Analizador clase A", "IEC 61000-4-30 · IEEE 519", "agregados 10 ciclos / 10 min"],
        ["Par y velocidad del eje", "Torquímetro + encoder", "IEC 60034-2-1 (eficiencia de máquinas)", "≥ 100 Hz"],
        ["Presión, temperatura y caudal de aire (FAD)", "Transductores calibrados + caudalímetro", "ISO 1217 (compresores)", "≥ 10 Hz"],
        ["Energía almacenada interna", "p de depósitos, ω de volantes, SoC, nivel de agua", "Balance de exergía", "inicio/fin + continuo"],
        ["Temperaturas agua/aire/ambiente y flujo de calor", "RTD Pt100 clase A, termopares calibrados", "Trazabilidad SI", "≥ 1/min"],
        ["Tiempo y sincronización", "GPS/PTP, registro con sello de tiempo", "IEEE 1588", "—"],
        ["Integridad de datos", "Registro firmado/hash, acceso del tercero", "ISO/IEC 17025 · ISO 50015 (M&V)", "—"],
    ], columns=["Magnitud", "Instrumento", "Referencia normativa", "Muestreo"])
    st.table(checklist.set_index("Magnitud"))
    ui.callout("science", "Tres principios (alineados con la hoja de ruta de la empresa): Completo · Repetible · Independiente",
               "<b>Completo:</b> toda entrada y todo almacenamiento dentro de la frontera. <b>Repetible:</b> múltiples MVP, "
               "múltiples campañas, criterio de aceptación fijado <i>antes</i> de medir. <b>Independiente:</b> laboratorio "
               "acreditado o tercero con acceso a instrumentos, datos crudos y configuración.")

# ----------------------------------------------------------------------------- GUM
with tabs[1]:
    st.markdown("Seleccione la instrumentación de cada canal. Las especificaciones se tratan como límites con distribución "
                "rectangular (u = a/√3).")
    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        st.markdown("**Canal de entrada (ABIS + aux)**")
        m_in = st.selectbox("Medidor", list(METERS), index=2, key="m_in")
        ct_in = st.selectbox("TC", list(CTS), index=2, key="ct_in")
        vt_in = st.selectbox("TT", list(VTS), index=0, key="vt_in")
        pf_in = st.slider("Factor de potencia típico", 0.5, 1.0, 0.82, 0.01, key="pf_in")
        ex_in = st.slider("Armónicos / ancho de banda / otros (± %)", 0.0, 5.0, 0.5, 0.1, key="ex_in",
                          help="Compresores con variador (PWM) exigen medidores de ancho de banda suficiente.")
    with c2:
        st.markdown("**Canal de salida (PDU)**")
        m_out = st.selectbox("Medidor", list(METERS), index=2, key="m_out")
        ct_out = st.selectbox("TC", list(CTS), index=2, key="ct_out")
        vt_out = st.selectbox("TT", list(VTS), index=0, key="vt_out")
        pf_out = st.slider("Factor de potencia típico", 0.5, 1.0, 0.98, 0.01, key="pf_out")
        ex_out = st.slider("Armónicos / ancho de banda / otros (± %)", 0.0, 5.0, 0.2, 0.1, key="ex_out")
    with c3:
        st.markdown("**Repetibilidad y decisión**")
        corr = st.slider("Correlación entre canales r", -0.5, 1.0, 0.0, 0.05,
                         help="Mismo analizador y rango en ambos canales ⇒ errores de ganancia correlacionados (r > 0) que se cancelan parcialmente en el cociente.")
        sig_w = st.slider("Variabilidad entre ventanas σ (%)", 0.5, 15.0, 4.0, 0.5)
        n_w = st.slider("Número de ventanas independientes", 3, 500, 48, 1)
        err_meas = st.slider("ERR medido (valor hipotético para probar la regla)", 0.30, 1.50, 1.01, 0.005)
    ui_in = channel_uncertainty(m_in, ct_in, vt_in, pf_in, ex_in)
    ui_out = channel_uncertainty(m_out, ct_out, vt_out, pf_out, ex_out)
    uB_rel = ratio_uncertainty(ui_out["u_pct"], ui_in["u_pct"], corr)
    uA_rel = sig_w / math.sqrt(n_w)
    uc_rel = math.sqrt(uA_rel ** 2 + uB_rel ** 2)
    dec = decision(err_meas, err_meas * uc_rel / 100)
    ui.kpis([
        {"label": "u entrada (tipo B)", "value": f"{ui_in['u_pct']:.3f} %", "accent": ui.BRAND["amber"]},
        {"label": "u salida (tipo B)", "value": f"{ui_out['u_pct']:.3f} %", "accent": ui.BRAND["teal"]},
        {"label": "u(ERR) tipo A / tipo B", "value": f"{uA_rel:.2f} % / {uB_rel:.2f} %", "accent": ui.BRAND["blue"]},
        {"label": "U expandida (k = 2)", "value": f"± {2*uc_rel:.2f} %", "sub": f"± {dec['U']:.4f} en ERR", "accent": ui.BRAND["navy"]},
        {"label": "P(ERR > 1 | datos)", "value": f"{dec['P(ERR>1)']:.3f}", "sub": f"IC95: [{dec['lower']:.3f}; {dec['upper']:.3f}]", "accent": ui.BRAND["violet"]},
    ])
    getattr(st, {"success": "success", "warning": "warning", "info": "info"}[dec["level"]])(ui.es_num(f"**Dictamen para el ERR hipotético de {err_meas:.3f}:** {dec['verdict']}"))
    c1, c2 = st.columns(2, gap="large")
    with c1:
        comps = {f"Entrada · {k}": v for k, v in ui_in["components"].items()}
        comps.update({f"Salida · {k}": v for k, v in ui_out["components"].items()})
        comps["Repetibilidad (tipo A)"] = uA_rel
        comps = dict(sorted(((k, v) for k, v in comps.items() if v > 1e-6), key=lambda kv: -kv[1]))
        fig = go.Figure(go.Bar(x=list(comps.values()), y=list(comps.keys()), orientation="h", marker_color=ui.BRAND["blue"]))
        fig.update_yaxes(autorange="reversed")
        ui.style_fig(fig, height=380, title="Contribuciones a la incertidumbre (u estándar, %)", xaxis_title="%")
        ui.show(fig, key="pareto")
    with c2:
        deltas = np.linspace(0.005, 0.10, 40)
        nreq = [required_windows(d, sig_w / 100, uB_rel / 100) for d in deltas]
        fig = go.Figure(go.Scatter(x=100 * deltas, y=[n if np.isfinite(n) else None for n in nreq], mode="lines",
                                   line=dict(color=ui.BRAND["navy"], width=3)))
        fig.update_yaxes(type="log")
        ui.style_fig(fig, height=380, title="Ventanas necesarias para detectar ERR = 1 + δ (α = 5 %, potencia 80 %)",
                     xaxis_title="δ (%)", yaxis_title="ventanas (log)")
        ui.show(fig, key="nreq")
        d_min = (1.645 + 0.842) * uB_rel
        st.caption(ui.es_num(f"Con esta instrumentación, ningún número de repeticiones permite detectar δ < {d_min:.2f} %: la "
                   "incertidumbre sistemática (tipo B) fija un piso. Mejorar la clase de los instrumentos es la única vía."))
    ui.source(source_line("S12"))

# ----------------------------------------------------------------------------- Campaña
with tabs[2]:
    c1, c2 = st.columns([1, 2.3], gap="large")
    with c1:
        true_err = st.slider("ERR verdadero (supuesto del simulador)", 0.3, 1.3, 0.90, 0.01,
                             help="Solo para dimensionar el ensayo; no es una predicción del desempeño.")
        Pin = st.number_input("Potencia de entrada media (W)", 100.0, 1e6, 2000.0, 100.0)
        hours = st.slider("Duración del ensayo (h)", 1.0, 168.0, 8.0, 1.0)
        win = st.select_slider("Ventana de análisis (min)", [1, 5, 10, 15, 30, 60], value=10)
        sw = st.slider("Variabilidad de proceso entre ventanas (%)", 0.5, 15.0, 4.0, 0.5, key="camp_sw")
        Es = st.slider("Energía almacenada al inicio (kWh)", 0.0, 5.0, 0.30, 0.05)
        tau = st.slider("Constante de descarga del almacenamiento (min)", 1.0, 240.0, 15.0, 1.0)
        meas_st = st.toggle("Se mide y se descuenta el almacenamiento", value=False)
        seed = st.number_input("Semilla aleatoria", 0, 9999, 3, 1)
    camp = simulate_campaign(true_err, Pin, hours, float(win), sw, ui_in["u_pct"], ui_out["u_pct"], corr, Es, tau, meas_st, int(seed))
    with c2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=camp["t_min"] / 60, y=camp["IC95_sup"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=camp["t_min"] / 60, y=camp["IC95_inf"], fill="tonexty", fillcolor="rgba(0,152,212,0.15)", line=dict(width=0), name="IC 95 % (A+B)"))
        fig.add_trace(go.Scatter(x=camp["t_min"] / 60, y=camp["ERR_ventana"], mode="markers", marker=dict(size=4, color="#94A3B8"), name="ERR por ventana"))
        fig.add_trace(go.Scatter(x=camp["t_min"] / 60, y=camp["ERR_acum_bruto"],
                                 name="ERR acumulado (sin medir almacenamiento)", line=dict(color=ui.BRAND["red"], width=2.5)))
        if meas_st:
            fig.add_trace(go.Scatter(x=camp["t_min"] / 60, y=camp["ERR_acum_corr"], name="ERR acumulado (ΔE medido · frontera completa)",
                                     line=dict(color=ui.BRAND["navy"], width=3)))
        fig.add_hline(y=1, line=dict(color="#0B2A5B", dash="dot"))
        fig.add_hline(y=true_err, line=dict(color=ui.BRAND["teal"], dash="dash"), annotation_text="ERR verdadero")
        ui.style_fig(fig, height=460, title="Convergencia del ERR durante la campaña", xaxis_title="horas", yaxis_title="ERR")
        ui.show(fig, key="camp")
    last = camp.iloc[-1]
    first_h = camp[camp["t_min"] <= 60]
    ui.kpis([
        {"label": "ERR primera hora (bruto)", "value": f"{first_h['E_out_kWh'].sum()/first_h['E_in_kWh'].sum():.3f}", "accent": ui.BRAND["red"]},
        {"label": "ERR final (bruto)", "value": f"{last['ERR_acum_bruto']:.3f}", "accent": ui.BRAND["amber"]},
        {"label": "ERR final (corregido)", "value": f"{last['ERR_acum_corr']:.3f}", "accent": ui.BRAND["navy"]},
        {"label": "IC 95 % final", "value": f"[{last['IC95_inf']:.3f}; {last['IC95_sup']:.3f}]", "accent": ui.BRAND["blue"]},
        {"label": "n efectivo de ventanas", "value": f"{n_effective(camp['ERR_ventana'].to_numpy()):.0f}", "sub": f"de {len(camp)}", "accent": ui.BRAND["gray"]},
    ])
    ui.callout("warning", "Lección de diseño",
               "Si un almacenamiento interno (depósito precargado, volante, batería) libera energía al inicio y no se mide, el "
               "ERR de las primeras horas aparece inflado. Exigir: (1) estado inicial = estado final, o medición de ΔE; (2) "
               "duración ≫ energía almacenable / potencia neta; (3) regla de decisión fijada antes del ensayo.")

# ----------------------------------------------------------------------------- Errores típicos
with tabs[3]:
    c1, c2 = st.columns([1, 2], gap="large")
    with c1:
        base_err = st.slider("ERR verdadero", 0.2, 1.2, 0.60, 0.01, key="pit_base")
        pf_load = st.slider("FP de la carga de salida (si se mide S = V·I en vez de P)", 0.6, 1.0, 0.85, 0.01)
        use_pf = st.checkbox("Salida medida como potencia aparente (V·I)", True)
        rms_err = st.slider("Sub-registro de un medidor no-RMS verdadero en la entrada (%)", 0.0, 40.0, 15.0, 1.0)
        use_rms = st.checkbox("Entrada con medidor no-RMS / ancho de banda insuficiente", True)
        aux_sh = st.slider("Auxiliares sobre el consumo del ABIS (%)", 0.0, 30.0, 8.0, 0.5)
        use_aux = st.checkbox("Auxiliares fuera de la frontera", True)
        st_sh = st.slider("Energía almacenada liberada / salida verdadera en el ensayo (%)", 0.0, 100.0, 30.0, 1.0)
        use_st = st.checkbox("Ensayo corto con almacenamiento no medido", True)
        peak = st.slider("Relación pico/medio de la salida (ventana favorable)", 1.0, 1.6, 1.15, 0.01)
        use_pk = st.checkbox("Ventana de salida no sincronizada (pico)", False)
    steps = [("ERR verdadero", base_err)]
    f = 1.0
    if use_pf:
        steps.append(("Salida como V·I (÷FP)", 1 / pf_load))
    if use_rms:
        steps.append(("Entrada sub-registrada (no-RMS)", 1 / (1 - rms_err / 100)))
    if use_aux:
        steps.append(("Auxiliares omitidos", 1 + aux_sh / 100))
    if use_st:
        steps.append(("Almacenamiento no medido", 1 + st_sh / 100))
    if use_pk:
        steps.append(("Ventana de pico", peak))
    vals = [base_err]
    for _, fac in steps[1:]:
        vals.append(vals[-1] * fac)
    with c2:
        measures = ["absolute"] + ["relative"] * (len(steps) - 1) + ["total"]
        y = [base_err] + [vals[i] - vals[i - 1] for i in range(1, len(vals))] + [vals[-1]]
        x = [s[0] for s in steps] + ["ERR aparente"]
        fig = go.Figure(go.Waterfall(x=x, y=y, measure=measures, connector=dict(line=dict(color="#CBD5E1")),
                                     increasing=dict(marker=dict(color=ui.BRAND["red"])), totals=dict(marker=dict(color=ui.BRAND["navy"])),
                                     decreasing=dict(marker=dict(color=ui.BRAND["teal"])), text=[ui.es_num(f"{v:+.3f}" if i not in (0, len(y) - 1) else f"{v:.3f}") for i, v in enumerate(y)],
                                     textposition="outside"))
        fig.add_hline(y=1, line=dict(color="#0B2A5B", dash="dot"), annotation_text="ERR = 1")
        ui.style_fig(fig, height=430, title="Cómo errores comunes pueden inflar el ERR aparente", yaxis_title="ERR")
        ui.show(fig, key="wf")
    tbl = pd.DataFrame([
        ["Potencia aparente vs activa", "S = V·I sobreestima P si FP < 1", "Medir P activa (W) con analizador; registrar FP"],
        ["Medidores no-RMS / poco ancho de banda", "Sub-registro con corrientes distorsionadas (variadores, rectificadores)", "Analizador de potencia con ancho de banda ≥ 100 kHz; verificación cruzada"],
        ["Auxiliares fuera de frontera", "CMS, bombas, enfriamiento no contabilizados", "Medir todos los consumos dentro de la frontera"],
        ["Almacenamiento no medido", "Depósitos, volantes, baterías aportan energía no registrada", "Medir ΔE inicio/fin; ensayos largos; estado cíclico"],
        ["Ventanas no sincronizadas", "Comparar picos de salida con medias de entrada", "Sincronización GPS/PTP; ventanas idénticas"],
        ["Sesgo de selección", "Reportar sólo las mejores corridas", "Plan de ensayo y criterio de aceptación pre-registrados"],
    ], columns=["Error", "Mecanismo", "Control en el protocolo"])
    st.table(tbl.set_index("Error"))

# ----------------------------------------------------------------------------- CSV
with tabs[4]:
    c1, c2 = st.columns([1, 1.4], gap="large")
    with c1:
        up = st.file_uploader("Archivo CSV del ensayo", type=["csv"])
        use_example = st.toggle("Usar datos sintéticos didácticos de ejemplo", value=up is None)
        st.download_button("Descargar plantilla CSV", template_csv().encode(), "plantilla_ensayo_mvp.csv", "text/csv")
        with st.expander("Columnas reconocidas"):
            st.table(pd.DataFrame({"columna": list(TEMPLATE_COLUMNS), "descripción": list(TEMPLATE_COLUMNS.values())}))
    with c2:
        tank = st.number_input("Volumen del depósito de aire (L) — para ΔE", 0.0, 100000.0, 500.0, 10.0)
        Jf = st.number_input("Inercia del volante/rotor (kg·m²) — para ΔE", 0.0, 10000.0, 0.0, 0.1)
        bWh = st.number_input("Capacidad de baterías internas (Wh) — para ΔE", 0.0, 1e7, 0.0, 10.0)
        wmin = st.select_slider("Ventana de análisis (min)", [1, 2, 5, 10, 15, 30, 60], value=10, key="csv_win")
        st.markdown("Instrumentación: se usa el presupuesto de la pestaña «Presupuesto de incertidumbre».")
    data, fname = None, None
    if up is not None and not use_example:
        try:
            data = pd.read_csv(up)
            fname = up.name
        except Exception as e:  # noqa: BLE001
            st.error(f"No se pudo leer el CSV: {e}")
    elif use_example:
        data = synthetic_test_dataset()
        fname = "ejemplo_sintetico_didactico.csv"
        st.info("Datos **sintéticos didácticos** (no son mediciones de Infinity Energy): ensayo de 2 h con un depósito de aire "
                "precargado que se descarga al inicio.")
    if data is not None:
        try:
            res = analyze_timeseries(data, tank_L=tank, J_fly=Jf, batt_Wh=bWh, window_min=float(wmin))
        except Exception as e:  # noqa: BLE001
            st.error(str(e))
            res = None
        if res is not None:
            win_df = res["windows"]
            errs = win_df["ERR_corr"].dropna().to_numpy()
            neff = n_effective(errs) if len(errs) > 2 else float(len(errs))
            uA = float(np.std(errs, ddof=1) / math.sqrt(max(neff, 1))) if len(errs) > 2 else float("nan")
            uB = res["ERR_corr"] * uB_rel / 100
            uc = math.sqrt((uA if np.isfinite(uA) else 0) ** 2 + uB ** 2)
            dd = decision(res["ERR_corr"], uc)
            ui.kpis([
                {"label": "Duración", "value": f"{res['duration_h']:.2f} h", "accent": ui.BRAND["gray"]},
                {"label": "E entrada (ABIS + aux)", "value": f"{res['E_in_kWh']:.3f} kWh", "accent": ui.BRAND["amber"]},
                {"label": "E salida útil", "value": f"{res['E_out_kWh']:.3f} kWh", "accent": ui.BRAND["teal"]},
                {"label": "ΔE almacenada (fin − inicio)", "value": f"{res['dE_stored_kWh']:+.3f} kWh", "accent": ui.BRAND["red"]},
                {"label": "ERR bruto → corregido", "value": f"{res['ERR_raw']:.3f} → {res['ERR_corr']:.3f}", "sub": f"U(k=2) = ±{dd['U']:.3f}", "accent": ui.BRAND["navy"]},
            ])
            getattr(st, dd["level"])(ui.es_num(f"**Dictamen:** {dd['verdict']} · P(ERR>1) ≈ {dd['P(ERR>1)']:.3f}"))
            t_h = res["t"] / 3600
            step = max(1, len(t_h) // 3000)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                                subplot_titles=("Potencias medidas", "ERR acumulado: bruto vs frontera completa"))
            fig.add_trace(go.Scatter(x=t_h[::step], y=res["p_abis"][::step], name="P ABIS", line=dict(color=ui.BRAND["amber"], width=1)), 1, 1)
            fig.add_trace(go.Scatter(x=t_h[::step], y=res["p_aux"][::step], name="P aux", line=dict(color=ui.BRAND["violet"], width=1)), 1, 1)
            fig.add_trace(go.Scatter(x=t_h[::step], y=res["p_out"][::step], name="P salida", line=dict(color=ui.BRAND["teal"], width=1.5)), 1, 1)
            fig.add_trace(go.Scatter(x=t_h[::step], y=res["err_cum_raw"][::step], name="ERR bruto", line=dict(color=ui.BRAND["red"], width=2)), 2, 1)
            fig.add_trace(go.Scatter(x=t_h[::step], y=res["err_cum_corr"][::step], name="ERR corregido", line=dict(color=ui.BRAND["navy"], width=3)), 2, 1)
            fig.add_hline(y=1, line=dict(color="#0B2A5B", dash="dot"), row=2, col=1)
            fig.update_yaxes(title_text="W", row=1, col=1)
            fig.update_yaxes(title_text="ERR", row=2, col=1, range=[0, max(1.5, float(np.nanmax(res["err_cum_raw"][len(t_h)//50:])) * 1.1)])
            fig.update_xaxes(title_text="horas", row=2, col=1)
            ui.style_fig(fig, height=620)
            ui.show(fig, key="csvplot")
            st.markdown("**Análisis por ventanas**")
            st.dataframe(ui.sfmt(win_df, "{:.3f}"), width="stretch", hide_index=True, height=240)
            rep = report_markdown(res, {"uA": uA, "uB": uB, "uc": uc, "n_eff": neff}, dd, {"file": fname})
            cA, cB = st.columns(2)
            with cA:
                st.download_button("Descargar informe (Markdown)", rep.encode(), "informe_balance_energetico.md", "text/markdown")
            with cB:
                st.download_button("Descargar resultados por ventana (CSV)", win_df.to_csv(index=False).encode(), "ventanas_err.csv", "text/csv")

# ----------------------------------------------------------------------------- Autosostenimiento
with tabs[5]:
    c1, c2 = st.columns([1, 1.4], gap="large")
    with c1:
        Pnet = st.number_input("Potencia neta exportada declarada (kW)", 0.01, 10000.0, 1.0, 0.1)
        Ehid = st.number_input("Energía máxima que podría ocultarse internamente (kWh)", 0.0, 100000.0, 10.0, 1.0,
                               help="Suma de baterías, depósitos de aire, volantes y otros almacenamientos posibles en el equipo.")
        k = st.slider("Factor de seguridad", 3, 50, 10)
    tmin = k * Ehid / Pnet
    with c2:
        ui.kpis([
            {"label": "Duración mínima del ensayo autónomo", "value": f"{tmin:,.0f} h".replace(",", " "), "sub": f"≈ {tmin/24:,.1f} días".replace(",", " "), "accent": ui.BRAND["navy"]},
            {"label": "Energía neta exportada en el ensayo", "value": f"{Pnet*tmin:,.0f} kWh".replace(",", " "), "sub": f"= {k}× la energía almacenable", "accent": ui.BRAND["teal"]},
        ])
        ui.callout("science", "Prueba de mayor poder de convicción",
                   "Un equipo con excedente neto real puede operar <b>desconectado de toda fuente externa</b>, alimentando su "
                   "propio ABIS y auxiliares y exportando potencia a una carga resistiva medida, durante un tiempo muy superior "
                   "al que cualquier almacenamiento interno podría sostener. Condiciones: equipo sellado e inspeccionado, sin "
                   "baterías no declaradas, testigos independientes, registro continuo y verificación del estado inicial/final.")
    ui.steps([
        ("Inspección previa", "Inventario de almacenamientos, diagramas unifilares, sellos y fotografías; estado inicial documentado."),
        ("Arranque asistido", "Se permite energía externa de arranque, medida y registrada; luego se desconecta físicamente."),
        ("Operación autónoma", f"≥ {tmin:,.0f} h con carga resistiva calibrada; registro de P, V, f, T y presiones.".replace(",", " ")),
        ("Cierre y verificación", "Estado final de todos los almacenamientos; análisis por tercero con datos crudos."),
    ])

ui.footer()
