import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import ui
from core.data import CR_CAPACITY_2025, DISPATCH_COLS, NEW_LOADS, load_dispatch, source_line
from core.reliability import modules_needed

ui.page_header(
    "2 · El problema",
    "Costa Rica necesita potencia firme, limpia y rápida de desplegar",
    "La demanda crece más rápido que la capacidad firme. El despacho real de un día de junio de 2026 muestra el "
    "embalse de Arenal operando casi a plena potencia las 24 horas y plantas térmicas encendidas desde el mediodía.",
    [("Datos públicos ICE-DOCSE", ""), ("Reconstrucción digitalizada", "amber"), ("Escenarios editables", "mint")],
)

ui.kpis([
    {"label": "Capacidad instalada SEN 2025", "value": "3 658,6 MW", "sub": "64 % hidro · 14,5 % térmica · 12 % eólica", "accent": ui.BRAND["navy"]},
    {"label": "Demanda de energía 2025", "value": "12 995 GWh", "sub": "≈ 35,6 GWh/día", "accent": ui.BRAND["blue"]},
    {"label": "Pico histórico", "value": "2 040,9 MW", "sub": "29-jun-2026", "accent": ui.BRAND["amber"]},
    {"label": "Crecimiento T1-2026", "value": "+3,35 %", "sub": "interanual (energía)", "accent": ui.BRAND["teal"]},
    {"label": "Respaldo térmico", "value": "273 + 200 MW", "sub": "alquiler 2027–29 + Moín IV (2029)", "accent": ui.BRAND["red"]},
])
ui.source(source_line("S3", "S1", "S7", "S4", "S6"))

df = load_dispatch()
names = [n for _, n in DISPATCH_COLS]
h = df["h"].to_numpy()

tab1, tab2, tab3 = st.tabs(["📈 Despacho del 14-jun-2026", "🏭 Escenario: nuevas cargas 24/7", "🧱 Matriz instalada 2025"])

with tab1:
    c1, c2 = st.columns([3, 1.05], gap="large")
    with c1:
        pct = st.toggle("Mostrar como % de la demanda", value=False)
        fig = go.Figure()
        tot = df["demanda_total_MW"].to_numpy()
        for col, name in DISPATCH_COLS:
            y = df[col].to_numpy()
            if pct:
                y = 100 * y / tot
            fig.add_trace(go.Scatter(
                x=h, y=y, name=name, stackgroup="one", mode="lines", line=dict(width=0.6, color=ui.TECH_COLORS[name]),
                fillcolor=ui.TECH_COLORS[name], hovertemplate="%{y:.0f}" + (" %" if pct else " MW") + f"<extra>{name}</extra>"))
        if not pct:
            fig.add_trace(go.Scatter(x=h, y=tot, name="Demanda", mode="lines", line=dict(color="#0B2A5B", width=2.2, dash="dot"),
                                     hovertemplate="%{y:.0f} MW<extra>Demanda</extra>"))
            fig.add_vline(x=12.5, line=dict(color="#E5484D", width=1, dash="dash"))
            fig.add_annotation(x=12.5, y=tot.max() * 1.04, text="12:30 entran térmicas", showarrow=False,
                               font=dict(color="#E5484D", size=11), xanchor="left")
            fig.add_annotation(x=19.6, y=float(tot.max()), text="pico vespertino", showarrow=True, ay=-35,
                               font=dict(size=11))
        fig.update_xaxes(tickmode="array", tickvals=list(range(0, 25, 2)), ticktext=[f"{i}:00" for i in range(0, 25, 2)],
                         range=[0, 24])
        ui.style_fig(fig, height=470, title="Despacho del Sistema Eléctrico Nacional · domingo 14-jun-2026 (reconstruido)",
                     yaxis_title="% de la demanda" if pct else "MW", xaxis_title="hora")
        ui.show(fig, key="disp")
    with c2:
        e = {n: float(np.trapezoid(df[c], h)) if hasattr(np, "trapezoid") else float(np.trapz(df[c], h)) for c, n in DISPATCH_COLS}
        E_tot = sum(e.values())
        ui.kpis([
            {"label": "Pico del día", "value": f"{tot.max():,.0f} MW".replace(",", " "), "sub": f"a las {h[np.argmax(tot)]:.1f} h", "accent": ui.BRAND["navy"]},
            {"label": "Energía del día", "value": f"{E_tot/1000:,.1f} GWh", "sub": "≈ promedio diario 2025", "accent": ui.BRAND["blue"]},
            {"label": "Térmica", "value": f"{e['Térmica']:,.0f} MWh".replace(",", " "), "sub": f"máx. {df['termica_MW'].max():.0f} MW", "accent": ui.BRAND["red"]},
            {"label": "Arenal (media)", "value": f"{df['arenal_MW'].mean():.0f} MW", "sub": "≈ capacidad del complejo", "accent": ui.TECH_COLORS["Arenal"]},
        ])
    ui.callout("science", "Lectura técnica del despacho",
               "<ul style='margin:0;padding-left:18px'>"
               "<li><b>Base:</b> geotermia (~180 MW) constante; eólica fuerte en la mañana y débil en la tarde.</li>"
               "<li><b>Hidro de regulación diaria</b> (p. ej., embalses con ~2 h de almacenamiento) forma dos jorobas: mediodía y noche.</li>"
               "<li><b>Arenal</b> —el embalse estacional estratégico— opera cerca de su máximo las 24 h, consumiendo la reserva "
               "hídrica que debería proteger la estación seca (riesgo El Niño 2026–2027).</li>"
               "<li><b>Térmica</b> desde las 12:30 hasta medianoche (pico ~200 MW) e importaciones regionales puntuales.</li>"
               "<li>Conclusión: el sistema no tiene déficit de <i>energía</i> renovable anual, sino de <b>potencia firme</b> "
               "despachable en las horas críticas y de margen para cargas nuevas 24/7.</li></ul>")
    with st.expander("Método de reconstrucción y limitaciones"):
        st.markdown(
            "La serie se obtuvo **digitalizando por color** el gráfico DOCSE-ICE mostrado en el video [V1] (resolución 15 min). "
            "Error estimado ±15–25 MW por banda; la geotermia se fijó en su valor medio y las importaciones (puntos negros) "
            "no se incluyen. La energía diaria resultante (≈35,7 GWh) es coherente con el promedio de 2025 (35,6 GWh/día). "
            "Para estudios formales, use los datos oficiales del CENCE.")
        st.dataframe(df, width="stretch", height=240, hide_index=True)
        st.download_button("Descargar CSV reconstruido", df.to_csv(index=False).encode(), "cr_despacho_2026-06-14_reconstruido.csv",
                           mime="text/csv")
    ui.source(source_line("V1"))

with tab2:
    st.markdown("Agregue cargas industriales 24/7 y crecimiento vegetativo de la demanda sobre el perfil del 14-jun-2026. "
                "La generación renovable existente se mantiene **limitada por el recurso** del día (agua, viento, vapor); "
                "el faltante debe cubrirse con térmica, importaciones o **nueva capacidad firme**.")
    c1, c2, c3 = st.columns([1.2, 1, 1], gap="large")
    with c1:
        st.markdown("**Cargas 24/7 adicionales**")
        loads = 0.0
        for i, (name, mw) in enumerate(NEW_LOADS):
            on = st.checkbox(f"{name}", value=(i != 1), key=f"ld_on_{i}")
            val = st.number_input(f"MW · {name.split(' (')[0]}", 0, 2000, mw, step=10, key=f"ld_mw_{i}",
                                  label_visibility="collapsed", disabled=not on)
            loads += val if on else 0.0
        extra = st.number_input("Otra carga 24/7 (MW)", 0, 2000, 0, step=10)
        loads += extra
    with c2:
        st.markdown("**Crecimiento vegetativo**")
        years = st.slider("Años hacia adelante", 0, 6, 3)
        g = st.slider("Crecimiento anual de la demanda (%)", 0.0, 6.0, 3.5, 0.1)
        st.markdown("**Costos de cubrir con térmica**")
        fuel = st.slider("Costo variable térmico (USD/MWh)", 120, 400, 230, 10)
        ef = st.slider("Factor de emisión (tCO₂/MWh)", 0.50, 0.90, 0.70, 0.01)
    with c3:
        st.markdown("**Cobertura con módulos firmes (escenario IE)**")
        pm_kw = st.select_slider("Potencia neta por módulo (kW)", [50, 100, 250, 500, 1000, 2000], value=500)
        A = st.slider("Disponibilidad por módulo A", 0.80, 0.995, 0.95, 0.005)
        alpha = st.select_slider("Confiabilidad objetivo", [0.99, 0.999, 0.9999], value=0.999,
                                 format_func=lambda x: f"{x*100:.2f} %")
    D0 = df["demanda_total_MW"].to_numpy()
    renew = df[[c for c, n in DISPATCH_COLS if n != "Térmica"]].sum(axis=1).to_numpy()
    D1 = D0 * (1 + g / 100) ** years + loads
    deficit = np.maximum(D1 - renew, 0)
    dE = float(np.trapezoid(deficit, h)) if hasattr(np, "trapezoid") else float(np.trapz(deficit, h))
    peak_def = float(deficit.max())
    n_mod = modules_needed(peak_def, pm_kw / 1000, A, alpha) if peak_def > 0 else 0

    fig = go.Figure()
    for col, name in DISPATCH_COLS:
        if name == "Térmica":
            continue
        fig.add_trace(go.Scatter(x=h, y=df[col], name=name, stackgroup="r", mode="lines", line=dict(width=0.5, color=ui.TECH_COLORS[name]),
                                 fillcolor=ui.TECH_COLORS[name], hovertemplate="%{y:.0f} MW<extra>" + name + "</extra>"))
    fig.add_trace(go.Scatter(x=h, y=deficit, name="Brecha a cubrir (térmica / import. / firme nueva)", stackgroup="r", mode="lines",
                             line=dict(width=0.5, color="#E5484D"), fillcolor="rgba(229,72,77,0.55)",
                             hovertemplate="%{y:.0f} MW<extra>Brecha</extra>"))
    fig.add_trace(go.Scatter(x=h, y=D0, name="Demanda 14-jun-2026", mode="lines", line=dict(color="#64748B", width=1.6, dash="dot")))
    fig.add_trace(go.Scatter(x=h, y=D1, name="Demanda escenario", mode="lines", line=dict(color="#0B2A5B", width=2.6)))
    fig.update_xaxes(tickvals=list(range(0, 25, 2)), ticktext=[f"{i}:00" for i in range(0, 25, 2)], range=[0, 24])
    ui.style_fig(fig, height=470, title="Brecha de potencia firme bajo el escenario seleccionado", yaxis_title="MW", xaxis_title="hora")
    ui.show(fig, key="scen")
    ui.kpis([
        {"label": "Brecha pico", "value": f"{peak_def:,.0f} MW".replace(",", " "), "sub": f"cargas nuevas: {loads:,.0f} MW".replace(",", " "), "accent": ui.BRAND["red"]},
        {"label": "Energía de brecha", "value": f"{dE:,.0f} MWh/día".replace(",", " "), "sub": f"≈ {dE*365/1000:,.0f} GWh/año".replace(",", " "), "accent": ui.BRAND["amber"]},
        {"label": "Costo si es térmica", "value": f"USD {dE*365*fuel/1e6:,.0f} M/año".replace(",", " "), "sub": f"a {fuel} USD/MWh (solo variable)", "accent": ui.BRAND["navy"]},
        {"label": "Emisiones si es térmica", "value": f"{dE*365*ef/1e3:,.0f} kt CO₂/año".replace(",", " "), "sub": f"FE = {ef:.2f} t/MWh", "accent": ui.BRAND["gray"]},
        {"label": "Módulos firmes requeridos", "value": (f"{n_mod:,}".replace(",", " ") if n_mod >= 0 else "—"),
         "sub": f"{pm_kw} kW c/u · A={A:.3f} · {alpha*100:.2f} % · {n_mod*pm_kw/1000:,.0f} MW instalados".replace(",", " "), "accent": ui.BRAND["teal"]},
    ])
    ui.callout("eoi", "Implicación para Infinity Energy",
               "El mercado direccionable inmediato no es la energía barata de mediodía, sino la <b>potencia firme</b> en las "
               "horas críticas y para cargas 24/7 (industria, centros de datos, hidrógeno verde). Hoy esa necesidad se cubre "
               "con térmica de alquiler (≈ USD 469/kW-año sin combustible, implícito del contrato 2027–2029). Una tecnología "
               "firme, modular y renovable —<i>si se valida</i>— competiría contra ese costo evitado, además de emisiones y "
               "exposición al precio del combustible.")

with tab3:
    cap = pd.DataFrame({"Fuente": list(CR_CAPACITY_2025), "MW": list(CR_CAPACITY_2025.values())})
    cap["%"] = 100 * cap["MW"] / cap["MW"].sum()
    colors = {"Hidroeléctrica": "#3A49E0", "Termoeléctrica": "#E5484D", "Eólica": "#B8C4D6", "Geotérmica": "#F2C200",
              "Bagazo": "#8B5E3C", "Solar": "#F59E0B"}
    c1, c2 = st.columns([1.1, 1])
    with c1:
        fig = go.Figure(go.Pie(labels=cap["Fuente"], values=cap["MW"], hole=0.55, sort=False,
                               marker=dict(colors=[colors[f] for f in cap["Fuente"]], line=dict(color="white", width=2)),
                               textinfo="label+percent"))
        fig.add_annotation(text="3 658,6 MW<br><span style='font-size:11px'>2025</span>", showarrow=False, font=dict(size=16, color="#0B2A5B"))
        ui.style_fig(fig, height=400, title="Capacidad instalada del SEN por fuente (2025)")
        fig.update_layout(showlegend=False)
        ui.show(fig, key="pie")
    with c2:
        st.dataframe(ui.sfmt(cap, {"MW": "{:,.1f}", "%": "{:.1f}"}), width="stretch", hide_index=True)
        ui.callout("science", "Firmeza ≠ capacidad instalada",
                   "La hidroelectricidad es firme solo mientras haya agua embalsada; la eólica y la solar aportan energía "
                   "pero poca capacidad garantizada en el pico vespertino; la geotermia es firme pero de desarrollo lento "
                   "(Borinquen I, 55 MW, ~2030). De ahí la dependencia de térmica de respaldo.")
    ui.source(source_line("S3"))

ui.footer()
