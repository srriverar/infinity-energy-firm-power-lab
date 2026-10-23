import datetime as dt

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core import ui
from core.data import COMPANY

ui.page_header(
    "4 · Validación",
    "Hoja de ruta de 18 meses: TRL, gates cuantitativos y riesgos",
    "Propuesta de programa por etapas, alineada con las tareas e hitos del Perfil Ejecutivo. Cada gate tiene criterios "
    "de aceptación medibles: el financiamiento y las alianzas se liberan contra evidencia.",
    [("Stage-gate", ""), ("TRL 3 → 5/6", "mint"), ("Propuesta editable", "amber")],
)

TRL = [
    (1, "Principios básicos observados"), (2, "Concepto tecnológico formulado"), (3, "Prueba de concepto experimental"),
    (4, "Validación en laboratorio"), (5, "Validación en entorno relevante"), (6, "Demostración en entorno relevante"),
    (7, "Demostración en entorno operativo"), (8, "Sistema completo calificado"), (9, "Sistema probado en operación"),
]
c1, c2 = st.columns([1.3, 1], gap="large")
with c1:
    status = []
    for n, _ in TRL:
        status.append("actual (POC reportado)" if n <= 3 else ("objetivo 18 meses" if n <= 6 else "futuro"))
    colmap = {"actual (POC reportado)": ui.BRAND["navy"], "objetivo 18 meses": ui.BRAND["teal"], "futuro": "#CBD5E1"}
    fig = go.Figure()
    for stt in colmap:
        idx = [i for i, s_ in enumerate(status) if s_ == stt]
        fig.add_trace(go.Bar(y=[f"TRL {TRL[i][0]}" for i in idx], x=[1] * len(idx), orientation="h", name=stt,
                             marker_color=colmap[stt], text=[TRL[i][1] for i in idx], textposition="inside",
                             insidetextanchor="start", textfont=dict(color="white" if stt != "futuro" else "#334155", size=13),
                             hoverinfo="skip"))
    fig.update_yaxes(autorange="reversed", categoryorder="array", categoryarray=[f"TRL {n}" for n, _ in TRL])
    fig.update_xaxes(visible=False, range=[0, 1])
    ui.style_fig(fig, height=400, title="Madurez tecnológica (escala TRL)")
    fig.update_layout(bargap=0.18, margin=dict(l=70, r=10, t=40, b=10))
    ui.show(fig, key="trl")
with c2:
    ui.callout("info", "Dónde estamos",
               "La empresa reporta un POC completado (TRL 3, resultado interno). El programa MVP apunta a <b>TRL 4–5</b> "
               "(validación en laboratorio y entorno relevante) y, con pruebas prolongadas y verificación independiente, "
               "a <b>TRL 6</b>.")
    st.markdown("**Tareas MVP (Perfil Ejecutivo)**")
    for t in COMPANY["mvp_tasks"]:
        st.markdown(f"- {t}")

start = st.date_input("Inicio del programa", dt.date(2027, 1, 1))
start = pd.Timestamp(start)


def m(k):
    return start + pd.DateOffset(months=k)


wp = [
    ("WP0 Gobernanza, financiamiento y PI", 0, 18, "Gestión"),
    ("WP1 Metrología y frontera energética", 0, 4, "Validación"),
    ("WP2 Modelado termo-fluido y gemelo digital", 0, 8, "Ingeniería"),
    ("WP3 Diseño mecánico KEM / ABIS", 1, 9, "Ingeniería"),
    ("WP4 Eléctrica PDU + control CMS", 2, 10, "Ingeniería"),
    ("WP5a Construcción MVP-1 y MVP-2", 4, 10, "Construcción"),
    ("WP5b Construcción MVP-3 y MVP-4", 9, 14, "Construcción"),
    ("WP6 Campañas de ensayo repetibles", 8, 15, "Validación"),
    ("WP7 Ensayo autónomo prolongado", 13, 16, "Validación"),
    ("WP8 Validación independiente", 14, 17, "Validación"),
    ("WP9 Tecno-economía, confiabilidad, UCF/ELCC", 6, 18, "Negocio"),
    ("WP10 Industrialización y primeras implementaciones", 15, 18, "Negocio"),
]
gantt = pd.DataFrame([{"Paquete": n, "Inicio": m(a), "Fin": m(b), "Tipo": t} for n, a, b, t in wp])
fig = px.timeline(gantt, x_start="Inicio", x_end="Fin", y="Paquete", color="Tipo",
                  category_orders={"Paquete": [w[0] for w in wp]},
                  color_discrete_map={"Gestión": "#94A3B8", "Validación": ui.BRAND["navy"], "Ingeniería": ui.BRAND["blue"],
                                      "Construcción": ui.BRAND["amber"], "Negocio": ui.BRAND["teal"]})
fig.update_yaxes(title=None)
gates = [("G1", 4), ("G2", 10), ("G3", 15), ("G4", 16), ("G5", 17), ("G6", 18)]
for g, mo in gates:
    x = m(mo)
    fig.add_shape(type="line", x0=x, x1=x, y0=0, y1=1, yref="paper", line=dict(color=ui.BRAND["red"], width=1.5, dash="dot"))
fig.add_trace(go.Scatter(x=[m(mo) for _, mo in gates], y=[gantt["Paquete"].iloc[0]] * len(gates), mode="markers+text",
                         marker=dict(symbol="diamond", size=13, color=ui.BRAND["red"], line=dict(color="white", width=1.5)),
                         text=[g for g, _ in gates], textposition="top center", textfont=dict(color=ui.BRAND["red"], size=11),
                         name="Gates", hovertext=[f"{g} · mes {mo}" for g, mo in gates], hoverinfo="text", cliponaxis=False))
ui.style_fig(fig, height=540, title="Cronograma propuesto (18 meses) y gates de decisión (◆)")
fig.update_layout(margin=dict(t=60))
ui.show(fig, key="gantt")

st.subheader("Criterios de aceptación por gate")
gate_tbl = pd.DataFrame([
    ["G1 · M4", "Protocolo de ensayo y frontera aprobados por un revisor externo; instrumentos calibrados (trazabilidad SI); presupuesto U(k=2) del ERR ≤ 1,5 %.", "Ingeniería, metrología, laboratorio aliado"],
    ["G2 · M10", "MVP-1 y MVP-2 operando ≥ 100 h acumuladas; datos crudos accesibles; disponibilidad técnica ≥ 90 %.", "Fabricantes, ingeniería, inversión"],
    ["G3 · M15", "ERR medido en ≥ 3 MVP y ≥ 3 campañas cada uno, criterio pre-registrado; reproducibilidad entre MVP ≤ 3 %; identificación del flujo energético dominante.", "Universidades, metrología"],
    ["G4 · M16", "Operación autónoma (sin fuente externa) ≥ 72 h, o ≥ 10× la energía almacenable / potencia neta; estado inicial = final.", "Laboratorio independiente"],
    ["G5 · M17", "Informe de tercero acreditado (ISO/IEC 17025) con datos crudos y regla de decisión explícita.", "Entidad independiente"],
    ["G6 · M18", "Decisión: escalar (modelo de costos, MTBF/MTTR, plan de industrialización) o reorientar subsistemas (p. ej., almacenamiento).", "Inversionistas, aliados estratégicos"],
], columns=["Gate", "Criterio cuantitativo de aceptación", "Aliados críticos"])
st.table(gate_tbl.set_index("Gate"))

st.subheader("Matriz de riesgos técnicos")
risks = pd.DataFrame([
    ("R1", "Balance neto positivo no confirmado en frontera completa", 4, 5, "G3/G4 tempranos; hipótesis falsables; ruta de reorientación"),
    ("R2", "Metrología insuficiente o no trazable", 3, 4, "Laboratorio acreditado; analizadores clase 0,05–0,2"),
    ("R3", "Sincronización ABIS–KEM y deslizamiento del aire", 3, 3, "CMS con sensores de posición; CFD bifásico; ensayos paramétricos"),
    ("R4", "Corrosión, fatiga y mantenimiento", 3, 3, "Selección de materiales; ensayos acelerados; diseño para mantenibilidad"),
    ("R5", "Escalamiento no lineal (H, V₀, frecuencia)", 3, 4, "Gemelo digital validado; análisis adimensional"),
    ("R6", "CAPEX por kW neto no competitivo", 3, 4, "Diseño para fabricación; análisis de costo objetivo (CAPEX de equilibrio)"),
    ("R7", "Conexión a red y calidad de potencia", 2, 3, "Electrónica con control de rizado; cumplimiento de códigos de red"),
    ("R8", "Solicitudes de patente no concedidas o limitadas", 2, 3, "Estrategia de PI y secretos industriales; libertad de operación"),
], columns=["ID", "Riesgo", "Probabilidad", "Impacto", "Mitigación"])
c1, c2 = st.columns([1, 1.3], gap="large")
with c1:
    z = [[(i * j) for i in range(1, 6)] for j in range(1, 6)]
    fig = go.Figure(go.Heatmap(x=list(range(1, 6)), y=list(range(1, 6)), z=z, colorscale=[[0, "#ECFDF5"], [0.5, "#FEF3C7"], [1, "#FECACA"]],
                               showscale=False, hoverinfo="skip"))
    for _, rr in risks.iterrows():
        fig.add_annotation(x=rr["Probabilidad"], y=rr["Impacto"], text=f"<b>{rr['ID']}</b>", showarrow=False, font=dict(size=13, color="#0B2A5B"),
                           xshift=(int(rr["ID"][1:]) % 3 - 1) * 14, yshift=(int(rr["ID"][1:]) % 2) * 12 - 6)
    fig.update_xaxes(title="Probabilidad", tickvals=list(range(1, 6)))
    fig.update_yaxes(title="Impacto", tickvals=list(range(1, 6)))
    ui.style_fig(fig, height=420, title="Probabilidad × impacto")
    ui.show(fig, key="risk")
with c2:
    st.table(risks[["ID", "Riesgo", "Mitigación"]].set_index("ID"))

ui.callout("eoi", "Cómo se conecta con la convocatoria",
           "Cada paquete de trabajo es una puerta de entrada para un tipo de aliado: metrología y laboratorios (WP1, WP6–WP8), "
           "universidades y centros de investigación (WP2, WP9), fabricantes y proveedores (WP3–WP5), integradores (WP4, WP10) "
           "e inversionistas (WP0, con liberación de fondos por gate).")
ui.footer()
