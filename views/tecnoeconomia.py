import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import ui
from core.data import source_line
from core.economics import (BENCHMARKS, breakeven_capex, co2_avoided_t, cr_rental_capacity_cost, firm_pv_bess, lcoe,
                            thermal_cost_mwh)
from core.ucf import FirmModularResource, PVResource, WindResource, levelized_uncertainty_cost

ui.page_header(
    "5 · Negocio",
    "Tecno-economía paramétrica: ¿a qué costo competiría una fuente firme modular?",
    "Los costos de Infinity Energy aún no están definidos (dependen de la validación de los MVP). Esta página invierte la "
    "pregunta: dado el valor de la firmeza en el mercado, ¿qué CAPEX y desempeño debe alcanzar el producto?",
    [("LCOE · CRF", ""), ("LCOE firme FV+BESS", ""), ("CAPEX de equilibrio", "mint"), ("Supuestos de escenario", "amber")],
)
ui.callout("warning", "Condición previa",
           "Todo el análisis se expresa por <b>kW neto</b> (salida útil menos consumos propios). Solo tiene sentido económico si "
           "el MVP valida una potencia neta positiva y sostenida en frontera completa.")

c1, c2, c3 = st.columns(3, gap="large")
with c1:
    st.markdown("**Escenario IE (por kW neto)**")
    capex = st.slider("CAPEX (USD/kW neto)", 500, 15000, 3500, 100)
    fom_pct = st.slider("O&M fijo (% CAPEX/año)", 0.5, 8.0, 3.0, 0.1)
    vom = st.slider("O&M variable (USD/MWh)", 0.0, 40.0, 5.0, 0.5)
with c2:
    st.markdown("**Desempeño y financiamiento**")
    A = st.slider("Disponibilidad", 0.70, 0.99, 0.92, 0.01)
    load = st.slider("Factor de carga cuando disponible", 0.5, 1.0, 0.95, 0.01)
    life = st.slider("Vida útil (años)", 10, 35, 20, 1)
    wacc = st.slider("WACC real (%)", 3.0, 16.0, 9.0, 0.5) / 100
with c3:
    st.markdown("**Referencias de mercado (editables)**")
    fuel = st.slider("Costo variable térmico CR (USD/MWh)", 120, 400, 230, 10)
    cf_th = st.slider("Factor de planta de la térmica de respaldo", 0.05, 0.8, 0.30, 0.05)
    ef = st.slider("Factor de emisión térmica (tCO₂/MWh)", 0.5, 0.9, 0.70, 0.01)

cf = A * load
lc_ie = lcoe(capex, fom_pct / 100 * capex, vom, cf, wacc, life)
cap_cost = cr_rental_capacity_cost()
lc_th = thermal_cost_mwh(cf_th, cap_cost, fuel)


@st.cache_data(show_spinner=False)
def _luc(A, cvm=0.03, N=100):
    cu, co = 50.0, 300.0
    return {
        "Solar FV": levelized_uncertainty_cost(PVResource(P_r=50), cu, co)["LUC_mean"],
        "Eólica": levelized_uncertainty_cost(WindResource(W_r=50), cu, co)["LUC_mean"],
        "IE": levelized_uncertainty_cost(FirmModularResource(N=N, P_m=0.5, A=A, cv=cvm), cu, co)["LUC_mean"],
    }


luc = _luc(A)

tab1, tab2, tab3, tab4 = st.tabs(["💲 Comparación de costos", "🎯 CAPEX de equilibrio", "🔋 Firmeza FV + BESS (Costa Rica)", "🌪️ Sensibilidad"])

with tab1:
    rows = []
    for b in BENCHMARKS:
        if b["lcoe"] is None:
            continue
        add = luc["Solar FV"] if "Solar" in b["tecnologia"] and "BESS" not in b["tecnologia"] else (luc["Eólica"] if "Eólica" in b["tecnologia"] else 0.0)
        rows.append({"Tecnología": b["tecnologia"], "LCOE": b["lcoe"], "Costo de incertidumbre": add, "Firme": b["firme"],
                     "rango": b.get("lcoe_hi")})
    rows.append({"Tecnología": f"Térmica de alquiler CR (CF {cf_th:.0%})", "LCOE": lc_th, "Costo de incertidumbre": 0.0, "Firme": True, "rango": None})
    rows.append({"Tecnología": "IE — escenario", "LCOE": lc_ie, "Costo de incertidumbre": luc["IE"], "Firme": True, "rango": None})
    dfc = pd.DataFrame(rows)
    fig = go.Figure()
    fig.add_trace(go.Bar(y=dfc["Tecnología"], x=dfc["LCOE"], orientation="h", name="LCOE",
                         marker_color=[ui.TECH_COLORS["IE (escenario)"] if "IE" in t else (ui.BRAND["red"] if "Térmica" in t else ui.BRAND["blue"]) for t in dfc["Tecnología"]]))
    fig.add_trace(go.Bar(y=dfc["Tecnología"], x=dfc["Costo de incertidumbre"], orientation="h", name="Costo de incertidumbre (UCF*)", marker_color=ui.BRAND["navy"]))
    for i, rr in dfc.iterrows():
        if pd.notna(rr["rango"]) and rr["rango"]:
            fig.add_shape(type="line", x0=rr["LCOE"], x1=rr["rango"], y0=i, y1=i, line=dict(color=ui.BRAND["amber"], width=6))
    fig.update_layout(barmode="stack")
    fig.update_yaxes(autorange="reversed")
    ui.style_fig(fig, height=430, title="LCOE + costo de incertidumbre (USD/MWh)", xaxis_title="USD/MWh")
    ui.show(fig, key="lcoe")
    ui.kpis([
        {"label": "LCOE IE (escenario)", "value": f"{lc_ie:,.0f} USD/MWh", "sub": f"CF = {cf:.0%} · CRF = {wacc:.1%}, {life} años", "accent": ui.TECH_COLORS["IE (escenario)"]},
        {"label": "Térmica de alquiler CR", "value": f"{lc_th:,.0f} USD/MWh", "sub": f"capacidad ≈ {cap_cost:,.0f} USD/kW-año + combustible".replace(",", " "), "accent": ui.BRAND["red"]},
        {"label": "Emisiones evitadas", "value": f"{co2_avoided_t(8760*cf, ef):,.0f} t CO₂".replace(",", " "), "sub": "por MW-año, si desplaza térmica", "accent": ui.BRAND["green"]},
        {"label": "Ingreso por MW firme", "value": f"USD {cap_cost*1000/1e3:,.0f} k/año".replace(",", " "), "sub": "costo de capacidad evitado (sin energía)", "accent": ui.BRAND["navy"]},
    ])
    ui.source(source_line("S9", "S10", "S5"))

with tab2:
    targets = {"Térmica de alquiler CR": lc_th, "FV+BESS firme (IRENA, 82 USD/MWh)": 82.0, "FV+BESS firme (IRENA, 54 USD/MWh)": 54.0,
               "Geotermia (60 USD/MWh)": 60.0}
    tgt_name = st.radio("Costo objetivo a igualar", list(targets), horizontal=True)
    tgt = targets[tgt_name]
    A_grid = np.linspace(0.70, 0.99, 30)
    w_grid = np.linspace(0.04, 0.16, 25)
    Z = np.array([[breakeven_capex(tgt, fom_pct / 100 * 3000, vom, a * load, w, life, adders_mwh=luc["IE"]) for a in A_grid] for w in w_grid])
    c1, c2 = st.columns([1.4, 1], gap="large")
    with c1:
        fig = go.Figure(go.Contour(x=A_grid, y=100 * w_grid, z=Z, colorscale="Teal", contours=dict(showlabels=True, labelfont=dict(size=10)),
                                   colorbar=dict(title="USD/kW")))
        fig.add_trace(go.Scatter(x=[A], y=[100 * wacc], mode="markers", marker=dict(size=13, color="white", line=dict(color="#0B2A5B", width=3)), name="escenario"))
        ui.style_fig(fig, height=430, title=f"CAPEX máximo (USD/kW neto) para igualar: {tgt_name}", xaxis_title="disponibilidad", yaxis_title="WACC (%)")
        ui.show(fig, key="be")
    with c2:
        be_now = breakeven_capex(tgt, fom_pct / 100 * capex, vom, cf, wacc, life, adders_mwh=luc["IE"])
        ui.kpis([{"label": "CAPEX de equilibrio en el escenario", "value": f"{be_now:,.0f} USD/kW".replace(",", " "),
                  "sub": f"objetivo {tgt:,.0f} USD/MWh · O&M fijo según CAPEX actual".replace(",", " "), "accent": ui.BRAND["teal"]}])
        ui.callout("science", "Cómo leerlo",
                   "Cada curva indica el CAPEX por kW neto que haría competitivo al producto frente al objetivo elegido. "
                   "Es un <b>costo objetivo de diseño</b> para el equipo de ingeniería y una métrica clara para inversionistas.")
        st.caption("Nota: el O&M fijo del mapa se evalúa a 3 000 USD/kW para mantener el mapa independiente del CAPEX.")

with tab3:
    c1, c2 = st.columns([1, 1.6], gap="large")
    with c1:
        Lmw = st.number_input("Carga plana 24/7 (MW)", 1.0, 2000.0, 100.0, 10.0)
        yld = st.slider("Rendimiento FV (kWh/kWp·día)", 3.0, 6.5, 4.5, 0.1, help="Costa Rica: ~4–5 en estación lluviosa, más en Guanacaste en época seca.")
        pvc = st.slider("CAPEX FV (USD/kW)", 400, 1500, 708, 10)
        bc = st.slider("CAPEX BESS energía (USD/kWh)", 80, 400, 150, 5, help="IRENA: 197 USD/kWh en 2024, con caída ~30 % en 2025.")
        bp = st.slider("CAPEX BESS potencia (USD/kW)", 50, 400, 150, 10)
        eta = st.slider("Eficiencia ida y vuelta", 0.75, 0.95, 0.88, 0.01)
        aut = st.slider("Días de autonomía para nubosidad", 0.0, 3.0, 0.0, 0.25)
        w2 = st.slider("WACC (%)", 3.0, 16.0, 8.0, 0.5, key="w2") / 100
    res = firm_pv_bess(Lmw, pvc, bc, bp, eta, 0.9, aut, yld, w2)
    with c2:
        ui.kpis([
            {"label": "FV requerida", "value": f"{res['P_pv_MW']:,.0f} MW".replace(",", " "), "sub": f"{res['ratio_pv_load']:.1f}× la carga", "accent": ui.TECH_COLORS["Solar FV"]},
            {"label": "BESS requerido", "value": f"{res['E_bess_MWh']:,.0f} MWh".replace(",", " "), "sub": f"{res['hours_storage']:.1f} h de carga", "accent": ui.BRAND["violet"]},
            {"label": "CAPEX total", "value": f"USD {res['capex_total_musd']:,.0f} M".replace(",", " "), "accent": ui.BRAND["navy"]},
            {"label": "LCOE firme estimado", "value": f"{res['lcoe_firm']:,.0f} USD/MWh", "sub": "régimen diario periódico", "accent": ui.BRAND["teal"]},
        ])
        cap_eq = Lmw * 1000 / (A * load)
        st.markdown(f"Para entregar los mismos **{Lmw:,.0f} MW firmes** con un producto IE de disponibilidad {A:.0%} se requerirían "
                    f"≈ **{cap_eq/1000:,.0f} MW netos** instalados (antes de reserva por confiabilidad). El CAPEX equivalente que "
                    f"igualaría el CAPEX de FV+BESS sería ≈ **{res['capex_total_musd']*1e6/cap_eq:,.0f} USD/kW neto**.".replace(",", " "))
        ui.callout("info", "Referencia internacional",
                   "IRENA (2026) estima LCOE firmes de 54–82 USD/MWh (95 % de confiabilidad) en sitios de alto recurso, y cita "
                   "un complejo de 5,2 GW FV + 19 GWh de baterías para entregar 1 GW firme. El sobredimensionamiento de ~5× es "
                   "coherente con este cálculo simplificado.")
    ui.source(source_line("S10"))

with tab4:
    base = dict(capex=capex, fom=fom_pct, vom=vom, A=A, life=life, wacc=wacc)

    def f(p):
        return lcoe(p["capex"], p["fom"] / 100 * p["capex"], p["vom"], p["A"] * load, p["wacc"], int(round(p["life"])))

    l0 = f(base)
    sens = []
    for k, lab in [("capex", "CAPEX"), ("wacc", "WACC"), ("A", "Disponibilidad"), ("fom", "O&M fijo"), ("life", "Vida útil"), ("vom", "O&M variable")]:
        lo = dict(base)
        hi = dict(base)
        lo[k] = base[k] * 0.8
        hi[k] = min(base[k] * 1.2, 0.995) if k == "A" else base[k] * 1.2
        sens.append((lab, f(lo) - l0, f(hi) - l0))
    sens.sort(key=lambda s: -max(abs(s[1]), abs(s[2])))
    fig = go.Figure()
    fig.add_trace(go.Bar(y=[s[0] for s in sens], x=[s[1] for s in sens], orientation="h", name="−20 %", marker_color=ui.BRAND["teal"]))
    fig.add_trace(go.Bar(y=[s[0] for s in sens], x=[s[2] for s in sens], orientation="h", name="+20 %", marker_color=ui.BRAND["red"]))
    fig.update_layout(barmode="overlay")
    fig.update_yaxes(autorange="reversed")
    ui.style_fig(fig, height=380, title=f"Tornado: variación del LCOE IE (base {l0:,.0f} USD/MWh) ante ±20 % en cada parámetro", xaxis_title="Δ USD/MWh")
    ui.show(fig, key="tornado")
    ui.callout("eoi", "Prioridades de I+D que se desprenden",
               "El CAPEX por kW neto y la disponibilidad dominan el costo: los aliados de manufactura (diseño para fabricación) y "
               "de confiabilidad (MTBF/MTTR) tienen un impacto económico directo, comparable al del costo de capital que aportan "
               "los inversionistas.")

ui.footer()
