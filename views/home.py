import streamlit as st

from core import ui
from core.data import COMPANY, source_line

logo_sym = ui.img_b64("logo_symbol.png")

st.markdown(
    f"""
<div class="ie-hero">
  <div style="display:flex;gap:26px;align-items:center;flex-wrap:wrap;position:relative;z-index:2">
    <div style="background:#fff;border-radius:18px;padding:12px 14px;box-shadow:0 6px 18px rgba(0,0,0,.15)">
      <img src="{logo_sym}" style="height:62px;display:block">
    </div>
    <div style="flex:1;min-width:300px">
      <h1>Potencia firme renovable: de la prueba de concepto a la validación independiente</h1>
      <p>Plataforma abierta para evaluar con rigor de ingeniería eléctrica la propuesta de Infinity Energy:
      el problema sistémico que busca resolver, la física que debe demostrar, el valor que aportaría a la red
      —cuantificado con funciones de costo de incertidumbre (UCF), confiabilidad y tecno-economía— y el
      protocolo de validación de sus MVP.</p>
      <span class="ie-chip">Pre-Seed</span><span class="ie-chip">POC completado · reportado por la empresa</span>
      <span class="ie-chip">Próximo: 3–4 MVP</span><span class="ie-chip">Validación independiente</span>
      <span class="ie-chip">Costa Rica 🇨🇷</span>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.write("")
c1, c2 = st.columns([1.35, 1], gap="large")
with c1:
    st.subheader("La propuesta en 60 segundos")
    st.markdown(
        f"**Propósito.** {COMPANY['purpose']}\n\n"
        f"**Principio.** {COMPANY['concept']} La empresa trabaja en ingeniería y validación para establecer "
        "de forma repetible su rendimiento, eficiencia y operación prolongada."
    )
    ui.cards([
        {"num": "ABIS", "title": "Inserción de aire", "body": "<p>Introduce cuerpos de aire en la base de la columna. <b>Mide:</b> energía por inserción.</p>"},
        {"num": "KEM", "title": "Generación mecánica", "body": "<p>Convierte flotabilidad en par y giro. <b>Mide:</b> par, pérdidas, estabilidad.</p>"},
        {"num": "PDU", "title": "Entrega de potencia", "body": "<p>Generador + electrónica. <b>Mide:</b> potencia útil, V, f, consumo auxiliar.</p>"},
        {"num": "CMS", "title": "Control y datos", "body": "<p>Sincronización, protecciones, adquisición y punto óptimo de operación.</p>"},
    ], min_width=210)
with c2:
    st.image("assets/prototipo_poc.jpg", width="stretch",
             caption="Prototipo de prueba de concepto · imagen de Infinity Energy (ilustración conceptual del sitio web).")

st.write("")
st.subheader("Postura científica de esta plataforma")
cA, cB, cC = st.columns(3, gap="medium")
with cA:
    ui.callout("info", "Lo establecido (física)",
               "La hidrostática y la termodinámica fijan cotas claras: en un ciclo cerrado sin un flujo de energía "
               "externo identificado, el trabajo de flotación recuperable no supera el trabajo mínimo de inserción "
               "del aire (ERR ≤ 1). Esta plataforma lo muestra explícitamente, con ecuaciones y modelos abiertos.")
with cB:
    ui.callout("warning", "Lo reportado (empresa)",
               "Infinity Energy reporta un balance energético positivo en su POC, obtenido antes de varias "
               "optimizaciones. Es un resultado experimental interno: aún no constituye demostración independiente "
               "ni certificación de desempeño.")
with cC:
    ui.callout("success", "Lo que el MVP debe demostrar",
               "ERR &gt; 1 <b>repetible</b>, con incertidumbre expandida U(k=2) que excluya 1, en <b>frontera "
               "completa</b> (todas las entradas, auxiliares y almacenamientos), operación autónoma prolongada, "
               "verificación <b>independiente</b> e identificación del flujo energético que lo explica.")

st.write("")
ui.kpis([
    {"label": "Demanda máxima histórica CR", "value": "2 040,9 MW", "sub": "29-jun-2026 · por encima de la proyección (2 013 MW)", "accent": ui.BRAND["navy"]},
    {"label": "Térmica de alquiler 2027–2029", "value": "273 MW", "sub": "≈ USD 320 M adjudicados (6 bloques)", "accent": ui.BRAND["red"]},
    {"label": "Nuevas cargas 24/7 en discusión", "value": "≈ 950 MW", "sub": "fertilizantes 250 · semiconductores 500 · centros de datos 200", "accent": ui.BRAND["amber"]},
    {"label": "Arenal el 14-jun-2026", "value": "≈ 350 MW", "sub": "las 24 h: embalse estratégico casi a máxima potencia todo el día", "accent": ui.BRAND["blue"]},
    {"label": "Referencia firme a superar", "value": "54–82 USD/MWh", "sub": "FV+BESS 24/7 (95 %) en sitios de alto recurso · IRENA 2026", "accent": ui.BRAND["teal"]},
])
ui.source(source_line("S1", "S5", "V1", "S10"))

st.write("")
st.subheader("Recorrido sugerido")
nav = [
    ("views/demo.py", "1 · Demo del ciclo", "Animación interactiva, dinámica electromecánica y arquitectura ABIS–KEM–PDU–CMS.", ":material/water_drop:"),
    ("views/fisica.py", "1 · Física y balance", "Ciclo p–V animado, cotas termodinámicas, flujo de energía animado y la hipótesis de aporte térmico.", ":material/science:"),
    ("views/contexto.py", "2 · El problema", "Despacho real de Costa Rica (14-jun-2026), nuevas cargas 24/7 y brecha de potencia firme.", ":material/bolt:"),
    ("views/ucf_page.py", "3 · Costos de incertidumbre", "Despacho bajo incertidumbre animado, UCF/MUCF por tecnología, verificación Monte Carlo y despacho económico.", ":material/functions:"),
    ("views/firmeza.py", "3 · Firmeza y confiabilidad", "Simulación animada de módulos (Markov), capacidad firme (COPT) y crédito de capacidad (ELCC).", ":material/shield:"),
    ("views/validacion.py", "4 · Protocolo MVP", "Frontera de balance, presupuesto GUM, simulador de campañas y análisis de CSV.", ":material/biotech:"),
    ("views/roadmap.py", "4 · Hoja de ruta", "TRL, cronograma de 18 meses, gates cuantitativos y matriz de riesgos.", ":material/route:"),
    ("views/tecnoeconomia.py", "5 · Tecno-economía", "LCOE, LCOE firme FV+BESS, CAPEX de equilibrio y sensibilidad.", ":material/payments:"),
    ("views/eoi.py", "6 · Expresión de Interés", "Perfiles buscados, paquetes de trabajo y formulario de registro.", ":material/handshake:"),
]
cols = st.columns(3, gap="medium")
for i, (page, title, desc, icon) in enumerate(nav):
    with cols[i % 3]:
        with st.container(border=True):
            st.page_link(page, label=title, icon=icon)
            st.caption(desc)

ui.footer()
