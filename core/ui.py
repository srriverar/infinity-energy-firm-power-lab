"""
core/ui.py — Identidad visual, componentes HTML y plantilla de gráficos.
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

BRAND = {
    "blue": "#0098D4",
    "blue_dark": "#0A5FA8",
    "mint": "#2FD4B0",
    "teal": "#0FA99A",
    "navy": "#0B2A5B",
    "ink": "#0F172A",
    "muted": "#5B6B80",
    "soft": "#F2F7FB",
    "amber": "#F59E0B",
    "red": "#E5484D",
    "green": "#16A34A",
    "violet": "#7C3AED",
    "gray": "#94A3B8",
}

TECH_COLORS = {
    "Geotermia": "#F2C200",
    "Eólica": "#B8C4D6",
    "Hidro regulación diaria": "#1E1B8F",
    "Hidro filo de agua": "#3A49E0",
    "Embalses estacionales ICE": "#5B9BF0",
    "Arenal": "#8FD3F7",
    "Térmica": "#E5484D",
    "Solar FV": "#F59E0B",
    "PCH filo de agua": "#3A49E0",
    "VE / carga controlable": "#7C3AED",
    "IE (escenario)": "#0FA99A",
    "Planta modular firme (IE, escenario)": "#0FA99A",
    "Uniforme (simplificada)": "#94A3B8",
    "Nuevas cargas 24/7": "#111827",
}

_NUM = re.compile(r"(?<![\w.,/#])([1-9]\d{0,2}(?:,\d{3})+|\d+)(\.\d+)?(?![\w])")


def es_num(s) -> str:
    """Convierte números con formato inglés (1,234.5) a formato español (1 234,5) dentro de un texto."""
    if not isinstance(s, str):
        return s

    def rep(m):
        ip, dp = m.group(1), m.group(2)
        ip = ip.replace(",", "\u202f")
        return ip + ("," + dp[1:] if dp else "")

    return _NUM.sub(rep, s)


def sfmt(df, fmt=None):
    """Styler con formato numérico español."""
    return df.style.format(fmt, decimal=",", thousands="\u202f", na_rep="—")


COLORWAY = ["#0098D4", "#0FA99A", "#0B2A5B", "#F59E0B", "#E5484D", "#7C3AED", "#64748B", "#16A34A"]


def _register_template():
    if "ie" in pio.templates:
        return
    pio.templates["ie"] = go.layout.Template(
        layout=dict(
            font=dict(family="Inter, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif", size=13, color=BRAND["ink"]),
            colorway=COLORWAY,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="white",
            title=dict(font=dict(size=15, color=BRAND["navy"]), x=0.0, xanchor="left"),
            xaxis=dict(gridcolor="#E9EEF5", zerolinecolor="#CBD5E1", linecolor="#CBD5E1", ticks="outside",
                       tickcolor="#CBD5E1", title=dict(font=dict(size=12, color=BRAND["muted"]))),
            yaxis=dict(gridcolor="#E9EEF5", zerolinecolor="#CBD5E1", linecolor="#CBD5E1",
                       title=dict(font=dict(size=12, color=BRAND["muted"]))),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=12)),
            margin=dict(l=60, r=20, t=40, b=50),
            hoverlabel=dict(font_size=12, bgcolor="white"),
            separators=", ",
        )
    )
    pio.templates.default = "plotly_white+ie"


_register_template()


def img_b64(name: str) -> str:
    p = ASSETS / name
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


CSS = """
<style>
:root{--ie-blue:#0098D4;--ie-mint:#2FD4B0;--ie-navy:#0B2A5B;--ie-ink:#0F172A;--ie-muted:#5B6B80;--ie-soft:#F2F7FB;}
.block-container{padding-top:1.4rem;padding-bottom:2rem;max-width:1320px;}
h1,h2,h3{color:var(--ie-navy);}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#F7FBFE 0%,#EEF6FB 100%);border-right:1px solid #E3EAF2;}
.ie-hero{background:linear-gradient(118deg,#0B2A5B 0%,#0A4F8F 42%,#0098D4 74%,#2FD4B0 100%);color:#fff;border-radius:22px;
  padding:30px 34px;position:relative;overflow:hidden;box-shadow:0 10px 30px rgba(11,42,91,.18);}
.ie-hero:after{content:"";position:absolute;right:-60px;top:-60px;width:260px;height:260px;border-radius:50%;
  background:radial-gradient(circle,rgba(255,255,255,.22),rgba(255,255,255,0) 70%);}
.ie-hero h1{color:#fff;font-size:2.15rem;line-height:1.15;margin:.2rem 0 .5rem 0;font-weight:800;}
.ie-hero p{color:#E3F3FF;font-size:1.04rem;margin:0;max-width:880px;}
.ie-kicker{text-transform:uppercase;letter-spacing:.16em;font-size:.74rem;font-weight:800;color:#A7F3E4;}
.ie-chip{display:inline-block;padding:4px 11px;border-radius:999px;font-size:.76rem;font-weight:650;margin:10px 6px 0 0;
  background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.38);color:#fff;}
.ie-header{border-left:6px solid var(--ie-blue);padding:4px 0 4px 16px;margin:0 0 14px 0;}
.ie-header .k{color:var(--ie-blue);text-transform:uppercase;letter-spacing:.14em;font-size:.72rem;font-weight:800;}
.ie-header h1{font-size:1.85rem;margin:.1rem 0 .2rem 0;color:var(--ie-navy);font-weight:800;line-height:1.2;}
.ie-header p{color:var(--ie-muted);margin:0;font-size:1rem;max-width:980px;}
.ie-tag{display:inline-block;padding:2px 9px;border-radius:999px;font-size:.72rem;font-weight:700;margin:6px 6px 0 0;
  background:#E8F6FD;color:#0A5FA8;border:1px solid #CBE9F8;}
.ie-tag.mint{background:#E7FAF5;color:#08796C;border-color:#BDEFE3;}
.ie-tag.amber{background:#FFF6E5;color:#9A5B00;border-color:#F8DDAA;}
.ie-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(185px,1fr));gap:12px;margin:6px 0 10px 0;}
.ie-kpi{background:#fff;border:1px solid #E3EAF2;border-radius:14px;padding:13px 15px;box-shadow:0 1px 2px rgba(15,23,42,.04);
  border-top:4px solid var(--accent,#0098D4);}
.ie-kpi .label{font-size:.72rem;color:#5B6B80;text-transform:uppercase;letter-spacing:.06em;font-weight:700;}
.ie-kpi .value{font-size:1.5rem;font-weight:800;color:#0B2A5B;line-height:1.15;margin-top:3px;}
.ie-kpi .sub{font-size:.78rem;color:#6B7A90;margin-top:3px;line-height:1.3;}
.ie-callout{border-radius:12px;padding:13px 16px;margin:10px 0;border:1px solid;font-size:.95rem;line-height:1.5;}
.ie-callout .t{font-weight:800;color:#0B2A5B;margin-bottom:3px;font-size:.95rem;}
.ie-callout.science{background:#F0F7FF;border-color:#C5E0F7;}
.ie-callout.warning{background:#FFF8EB;border-color:#F3D7A6;}
.ie-callout.success{background:#ECFDF5;border-color:#A7F3D0;}
.ie-callout.info{background:#F5F7FA;border-color:#DCE3EC;}
.ie-callout.eoi{background:linear-gradient(90deg,#E9FBF6,#EAF6FF);border-color:#9DE3D2;}
.ie-card{background:#fff;border:1px solid #E3EAF2;border-radius:16px;padding:16px 18px;height:100%;
  box-shadow:0 1px 2px rgba(15,23,42,.04);}
.ie-card h4{margin:0 0 6px 0;color:#0B2A5B;font-size:1.02rem;}
.ie-card p,.ie-card li{color:#334155;font-size:.9rem;line-height:1.45;}
.ie-card .num{font-size:.72rem;font-weight:800;color:#0098D4;letter-spacing:.12em;text-transform:uppercase;}
.ie-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin:8px 0;}
.ie-footer{color:#6B7A90;font-size:.76rem;border-top:1px solid #E3EAF2;margin-top:34px;padding-top:12px;line-height:1.5;}
.ie-src{color:#6B7A90;font-size:.76rem;}
.ie-chart-title{font-weight:800;color:#0B2A5B;font-size:1rem;margin:10px 0 -4px 2px;}
.ie-eq{background:#FBFDFF;border:1px dashed #C5D6E8;border-radius:12px;padding:6px 10px;}
div[data-testid="stMetricValue"]{color:#0B2A5B;font-weight:800;}
.ie-step{display:flex;gap:12px;align-items:flex-start;margin:8px 0;}
.ie-step .n{flex:0 0 30px;height:30px;border-radius:50%;background:linear-gradient(135deg,#0098D4,#2FD4B0);color:#fff;
  font-weight:800;display:flex;align-items:center;justify-content:center;font-size:.85rem;}
.ie-step .b{flex:1;font-size:.92rem;color:#334155;}
.ie-step .b b{color:#0B2A5B;}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(kicker: str, title: str, subtitle: str = "", tags: list[tuple[str, str]] | None = None):
    tags_html = ""
    if tags:
        tags_html = "".join(f'<span class="ie-tag {cls}">{txt}</span>' for txt, cls in tags)
    st.markdown(
        f'<div class="ie-header"><div class="k">{kicker}</div><h1>{title}</h1><p>{subtitle}</p>{tags_html}</div>',
        unsafe_allow_html=True,
    )


def kpis(items: list[dict]):
    html = '<div class="ie-kpis">'
    for it in items:
        acc = it.get("accent", BRAND["blue"])
        sub = f'<div class="sub">{es_num(it["sub"])}</div>' if it.get("sub") else ""
        html += (f'<div class="ie-kpi" style="--accent:{acc}"><div class="label">{it["label"]}</div>'
                 f'<div class="value">{es_num(it["value"])}</div>{sub}</div>')
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def callout(kind: str, title: str, body_html: str):
    st.markdown(f'<div class="ie-callout {kind}"><div class="t">{es_num(title)}</div>{es_num(body_html)}</div>',
                unsafe_allow_html=True)


def cards(items: list[dict], min_width: int = 240):
    html = f'<div class="ie-grid" style="grid-template-columns:repeat(auto-fit,minmax({min_width}px,1fr));">'
    for it in items:
        num = f'<div class="num">{it["num"]}</div>' if it.get("num") else ""
        html += f'<div class="ie-card">{num}<h4>{it["title"]}</h4>{it["body"]}</div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def steps(items: list[tuple[str, str]]):
    html = ""
    for i, (t, b) in enumerate(items, 1):
        html += f'<div class="ie-step"><div class="n">{i}</div><div class="b"><b>{t}</b><br>{es_num(b)}</div></div>'
    st.markdown(html, unsafe_allow_html=True)


def source(text: str):
    st.markdown(f'<div class="ie-src">{text}</div>', unsafe_allow_html=True)


def style_fig(fig: go.Figure, height: int = 420, title: str | None = None, legend_top: bool = True,
              yaxis_title: str | None = None, xaxis_title: str | None = None) -> go.Figure:
    """Aplica la plantilla. El título se dibuja fuera del gráfico (evita solaparse con la leyenda)."""
    fig.update_layout(template="plotly_white+ie", height=height, separators=", ")
    if title is not None:
        meta = dict(fig.layout.meta) if isinstance(fig.layout.meta, dict) else {}
        meta["ie_title"] = title
        fig.update_layout(meta=meta, title=None)
    grid = getattr(fig, "_grid_ref", None)
    multi = grid is not None and (len(grid) * len(grid[0]) > 1)
    if multi:  # subplots: leyenda abajo para no tapar los títulos de cada panel
        fig.update_layout(legend=dict(orientation="h", yref="container", y=0.0, yanchor="bottom", x=0, xanchor="left"),
                          margin=dict(b=95))
    if not legend_top:
        fig.update_layout(legend=dict(orientation="v", y=1, x=1.02, yanchor="top", xanchor="left"))
    if yaxis_title is not None:
        fig.update_yaxes(title_text=yaxis_title)
    if xaxis_title is not None:
        fig.update_xaxes(title_text=xaxis_title)
    return fig


def show(fig: go.Figure, key: str | None = None):
    meta = fig.layout.meta if isinstance(fig.layout.meta, dict) else {}
    t = meta.get("ie_title") if meta else None
    if t:
        st.markdown(f'<div class="ie-chart-title">{es_num(t)}</div>', unsafe_allow_html=True)
    st.plotly_chart(fig, theme=None, key=key, config={"displaylogo": False, "responsive": True})


def footer():
    st.markdown(
        '<div class="ie-footer"><b>Aviso científico.</b> Demo con fines de divulgación técnica y evaluación para la '
        'Convocatoria de Expresiones de Interés de Infinity Energy. Los parámetros del módulo Infinity Energy son '
        '<b>supuestos de escenario</b>, no mediciones validadas. El resultado del POC es <b>reportado por la empresa</b> '
        'y no constituye una validación independiente ni una certificación de desempeño. Las solicitudes de patente '
        '(CR 2024-0000354 · PCT/CR2025/050003 · IN 202617045117) no equivalen a patentes concedidas. '
        'El esquema físico es genérico y no representa el diseño patentado. © Infinity Energy · '
        '<a href="https://www.infinityen.energy" target="_blank">infinityen.energy</a> · info@infinityen.energy</div>',
        unsafe_allow_html=True,
    )


def fmt(x: float, nd: int = 1, unit: str = "") -> str:
    try:
        s = f"{x:,.{nd}f}".replace(",", "\u202f")
    except (TypeError, ValueError):
        s = str(x)
    return f"{s} {unit}".strip()


def fmt_power(w: float) -> str:
    a = abs(w)
    if a >= 1e6:
        return f"{w/1e6:,.2f} MW"
    if a >= 1e3:
        return f"{w/1e3:,.2f} kW"
    return f"{w:,.0f} W"
