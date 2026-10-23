import datetime as dt
import json
import re
import urllib.parse

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import ui
from core.data import COMPANY

ui.page_header(
    "6 · Convocatoria",
    "Convocatoria de Expresiones de Interés",
    "Infinity Energy busca colaboradores, aliados estratégicos e inversionistas para diseñar, construir y validar de "
    "forma independiente sus 3–4 MVP. Esta página traduce el programa técnico en oportunidades concretas de participación.",
    [("Talento de ingeniería", ""), ("Tecnología e infraestructura", ""), ("Aliados estratégicos", "mint"), ("Inversión Pre-Seed", "amber")],
)

ui.cards([
    {"num": "Perfil 1", "title": "Ingeniería y especialización técnica",
     "body": "<p><b>Buscamos:</b> diseño mecánico, ingeniería eléctrica y de potencia, automatización y control, metrología, "
             "ensayos, optimización y evaluación técnica independiente.</p><p><b>Aporta valor en:</b> WP1–WP8.</p>"},
    {"num": "Perfil 2", "title": "Tecnología, materiales, componentes e infraestructura",
     "body": "<p><b>Buscamos:</b> compresores y válvulas, generadores de baja velocidad, electrónica de potencia, materiales "
             "resistentes a corrosión, manufactura y bancos de prueba.</p><p><b>Aporta valor en:</b> WP3–WP5, WP10.</p>"},
    {"num": "Perfil 3", "title": "Aliados estratégicos: empresas, universidades e instituciones",
     "body": "<p><b>Buscamos:</b> universidades y centros de investigación (tesis, laboratorios, publicaciones), integradores, "
             "usuarios industriales 24/7 y entidades del sector.</p><p><b>Aporta valor en:</b> WP2, WP6–WP9.</p>"},
    {"num": "Perfil 4", "title": "Inversionistas y socios de financiamiento",
     "body": "<p><b>Buscamos:</b> capital Pre-Seed y acompañamiento estratégico para MVP y validación, con liberación por gates "
             "verificables.</p><p><b>Aporta valor en:</b> WP0 y en la decisión de escalamiento (G6).</p>"},
], min_width=230)

st.subheader("Mapa de participación: paquetes de trabajo × perfiles")
wps = ["WP0 Gobernanza/financiamiento", "WP1 Metrología y frontera", "WP2 Modelado y gemelo digital", "WP3 Diseño KEM/ABIS",
       "WP4 PDU y control CMS", "WP5 Construcción de MVP", "WP6 Campañas de ensayo", "WP7 Ensayo autónomo",
       "WP8 Validación independiente", "WP9 Tecno-economía · UCF/ELCC", "WP10 Industrialización"]
profiles = ["Ingeniería", "Tecnología / materiales", "Aliados estratégicos", "Inversión"]
M = [[1, 0, 1, 3], [3, 1, 2, 0], [2, 0, 3, 0], [3, 3, 1, 0], [3, 3, 1, 0], [2, 3, 1, 1], [3, 1, 3, 0], [2, 1, 2, 1],
     [2, 0, 3, 1], [2, 0, 3, 2], [1, 3, 2, 3]]
fig = go.Figure(go.Heatmap(z=M, x=profiles, y=wps, colorscale=[[0, "#F8FAFC"], [0.34, "#D6F3EC"], [0.67, "#7FD9C6"], [1, "#0FA99A"]],
                           showscale=False, text=[[["", "●", "●●", "●●●"][v] for v in row] for row in M], texttemplate="%{text}",
                           hovertemplate="%{y} · %{x}<extra></extra>"))
fig.update_yaxes(autorange="reversed")
ui.style_fig(fig, height=460, title="Relevancia de cada perfil por paquete de trabajo (●●● = crítico)")
ui.show(fig, key="wpmap")

with st.expander("🎓 Preguntas abiertas de investigación (temas de tesis y proyectos conjuntos)"):
    st.markdown("""
- **Termofluidos bifásicos:** eficiencia de captura del trabajo de flotación; deslizamiento aire–cangilón; CFD con interfaz libre.
- **Compresión cuasi-isotérmica:** pistón líquido, aspersión y espumas para acercar el ABIS al límite p₀V₀·ln(p_H/p₀).
- **Máquinas eléctricas de baja velocidad y alto par:** PMSG de accionamiento directo vs caja multiplicadora; control de rizado.
- **Integración a red:** calidad de potencia, inercia sintética, códigos de red y operación en isla.
- **Valor sistémico:** funciones de costo de incertidumbre (UCF/MUCF), ELCC y despacho estocástico con fuentes firmes modulares.
- **Metrología energética:** presupuestos GUM, regla de decisión y protocolos de ensayo para conceptos energéticos no convencionales.
- **Confiabilidad:** modos de falla, MTBF/MTTR, mantenimiento predictivo con datos del CMS.
- **Opcionalidad:** almacenamiento por flotabilidad / aire comprimido subacuático con los mismos subsistemas.
""")

st.subheader("Registrar su interés")
st.caption("El formulario genera un correo prellenado para info@infinityen.energy y un archivo JSON. No se almacena "
           "información en esta demo, salvo que el operador configure un webhook en `st.secrets`.")

with st.form("eoi_form", clear_on_submit=False):
    c1, c2 = st.columns(2, gap="large")
    with c1:
        name = st.text_input("Nombre y apellido *")
        org = st.text_input("Organización *")
        email = st.text_input("Correo electrónico *")
        country = st.text_input("País", value="Costa Rica")
        role = st.text_input("Cargo / área")
    with c2:
        profile = st.selectbox("Perfil principal *", ["Ingeniería y especialización técnica", "Tecnología, materiales e infraestructura",
                                                      "Aliado estratégico (empresa, universidad, institución)", "Inversionista / financiamiento"])
        wp_sel = st.multiselect("Paquetes de trabajo de interés", wps, placeholder="Seleccione uno o varios")
        contrib = st.multiselect("Tipo de aporte", ["Horas de ingeniería", "Laboratorio / banco de pruebas", "Componentes / materiales",
                                                     "Manufactura", "Investigación conjunta / tesis", "Validación independiente",
                                                     "Capital", "Red de contactos / mercado"], placeholder="Seleccione uno o varios")
        ticket = st.selectbox("Rango de inversión (si aplica)", ["No aplica", "< USD 50 k", "USD 50–150 k", "USD 150–500 k", "> USD 500 k"])
        horizon = st.selectbox("Horizonte de participación", ["Inmediato (0–3 meses)", "Corto plazo (3–6 meses)", "Mediano plazo (6–18 meses)"])
    msg = st.text_area("Mensaje / capacidades que aporta", height=110)
    consent = st.checkbox("Acepto que Infinity Energy me contacte en relación con esta convocatoria. *")
    submitted = st.form_submit_button("Generar expresión de interés", type="primary", icon=":material/send:")

if submitted:
    errors = []
    if not name.strip():
        errors.append("nombre")
    if not org.strip():
        errors.append("organización")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()):
        errors.append("correo válido")
    if not consent:
        errors.append("consentimiento")
    if errors:
        st.error("Complete: " + ", ".join(errors) + ".")
    else:
        payload = {
            "fecha": dt.datetime.now().isoformat(timespec="seconds"), "nombre": name.strip(), "organizacion": org.strip(),
            "correo": email.strip(), "pais": country.strip(), "cargo": role.strip(), "perfil": profile,
            "paquetes_trabajo": wp_sel, "aportes": contrib, "rango_inversion": ticket, "horizonte": horizon,
            "mensaje": msg.strip(), "fuente": "Firm Power Lab (demo científica)",
        }
        body = "\n".join([f"{k}: {', '.join(v) if isinstance(v, list) else v}" for k, v in payload.items()])
        subject = f"Expresión de Interés — {profile} — {org.strip()}"
        mailto = f"mailto:{COMPANY['email']}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
        st.success("¡Gracias! Su expresión de interés está lista. Envíela por correo o descargue el archivo.")
        cA, cB = st.columns(2)
        with cA:
            st.link_button("Enviar por correo a info@infinityen.energy", mailto, type="primary", icon=":material/mail:")
        with cB:
            st.download_button("Descargar JSON", json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
                               f"expresion_interes_{re.sub(r'[^A-Za-z0-9]+', '_', org.strip())[:40]}.json", "application/json")
        hook = None
        try:
            hook = st.secrets.get("EOI_WEBHOOK_URL")
        except Exception:  # noqa: BLE001
            hook = None
        if hook:
            try:
                import requests
                rr = requests.post(hook, json=payload, timeout=10)
                if rr.ok:
                    st.info("Registro enviado al sistema de la convocatoria.")
                else:
                    st.warning(f"El webhook respondió {rr.status_code}; use el correo como respaldo.")
            except Exception as e:  # noqa: BLE001
                st.warning(f"No se pudo contactar el webhook ({e}); use el correo como respaldo.")

st.subheader("Próximos pasos")
ui.steps([
    ("Registro de interés", "Formulario o correo a info@infinityen.energy."),
    ("Conversación inicial", "Alineación de objetivos, capacidades y, si corresponde, acuerdo de confidencialidad (NDA)."),
    ("Acceso técnico", "Protocolo de ensayo, plan de MVP, criterios de gate y datos disponibles."),
    ("Acuerdo de participación", "Colaboración técnica, convenio académico, suministro o inversión por etapas."),
])
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Equipo (según el sitio web)**")
    for n, r_ in COMPANY["team"]:
        st.markdown(f"- **{n}** — {r_}")
    st.markdown("- Asesoría especializada en energías renovables")
with c2:
    st.markdown("**Contacto**")
    st.markdown(f"✉️ [{COMPANY['email']}](mailto:{COMPANY['email']})  \n🌐 [{COMPANY['web'].replace('https://', '')}]({COMPANY['web']})")
    st.markdown("**Propiedad intelectual (solicitudes en trámite):** " + " · ".join(COMPANY["patents"]))

ui.footer()
