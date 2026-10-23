"""
core/data.py — Datos de contexto, información pública de la empresa y fuentes.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

DISPATCH_COLS = [
    ("geotermia_MW", "Geotermia"),
    ("eolica_MW", "Eólica"),
    ("hidro_regulacion_MW", "Hidro regulación diaria"),
    ("hidro_filo_agua_MW", "Hidro filo de agua"),
    ("embalses_estacionales_MW", "Embalses estacionales ICE"),
    ("arenal_MW", "Arenal"),
    ("termica_MW", "Térmica"),
]


@st.cache_data(show_spinner=False)
def load_dispatch() -> pd.DataFrame:
    return pd.read_csv(DATA / "cr_despacho_2026-06-14_reconstruido.csv")


COMPANY = {
    "name": "Infinity Energy",
    "tagline": "Una nueva categoría de generación renovable firme",
    "tagline_en": "Clean Energy. Continuous. Everywhere.",
    "purpose": ("Desarrollar una solución modular de generación eléctrica diseñada para entregar potencia firme y "
                "continua las 24 horas, independiente del sol, el viento y los combustibles fósiles."),
    "concept": ("Inserción de cuerpos de aire en una columna de agua para aprovechar la flotabilidad, producir "
                "movimiento mecánico y accionar un sistema de generación eléctrica."),
    "stage": "Pre-Seed · POC completado (reportado por la empresa) · Próximo: 3–4 MVP + validación independiente",
    "patents": ["Costa Rica 2024-0000354", "PCT/CR2025/050003", "India 202617045117"],
    "team": [("Alvaro Cruz Ibarra", "Fundador e inventor"), ("Alvaro Blanco", "Ingeniero líder")],
    "email": "info@infinityen.energy",
    "web": "https://www.infinityen.energy",
    "subsystems": [
        ("ABIS", "Air Body Insertion System",
         "Inserta cuerpos de aire en la base de la columna. Métrica clave: energía por inserción/ciclo."),
        ("KEM", "Sistema de generación mecánica",
         "Convierte la flotabilidad en movimiento de eje. Métricas: par, pérdidas, estabilidad."),
        ("PDU", "Power Delivery Unit",
         "Generación y acondicionamiento eléctrico. Métricas: potencia útil, tensión, frecuencia, consumo auxiliar."),
        ("CMS", "Control & Management System",
         "Sincronización, protección, adquisición de datos y optimización del punto de operación."),
    ],
    "mvp_tasks": [
        "Diseñar la arquitectura mecánica, eléctrica y de control de los MVPs.",
        "Reproducir y verificar las mediciones de entradas y salidas energéticas.",
        "Optimizar eficiencia, componentes, transmisión y operación del sistema.",
        "Realizar pruebas de estabilidad y funcionamiento continuo.",
        "Contrastar resultados mediante especialistas o entidades independientes.",
        "Estimar costos de fabricación, instalación, operación y mantenimiento.",
    ],
    "milestones_18m": [
        "Completar el diseño y la construcción de los 3–4 MVPs.",
        "Obtener resultados energéticos repetibles, documentados y auditables.",
        "Validar estabilidad y desempeño en pruebas prolongadas.",
        "Realizar pruebas y revisiones técnicas independientes.",
        "Estandarizar el diseño y afinar la estructura de costos.",
        "Preparar la hoja de ruta de industrialización y primeras implementaciones.",
    ],
    "markets": ["Generación distribuida", "Instalaciones industriales", "Centros de datos / IA",
                "Infraestructura crítica", "Comunidades y sistemas aislados", "Complemento a solar y otras renovables"],
}

# Cifras de contexto (Costa Rica, 2025–2026) con id de fuente
CR_FACTS = {
    "peak_record_MW": (2040.9, "29-jun-2026", "S1"),
    "peak_2025_MW": (1940.23, "2025", "S2"),
    "installed_2025_MW": (3658.6, "2025", "S3"),
    "demand_2025_GWh": (12995.4, "2025", "S3"),
    "thermal_rental_MW": (273, "2027–2029", "S4"),
    "thermal_rental_usd": (320e6, "adjudicado oct-2026", "S5"),
    "moin_iv_MW": (200, "2029", "S6"),
    "q1_2026_growth": (3.35, "% interanual T1-2026", "S7"),
    "renewable_2025": (98.6, "% renovable 2025", "S8"),
}

CR_CAPACITY_2025 = {  # MW (DOCSE-ICE, Informe de atención de demanda 2025)
    "Hidroeléctrica": 2341.7, "Termoeléctrica": 531.0, "Eólica": 436.7,
    "Geotérmica": 262.7, "Bagazo": 71.0, "Solar": 15.5,
}

NEW_LOADS = [  # cargas 24/7 mencionadas en el video (declaraciones públicas)
    ("Fertilizantes verdes (hidrógeno/amoníaco)", 250),
    ("Fabricación de semiconductores", 500),
    ("Centros de datos", 200),
]

SOURCES = {
    "V1": ("Video: «Ejemplo de la problemática en la matriz de generación actual CR» (TV Legislativa, despacho DOCSE-ICE "
           "del 14/06/2026)", "https://youtu.be/j5LNATUHgT4"),
    "S1": ("La Nación (22-oct-2026): demanda máxima histórica de 2 040,9 MW el 29 de junio de 2026",
           "https://www.nacion.com/el-pais/demanda-electrica-crece-mas-rapido-que-la/WW6JCYFWTZH4DLEOUPDUSOKYZA/story/"),
    "S2": ("ICE-CENCE, Producción y Demanda — Informe Anual 2025",
           "https://apps.grupoice.com/CenceWeb/documentos/3/3008/28/Informe%20Anual%202025.pdf"),
    "S3": ("ICE-DOCSE, Informe de atención de demanda y producción de electricidad con fuentes renovables 2025",
           "https://apps.grupoice.com/CenceWeb/documentos/3/3008/27/R01-PDOCSE-07%20Informe_Atenci%C3%B3n%20demanda%20y%20producci%C3%B3n_2025_v2_firmado.pdf"),
    "S4": ("Semanario Universidad (29-may-2026): ICE contrata 273 MW térmicos de alquiler ante riesgo 2027–2029",
           "https://semanariouniversidad.com/pais/ice-corre-para-alquilar-plantas-termicas-privadas-ante-riesgo-de-desabastecimiento-en-verano-del-2027/"),
    "S5": ("CRHoy (21-oct-2026): contratación de USD 320 millones en seis bloques térmicos desde el 1-ene-2027",
           "https://crhoy.com/nacionales/contratacion-de-320-millones-en-energia-termica-del-ice-arrancara-en-2027/"),
    "S6": ("Delfino (dic-2025): Consejo del ICE aprueba USD 400 M para la Planta Térmica Moín IV (200 MW, 2029)",
           "https://delfino.cr/2025/12/consejo-del-ice-aprueba-destinar-400-millones-para-una-nueva-planta-termica"),
    "S7": ("CET-CR (may-2026): crecimiento de demanda de 3,35 % interanual en T1-2026",
           "https://www.cet-cr.org/post/the-electric-power-system-is-entering-a-pressure-zone-and-tourism-should-take-note"),
    "S8": ("Grupo ICE: Costa Rica produjo 98,6 % de su electricidad con fuentes renovables en 2025",
           "https://www.grupoice.com/"),
    "S9": ("IRENA (2025): Renewable Power Generation Costs in 2024",
           "https://www.irena.org/Digital-Report/Renewable-Power-Generation-Costs-in-2024"),
    "S10": ("IRENA (2026): 24/7 renewables — The economics of firm solar and wind",
            "https://www.irena.org/-/media/Files/IRENA/Agency/Publication/2026/May/IRENA_TEC_24-7_renewables_2026.pdf"),
    "S11": ("Garver, L. L. (1966). Effective load carrying capability of generating units. IEEE Trans. PAS-85(8), 910–919.",
            "https://doi.org/10.1109/TPAS.1966.291652"),
    "S12": ("JCGM 100:2008 — Evaluation of measurement data: Guide to the expression of uncertainty in measurement (GUM)",
            "https://www.bipm.org/en/committees/jc/jcgm/publications"),
    "S13": ("Hunt, J. D. et al. (2021). Buoyancy Energy Storage Technology. Journal of Energy Storage, 40, 102746.",
            "https://doi.org/10.1016/j.est.2021.102746"),
    "S14": ("Infinity Energy — sitio web y Perfil Ejecutivo (octubre 2026)", "https://www.infinityen.energy"),
}


def source_line(*ids: str) -> str:
    parts = []
    for i in ids:
        txt, url = SOURCES[i]
        parts.append(f'[{i}] <a href="{url}" target="_blank">{txt}</a>')
    return "Fuentes: " + " · ".join(parts)
