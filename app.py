"""
Infinity Energy · Firm Power Lab
Plataforma científica de evaluación (Streamlit) — navegación y tema.

Ejecutar localmente:   streamlit run app.py
"""
import streamlit as st

from core import ui

st.set_page_config(
    page_title="Infinity Energy · Firm Power Lab",
    page_icon="assets/logo_symbol.png",
    layout="wide",
    initial_sidebar_state="expanded",
)
ui.inject_css()

PAGES = {
    "Inicio": [
        st.Page("views/home.py", title="Resumen ejecutivo", icon=":material/home:", default=True),
    ],
    "1 · La tecnología": [
        st.Page("views/demo.py", title="Demo interactiva del ciclo", icon=":material/water_drop:", url_path="demo"),
        st.Page("views/fisica.py", title="Física y balance energético", icon=":material/science:", url_path="fisica"),
    ],
    "2 · El problema": [
        st.Page("views/contexto.py", title="Sistema eléctrico y brecha firme", icon=":material/bolt:", url_path="contexto"),
    ],
    "3 · Valor sistémico": [
        st.Page("views/ucf_page.py", title="Costos de incertidumbre (UCF)", icon=":material/functions:", url_path="ucf"),
        st.Page("views/firmeza.py", title="Firmeza y confiabilidad", icon=":material/shield:", url_path="firmeza"),
    ],
    "4 · Validación": [
        st.Page("views/validacion.py", title="Protocolo MVP y metrología", icon=":material/biotech:", url_path="validacion"),
        st.Page("views/roadmap.py", title="Hoja de ruta, TRL y riesgos", icon=":material/route:", url_path="hoja-de-ruta"),
    ],
    "5 · Negocio": [
        st.Page("views/tecnoeconomia.py", title="Tecno-economía", icon=":material/payments:", url_path="tecnoeconomia"),
    ],
    "6 · Convocatoria": [
        st.Page("views/eoi.py", title="Expresión de Interés", icon=":material/handshake:", url_path="expresion-de-interes"),
    ],
}

pg = st.navigation(PAGES, position="sidebar", expanded=True)

st.logo("assets/logo_infinity.png", icon_image="assets/logo_symbol.png", size="large",
        link="https://www.infinityen.energy")

with st.sidebar:
    st.markdown(
        '<div style="font-size:.78rem;color:#5B6B80;line-height:1.45;margin-top:.4rem">'
        '<b style="color:#0B2A5B">Firm Power Lab</b> · demo científica para la Convocatoria de '
        'Expresiones de Interés.<br>Modelos abiertos, supuestos explícitos y validación falsable.</div>',
        unsafe_allow_html=True,
    )
    st.page_link("views/eoi.py", label="Registrar interés", icon=":material/how_to_reg:")

pg.run()
