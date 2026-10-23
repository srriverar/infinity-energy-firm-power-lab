"""
core/anim_physics.py — Animaciones de la página «Física y balance energético».

1. `pv_cycle_animation_html`: una inserción recorrida en sincronía sobre la columna
   de agua y el diagrama p–V. Las áreas ∫V dp (trabajo técnico) de la compresión
   y de la flotación se llenan en vivo y se contrastan con la contabilidad
   eléctrica por inserción.
2. `energy_flow_animation_html`: flujo de potencia en régimen como un Sankey
   animado. Cada partícula transporta la misma potencia y se desvía en cada etapa
   con probabilidad = pérdida / potencia que llega (balance exacto en promedio).

Todas las magnitudes provienen de `core.physics.cycle` (modelo genérico de primeros
principios; no representa el diseño patentado de Infinity Energy).
"""
from __future__ import annotations

import math

from .anim import render
from .physics import GAMMA, CycleParams, CycleResult


# -----------------------------------------------------------------------------
# Parámetros (Python) — separados de la plantilla para poder probarlos
# -----------------------------------------------------------------------------
def compression_exponent(p: CycleParams) -> float:
    if p.compression == "isotérmica":
        return 1.0
    if p.compression == "adiabática":
        return GAMMA
    return max(1.0001, p.n_poly)


def pv_cycle_params(p: CycleParams, r: CycleResult) -> dict:
    """Estados del ciclo ideal (unidades: kPa, L, K, J; 1 kPa·L = 1 J)."""
    k = compression_exponent(p)
    Tw, Ta = p.T_w_C + 273.15, p.T_a_C + 273.15
    p0, pH = r.p0 / 1000.0, r.pH / 1000.0
    V0 = p.V0_L
    return {
        "H": p.H, "V0": V0, "p0": p0, "pH": pH, "rho": r.rho, "Tw": Tw, "Ta": Ta, "k": k,
        "mode": p.compression,
        "V2": V0 * (p0 / pH) ** (1.0 / k),             # fin de la compresión ideal
        "V3": V0 * (p0 / pH) * (Tw / Ta),              # equilibrio térmico con el agua a p_H
        "V4": V0 * (Tw / Ta),                          # llegada a la superficie (isoterma T_w)
        "T2": Ta * (pH / p0) ** ((k - 1.0) / k),       # descarga del proceso ideal
        "Wci": r.W_comp_ideal, "Wiso": r.W_iso_ref, "Wb": r.W_buoy, "Wc": r.W_comp,
        "Eins": r.E_ins, "Wout": r.W_out, "Eaux": r.P_aux / max(p.f_ins, 1e-9),
        "ERR": r.ERR, "ERRi": r.ERR_ideal_cycle, "f": p.f_ins,
    }


def energy_flow_params(p: CycleParams, r: CycleResult) -> dict:
    f = p.f_ins
    return {
        "Pin": r.P_in, "Pabis": r.P_abis, "Paux": r.P_aux,
        "Wc": f * r.W_comp, "Wiso": f * r.W_iso_ref, "Wb": f * r.W_buoy,
        "gain": f * max(0.0, r.W_buoy - r.W_iso_ref), "deficit": f * max(0.0, r.W_iso_ref - r.W_buoy),
        "Wmech": f * r.W_mech, "Wshaft": f * r.W_shaft, "Wgen": f * r.W_gen, "Wout": f * r.W_out,
        "eta_m": p.eta_motor, "eta_c": r.W_iso_ref / r.W_comp if r.W_comp > 0 else float("nan"),
        "eta_cap": p.eta_cap, "eta_t": p.eta_gear, "eta_g": p.eta_gen, "eta_pe": p.eta_pe,
        "ERR": r.ERR, "Pnet": r.P_net, "f": f,
    }


def area_check(params: dict, n: int = 4000) -> tuple[float, float]:
    """Integra numéricamente ∫V dp sobre las curvas dibujadas (para pruebas)."""
    p0, pH, V0, V3, k = params["p0"], params["pH"], params["V0"], params["V3"], params["k"]
    h = (pH - p0) / n
    wc = wa = 0.0
    for i in range(n):
        pm = p0 + (i + 0.5) * h
        wc += V0 * (p0 / pm) ** (1.0 / k) * h
        wa += V3 * pH / pm * h
    return wc, wa


# -----------------------------------------------------------------------------
# 1. Ciclo p–V sincronizado con la columna
# -----------------------------------------------------------------------------
_PV_TEMPLATE = r"""
<div style="width:100%;font-family:Inter,Segoe UI,Roboto,Arial,sans-serif;">
<canvas id="__CID__" title="Clic para pausar o continuar" style="width:100%;max-width:1100px;height:auto;aspect-ratio:1100/580;display:block;margin:0 auto;border-radius:16px;background:#F7FBFE;border:1px solid #E3EAF2;cursor:pointer"></canvas>
</div>
<script>
(function(){
const P = __PARAMS__;
__JSLIB__
function run(cv){
const W = 1100, H = 580;
const ctx = setupCanvas(cv, W, H);
let paused = false;
cv.addEventListener('click', function(){ paused = !paused; });
const C = {amber:'#F59E0B', amberD:'#B45309', teal:'#0FA99A', navy:'#0B2A5B', red:'#E5484D', green:'#16A34A', violet:'#7C3AED', muted:'#5B6B80', orange:'#EA580C', grid:'#E3EAF2'};
const COL = {x0:205, x1:325, yTop:98, ySurf:126, yBot:480};
const CYL = {x:38, y:132, w:88, h:126};
const PIPE = [[82,258],[82,508],[265,508],[265,481]];
const PV = {x0:505, x1:790, y0:110, y1:444};
const LED = {x:826, w:254};
const V0 = P.V0, V2 = P.V2, V3 = P.V3, V4 = P.V4, p0 = P.p0, pH = P.pH, k = P.k;
const dp = pH - p0;
const Vmax = Math.max(V0, V2, V3, V4)*1.12;
const pLo = p0 - 0.10*dp, pHi = pH + 0.12*dp;
const isoK = Math.abs(k - 1) < 1e-6;
function X(v){ return PV.x0 + (PV.x1 - PV.x0)*v/Vmax; }
function Y(p){ return PV.y1 - (PV.y1 - PV.y0)*(p - pLo)/(pHi - pLo); }
function Vc(p){ return V0*Math.pow(p0/p, 1/k); }
function Va(p){ return V3*pH/p; }
function Wcomp(p){ return isoK ? p0*V0*Math.log(p/p0) : k/(k - 1)*p0*V0*(Math.pow(p/p0, (k - 1)/k) - 1); }
function Wasc(p){ return pH*V3*Math.log(pH/p); }
function Tcomp(p){ return P.Ta*Math.pow(p/p0, (k - 1)/k); }
function zOf(p){ return P.H*(p - p0)/dp; }
const hatchA = hatchPattern(ctx, 'rgba(217,119,6,0.75)', null);
const PH = [0.9, 2.4, 1.3, 3.4, 1.3, 2.4];
const TC = PH.reduce(function(a, b){ return a + b; }, 0);
const NAMES = ['Admisión (estado 1)', '① Compresión ' + P.mode + ' (1→2)', '② Inyección a profundidad (2→3)', '③ Ascenso con expansión (3→4)', '④ Liberación a p₀ (4→1)', 'Balance de áreas'];
let t = 0, last = performance.now(), tg = 0;
let ripples = [];
function phaseAt(tt){ let a = 0; for (let i = 0; i < PH.length; i++){ if (tt < a + PH[i]) return [i, (tt - a)/PH[i]]; a += PH[i]; } return [PH.length - 1, 1]; }
function gasColor(T){
  const hot = clamp((T - P.Tw)/Math.max(35, P.T2 - P.Tw), 0, 1), cold = clamp((P.Tw - T)/35, 0, 1);
  const a = [226, 244, 255], m = hot > 0 ? [251, 146, 60] : [125, 180, 250], f = hot > 0 ? hot : cold;
  return 'rgb(' + Math.round(lerp(a[0], m[0], f)) + ',' + Math.round(lerp(a[1], m[1], f)) + ',' + Math.round(lerp(a[2], m[2], f)) + ')';
}
function pipePoint(u){
  let L = 0; const seg = [];
  for (let i = 1; i < PIPE.length; i++){ const d = Math.hypot(PIPE[i][0] - PIPE[i-1][0], PIPE[i][1] - PIPE[i-1][1]); seg.push(d); L += d; }
  let s = u*L;
  for (let i = 0; i < seg.length; i++){ if (s <= seg[i]){ const f = s/seg[i]; return [lerp(PIPE[i][0], PIPE[i+1][0], f), lerp(PIPE[i][1], PIPE[i+1][1], f)]; } s -= seg[i]; }
  return PIPE[PIPE.length - 1];
}
function drawColumn(){
  ctx.fillStyle = 'rgba(255,255,255,0.75)'; ctx.fillRect(COL.x0, COL.yTop, COL.x1 - COL.x0, COL.ySurf - COL.yTop);
  const g = ctx.createLinearGradient(0, COL.ySurf, 0, COL.yBot);
  g.addColorStop(0, '#C9EEFF'); g.addColorStop(0.5, '#5DB8EC'); g.addColorStop(1, '#0A4F8F');
  ctx.fillStyle = g; ctx.fillRect(COL.x0, COL.ySurf, COL.x1 - COL.x0, COL.yBot - COL.ySurf);
  ctx.strokeStyle = 'rgba(255,255,255,0.95)'; ctx.lineWidth = 2; ctx.beginPath();
  for (let x = COL.x0; x <= COL.x1; x += 4){ const y = COL.ySurf + 1.8*Math.sin((x + tg*50)/16); if (x === COL.x0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
  ctx.stroke();
  ctx.strokeStyle = '#7A8797'; ctx.lineWidth = 5; rrect(ctx, COL.x0 - 3, COL.yTop - 3, COL.x1 - COL.x0 + 6, COL.yBot - COL.yTop + 6, 8); ctx.stroke();
  txt(ctx, 'Columna de agua · H = ' + esn(P.H, 1) + ' m', (COL.x0 + COL.x1)/2, COL.yTop - 18, {a:'center', s:11.5, w:'800'});
  ctx.strokeStyle = '#94A3B8'; ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++){
    const y = COL.ySurf + (COL.yBot - COL.ySurf)*i/4;
    ctx.beginPath(); ctx.moveTo(COL.x1 + 5, y); ctx.lineTo(COL.x1 + 13, y); ctx.stroke();
    txt(ctx, esn(P.H*i/4, 1) + ' m', COL.x1 + 17, y - 6, {s:10, w:'600', c:C.muted});
    txt(ctx, esn(p0 + dp*i/4, 0) + ' kPa', COL.x1 + 17, y + 7, {s:10, w:'600', c:'#0A5FA8'});
  }
}
function drawPipe(){
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  ctx.strokeStyle = '#94A3B8'; ctx.lineWidth = 8; ctx.beginPath(); ctx.moveTo(PIPE[0][0], PIPE[0][1]);
  for (let i = 1; i < PIPE.length; i++) ctx.lineTo(PIPE[i][0], PIPE[i][1]); ctx.stroke();
  ctx.strokeStyle = '#E2E8F0'; ctx.lineWidth = 3.5; ctx.stroke();
  ctx.lineCap = 'butt'; ctx.lineJoin = 'miter';
  ctx.fillStyle = '#475569'; ctx.beginPath(); ctx.arc(PIPE[3][0], PIPE[3][1] + 2, 5, 0, 2*Math.PI); ctx.fill();
}
function drawCylinder(Vg, col){
  txt(ctx, 'ABIS · compresor', CYL.x + CYL.w/2, CYL.y - 22, {a:'center', s:11.5, w:'800'});
  ctx.fillStyle = '#F8FAFC'; ctx.strokeStyle = '#64748B'; ctx.lineWidth = 2; rrect(ctx, CYL.x, CYL.y, CYL.w, CYL.h, 7); ctx.fill(); ctx.stroke();
  const ix = CYL.x + 6, iy = CYL.y + 6, iw = CYL.w - 12, ih = CYL.h - 12;
  const hg = (ih - 14)*clamp(Vg/V0, 0, 1);
  const yg = iy + ih - hg;
  ctx.fillStyle = col; ctx.fillRect(ix, yg, iw, hg);
  ctx.fillStyle = '#475569'; ctx.fillRect(ix - 1, yg - 10, iw + 2, 10);
  ctx.fillStyle = '#64748B'; ctx.fillRect(CYL.x + CYL.w/2 - 3, CYL.y - 8, 6, Math.max(0, yg - 10 - CYL.y + 8));
  if (hg > 16) txt(ctx, esn(Vg, 1) + ' L', ix + iw/2, yg + hg/2, {a:'center', s:10.5, w:'800', c:'#0B2A5B'});
}
function drawBubble(x, y, V, col, arrow){
  const r = 6 + 17*Math.cbrt(V/Vmax);
  ctx.fillStyle = col; ctx.strokeStyle = 'rgba(255,255,255,0.95)'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.ellipse(x, y, r*1.12, r*0.92, 0, 0, 2*Math.PI); ctx.fill(); ctx.stroke();
  ctx.fillStyle = 'rgba(255,255,255,0.75)'; ctx.beginPath(); ctx.arc(x - r*0.35, y - r*0.3, r*0.22, 0, 2*Math.PI); ctx.fill();
  if (arrow){
    const L = 12 + 44*V/Vmax, y0 = y - r - 3, y1 = Math.max(y0 - L, COL.yTop + 6);
    if (y0 - y1 < 10) return;
    ctx.strokeStyle = C.navy; ctx.fillStyle = C.navy; ctx.lineWidth = 2.5;
    ctx.beginPath(); ctx.moveTo(x, y0); ctx.lineTo(x, y1 + 6); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x, y1); ctx.lineTo(x - 6, y1 + 9); ctx.lineTo(x + 6, y1 + 9); ctx.closePath(); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.85)'; rrect(ctx, x + 6, y1, 26, 15, 5); ctx.fill();
    txt(ctx, 'F_b', x + 19, y1 + 7.5, {a:'center', s:10.5, w:'800', c:C.navy});
  }
}
function curve(fn, pa, pb, n){ ctx.beginPath(); for (let i = 0; i <= n; i++){ const p = lerp(pa, pb, i/n), x = X(fn(p)), y = Y(p); if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); } }
function areaComp(pTo){ ctx.beginPath(); ctx.moveTo(X(0), Y(p0)); for (let i = 0; i <= 48; i++){ const p = lerp(p0, pTo, i/48); ctx.lineTo(X(Vc(p)), Y(p)); } ctx.lineTo(X(0), Y(pTo)); ctx.closePath(); }
function areaAsc(pTo){ ctx.beginPath(); ctx.moveTo(X(0), Y(pH)); for (let i = 0; i <= 48; i++){ const p = lerp(pH, pTo, i/48); ctx.lineTo(X(Va(p)), Y(p)); } ctx.lineTo(X(0), Y(pTo)); ctx.closePath(); }
function niceStep(x){ const e = Math.pow(10, Math.floor(Math.log10(x))), m = x/e; return (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10)*e; }
function stateDot(v, p, lab, dx, dy){
  ctx.fillStyle = '#FFFFFF'; ctx.strokeStyle = C.navy; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.arc(X(v), Y(p), 3.5, 0, 2*Math.PI); ctx.fill(); ctx.stroke();
  txt(ctx, lab, X(v) + dx, Y(p) + dy, {a:'center', s:11, w:'800', c:C.navy});
}
function drawPV(i, cF, aF, pc, pa, mv, mp){
  ctx.fillStyle = '#FFFFFF'; ctx.strokeStyle = C.grid; ctx.lineWidth = 1; rrect(ctx, PV.x0 - 8, PV.y0 - 10, PV.x1 - PV.x0 + 22, PV.y1 - PV.y0 + 18, 8); ctx.fill(); ctx.stroke();
  const st = niceStep(Vmax/5);
  ctx.strokeStyle = '#EEF2F7'; ctx.lineWidth = 1;
  for (let v = st; v < Vmax; v += st){ ctx.beginPath(); ctx.moveTo(X(v), PV.y0); ctx.lineTo(X(v), PV.y1); ctx.stroke(); }
  for (let v = 0; v < Vmax; v += st) txt(ctx, esn(v, 0), X(v), PV.y1 + 16, {a:'center', s:10, w:'600', c:C.muted});
  txt(ctx, 'V (L)', PV.x1 + 12, PV.y1 + 32, {a:'right', s:10.5, w:'700', c:C.muted});
  txt(ctx, 'p (kPa)', PV.x0 - 12, PV.y0 + 4, {a:'right', s:10.5, w:'700', c:C.muted});
  [[p0, 'p₀ = ' + esn(p0, 1)], [pH, 'p_H = ' + esn(pH, 1)]].forEach(function(q){
    ctx.save(); ctx.setLineDash([4, 4]); ctx.strokeStyle = '#CBD5E1'; ctx.beginPath(); ctx.moveTo(PV.x0, Y(q[0])); ctx.lineTo(PV.x1 + 10, Y(q[0])); ctx.stroke(); ctx.restore();
    txt(ctx, q[1], PV.x0 - 12, Y(q[0]), {a:'right', s:10.5, w:'700', c:'#0A5FA8'});
  });
  if (aF > 0){ areaAsc(pa); ctx.fillStyle = 'rgba(15,169,154,0.30)'; ctx.fill(); }
  if (cF > 0){ areaComp(pc); ctx.fillStyle = 'rgba(245,158,11,0.10)'; ctx.fill(); if (hatchA){ ctx.fillStyle = hatchA; ctx.fill(); } }
  ctx.save(); ctx.setLineDash([5, 5]); ctx.lineWidth = 1.6;
  ctx.strokeStyle = 'rgba(217,119,6,0.45)'; curve(Vc, p0, pH, 60); ctx.stroke();
  ctx.strokeStyle = 'rgba(15,169,154,0.55)'; curve(Va, pH, p0, 60); ctx.stroke();
  ctx.strokeStyle = 'rgba(100,116,139,0.6)'; ctx.beginPath(); ctx.moveTo(X(V4), Y(p0)); ctx.lineTo(X(V0), Y(p0)); ctx.stroke();
  ctx.restore();
  ctx.lineWidth = 3;
  if (cF > 0){ ctx.strokeStyle = C.amberD; curve(Vc, p0, pc, 60); ctx.stroke(); }
  if (i >= 2){ const s23 = i === 2 ? mv : V3; ctx.strokeStyle = C.orange; ctx.beginPath(); ctx.moveTo(X(V2), Y(pH)); ctx.lineTo(X(s23), Y(pH)); ctx.stroke(); }
  if (aF > 0){ ctx.strokeStyle = C.teal; curve(Va, pH, pa, 60); ctx.stroke(); }
  const same23 = Math.abs(V2 - V3) <= 0.002*V2, same41 = Math.abs(V4 - V0) <= 0.002*V0;
  const s23 = V3 >= V2 ? 1 : -1, s41 = V4 >= V0 ? 1 : -1;
  if (same41) stateDot(V0, p0, '1 ≡ 4', 4, 16); else { stateDot(V0, p0, '1', -s41*10, 16); stateDot(V4, p0, '4', s41*10, 16); }
  if (same23) stateDot(V2, pH, '2 ≡ 3', 4, -16); else { stateDot(V2, pH, '2', -s23*10, -15); stateDot(V3, pH, '3', s23*10, -15); }
  ctx.fillStyle = C.navy; ctx.strokeStyle = '#FFFFFF'; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.arc(X(mv), Y(mp), 6.5, 0, 2*Math.PI); ctx.fill(); ctx.stroke();
  const wcNow = cF > 0 ? Wcomp(pc) : 0, waNow = aF > 0 ? Wasc(pa) : 0;
  const ly = PV.y1 + 50;
  ctx.fillStyle = 'rgba(245,158,11,0.12)'; ctx.fillRect(PV.x0, ly - 7, 16, 14); if (hatchA){ ctx.fillStyle = hatchA; ctx.fillRect(PV.x0, ly - 7, 16, 14); }
  ctx.strokeStyle = C.amberD; ctx.lineWidth = 1; ctx.strokeRect(PV.x0, ly - 7, 16, 14);
  txt(ctx, 'Compresión ideal ∫V dp = ' + esn(wcNow, 0) + ' J', PV.x0 + 24, ly, {s:11.5, w:'700', c:C.amberD});
  ctx.fillStyle = 'rgba(15,169,154,0.30)'; ctx.fillRect(PV.x0, ly + 15, 16, 14); ctx.strokeStyle = C.teal; ctx.strokeRect(PV.x0, ly + 15, 16, 14);
  txt(ctx, 'Flotación ∫V dp = ' + esn(waNow, 0) + ' J', PV.x0 + 24, ly + 22, {s:11.5, w:'700', c:'#0B7F74'});
}
function bar(y, label, v, vmax, f, col, opt){
  opt = opt || {};
  txt(ctx, label, LED.x, y, {s:10.5, w:'600', c:C.muted});
  txt(ctx, esn(v*(opt.live ? f : 1), 0) + ' J', LED.x + LED.w, y, {a:'right', s:11, w:'800', c:col});
  const by = y + 9, bw = LED.w, bh = 11;
  ctx.fillStyle = '#EEF2F7'; rrect(ctx, LED.x, by, bw, bh, 5); ctx.fill();
  const L = bw*clamp(v/vmax, 0, 1);
  if (opt.outline){ ctx.strokeStyle = col; ctx.lineWidth = 1.6; ctx.setLineDash([4, 3]); rrect(ctx, LED.x, by, L, bh, 5); ctx.stroke(); ctx.setLineDash([]); return; }
  if (f > 0.002){ ctx.fillStyle = col; rrect(ctx, LED.x, by, Math.max(3, L*f), bh, 5); ctx.fill();
    if (opt.hatch && hatchA){ ctx.fillStyle = hatchA; rrect(ctx, LED.x, by, Math.max(3, L*f), bh, 5); ctx.fill(); } }
}
function drawLedger(i, cF, aF, cyc){
  txt(ctx, 'Contabilidad por inserción', LED.x, 82, {s:13, w:'800'});
  const vmax = Math.max(P.Eins, P.Wci, P.Wiso, P.Wb, P.Eaux, 1e-9);
  const y0 = 110, dy = 44;
  bar(y0, 'Electricidad al ABIS · W_comp/(η_c·η_m)', P.Eins, vmax, cF, C.amberD, {live:true});
  bar(y0 + dy, 'Compresión ideal ∫V dp (1→2)', P.Wci, vmax, cF, '#F59E0B', {live:true, hatch:true});
  bar(y0 + 2*dy, 'Mínimo reversible p₀V₀·ln(p_H/p₀)', P.Wiso, vmax, 1, C.navy, {outline:true});
  bar(y0 + 3*dy, 'Flotación ∫V dp (3→4)', P.Wb, vmax, aF, C.teal, {live:true});
  bar(y0 + 4*dy, 'Electricidad útil (η_cap·η_t·η_g·η_pe)', P.Wout, vmax, aF, C.green, {live:true});
  bar(y0 + 5*dy, 'Auxiliares por inserción · P_aux/f', P.Eaux, vmax, cyc, C.violet, {live:true});
  const by = 378, done = i >= 4;
  ctx.fillStyle = done ? '#FFFFFF' : 'rgba(255,255,255,0.6)'; ctx.strokeStyle = done ? (P.ERR >= 1 ? C.green : C.red) : C.grid; ctx.lineWidth = done ? 2 : 1;
  rrect(ctx, LED.x, by, LED.w, 70, 10); ctx.fill(); ctx.stroke();
  txt(ctx, 'ERR = E_útil / (E_ABIS + E_aux)', LED.x + 12, by + 16, {s:10.5, w:'700', c:C.muted});
  txt(ctx, esn(P.ERR, 3), LED.x + 12, by + 45, {s:24, w:'800', c: done ? (P.ERR >= 1 ? C.green : C.red) : '#94A3B8'});
  txt(ctx, 'Cota ideal (η = 1):', LED.x + LED.w - 12, by + 36, {a:'right', s:10, w:'600', c:C.muted});
  txt(ctx, 'W_flot / W_comp = ' + esn(P.ERRi, 3), LED.x + LED.w - 12, by + 52, {a:'right', s:11, w:'800', c:C.navy});
  let msg;
  const dT = P.Tw - P.Ta;
  if (dT > 0.05) msg = 'T_agua > T_aire: la isoterma de ascenso se desplaza a la derecha; el área adicional es calor tomado del agua (límite de Carnot).';
  else if (dT < -0.05) msg = 'T_agua < T_aire: el aire se contrae al enfriarse y se pierde área de flotación.';
  else if (isoK) msg = 'Compresión isotérmica y T_agua = T_aire: ambas áreas coinciden (W_flot = W_iso); con η = 1 el ERR sería exactamente 1.';
  else msg = 'La franja entre la curva de compresión y la isoterma es trabajo convertido en calor (irreversibilidad): ERR ideal menor que 1.';
  wrap(ctx, msg, LED.x, by + 90, LED.w, 15, {s:10.5, w:'600', c:C.navy});
}
function frame(now){
  if (!cv.isConnected) return;
  const dt = Math.min(0.05, (now - last)/1000); last = now;
  if (isHidden(cv)){ requestAnimationFrame(frame); return; }
  if (!paused){ t += dt; tg += dt; if (t >= TC){ t -= TC; } }
  const ph = phaseAt(t), i = ph[0], s = ph[1];
  const cF = i > 1 ? 1 : (i === 1 ? ease(s) : 0);
  const aF = i > 3 ? 1 : (i === 3 ? s : 0);
  const pc = p0 + dp*cF, pa = pH - dp*aF;
  const s2 = i === 2 ? clamp((s - 0.45)/0.55, 0, 1) : 0;
  let mv = V0, mp = p0;
  if (i === 1){ mv = Vc(pc); mp = pc; }
  else if (i === 2){ mv = lerp(V2, V3, ease(s2)); mp = pH; }
  else if (i === 3){ mv = Va(pa); mp = pa; }
  else if (i === 4){ mv = lerp(V4, V0, ease(s)); mp = p0; }
  ctx.clearRect(0, 0, W, H); ctx.fillStyle = '#F7FBFE'; ctx.fillRect(0, 0, W, H);
  txt(ctx, 'Una inserción, paso a paso: columna de agua ↔ diagrama p–V', 20, 24, {s:14.5, w:'800'});
  txt(ctx, 'Trabajo técnico = ∫V dp: área entre cada curva y el eje de presión · 1 kPa·L = 1 J', 20, 46, {s:11, w:'600', c:C.muted});
  drawColumn(); drawPipe();
  let Vg = V0, colG = gasColor(P.Ta);
  if (i === 1){ Vg = Vc(pc); colG = gasColor(Tcomp(pc)); }
  else if (i === 2){ Vg = s < 0.45 ? V2*(1 - s/0.45) : 0; colG = gasColor(P.T2); }
  else if (i === 3){ Vg = V0*ease(s); }
  drawCylinder(Vg, colG);
  if (i === 2 && s < 0.45){ const q = pipePoint(ease(s/0.45)); ctx.fillStyle = gasColor(P.T2); ctx.strokeStyle = '#FFFFFF'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(q[0], q[1], 6.5, 0, 2*Math.PI); ctx.fill(); ctx.stroke(); }
  const xb = (COL.x0 + COL.x1)/2 + 4;
  if (i === 2 && s >= 0.45){ drawBubble(xb, COL.yBot - 18, mv, gasColor(lerp(P.T2, P.Tw, ease(s2))), false); }
  if (i === 3){ const yb = lerp(COL.yBot - 18, COL.ySurf + 14, aF); drawBubble(xb + 3*Math.sin(tg*5), yb, mv, gasColor(P.Tw), true); }
  if (i === 4 && s < 0.05 && ripples.length === 0) ripples.push({r: 4, a: 0.9});
  if (i !== 4) ripples = [];
  ripples.forEach(function(r){ if (!paused){ r.r += 40*dt; r.a -= 0.8*dt; } ctx.strokeStyle = 'rgba(255,255,255,' + Math.max(r.a, 0) + ')'; ctx.lineWidth = 2; ctx.beginPath(); ctx.ellipse(xb, COL.ySurf, r.r, r.r*0.3, 0, 0, 2*Math.PI); ctx.stroke(); });
  drawPV(i, cF, aF, pc, pa, mv, mp);
  chip(ctx, NAMES[i], PV.x0 - 8, 82, i === 1 ? '#FEF3C7' : i === 3 ? '#CCFBF1' : i === 2 ? '#FFEDD5' : '#E0F2FE', C.navy, 11.5);
  const cyc = clamp(t/(TC - PH[5]), 0, 1);
  drawLedger(i, cF, aF, cyc);
  let l1 = '', l2 = '';
  const Tc = function(T){ return esn(T - 273.15, 1) + ' °C'; };
  if (i === 0){ l1 = 'Admisión: V₀ = ' + esn(V0, 1) + ' L de aire a p₀ = ' + esn(p0, 1) + ' kPa'; l2 = 'y T_aire = ' + Tc(P.Ta) + ' (estado 1).'; }
  else if (i === 1){ l1 = 'Compresión ' + P.mode + ': p = ' + esn(pc, 1) + ' kPa · V = ' + esn(mv, 1) + ' L'; l2 = 'T ≈ ' + Tc(Tcomp(pc)) + ' · trabajo invertido ' + esn(Wcomp(pc), 0) + ' J (ideal).'; }
  else if (i === 2){ l1 = 'Inyección a z = H = ' + esn(P.H, 1) + ' m, p_H = ' + esn(pH, 1) + ' kPa.'; l2 = 'Equilibrio isobárico con el agua: ' + Tc(lerp(P.T2, P.Tw, ease(s2))) + ' → ' + Tc(P.Tw) + '.'; }
  else if (i === 3){ const V = mv, z = zOf(pa); l1 = 'Ascenso: z = ' + esn(z, 2) + ' m · p = ' + esn(pa, 1) + ' kPa · V = ' + esn(V, 1) + ' L'; l2 = 'F_b = ρgV = ' + esn(P.rho*9.80665*V/1000, 0) + ' N · trabajo de flotación ' + esn(Wasc(pa), 0) + ' J.'; }
  else { l1 = 'Liberación en la superficie: V₄ = V₀·T_agua/T_aire = ' + esn(V4, 1) + ' L'; l2 = 'vuelve a la atmósfera a p₀ (ciclo abierto).'; }
  txt(ctx, l1, 20, 532, {s:11, w:'700', c:C.navy}); txt(ctx, l2, 20, 549, {s:11, w:'600', c:C.muted});
  txt(ctx, 'Diagrama del proceso ideal; las irreversibilidades (η_c, η_m, η_cap, η_t, η_g, η_pe) y los auxiliares se contabilizan en las barras · modelo genérico · clic para pausar', 20, 569, {s:10, w:'500', c:'#64748B'});
  pauseBadge(ctx, W, H, paused);
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
}
__BOOT__
})();
</script>
"""


# -----------------------------------------------------------------------------
# 2. Flujo de potencia animado (Sankey con partículas)
# -----------------------------------------------------------------------------
_EF_TEMPLATE = r"""
<div style="width:100%;font-family:Inter,Segoe UI,Roboto,Arial,sans-serif;">
<canvas id="__CID__" title="Clic para pausar o continuar" style="width:100%;max-width:1100px;height:auto;aspect-ratio:1100/440;display:block;margin:0 auto;border-radius:16px;background:#F7FBFE;border:1px solid #E3EAF2;cursor:pointer"></canvas>
</div>
<script>
(function(){
const P = __PARAMS__;
__JSLIB__
function run(cv){
const W = 1100, H = 440;
const ctx = setupCanvas(cv, W, H);
let paused = false;
cv.addEventListener('click', function(){ paused = !paused; });
const NODES = [
  ['Red eléctrica', 'P_in = ' + fmtW(P.Pin)],
  ['Motor ABIS', 'η_m = ' + esn(P.eta_m, 2)],
  ['Compresor', 'W_iso/W_c = ' + esn(P.eta_c, 2)],
  ['Aire a profundidad', 'exergía'],
  ['Captura KEM', 'η_cap = ' + esn(P.eta_cap, 2)],
  ['Transmisión', 'η_t = ' + esn(P.eta_t, 3)],
  ['Generador', 'η_g = ' + esn(P.eta_g, 2)],
  ['Electrónica PDU', 'η_pe = ' + esn(P.eta_pe, 3)],
  ['Salida útil', 'P_out = ' + fmtW(P.Wout)]
];
const XS = NODES.map(function(_, i){ return 92 + (980 - 92)*i/(NODES.length - 1); });
const FIN = [P.Pin, P.Pabis, P.Wc, P.Wiso, P.Wb, P.Wmech, P.Wshaft, P.Wgen, P.Wout];
const FOUT = [P.Pabis, P.Wc, P.Wiso, P.Wb, P.Wmech, P.Wshaft, P.Wgen, P.Wout, P.Wout];
const LOSS = [P.Paux, P.Pabis - P.Wc, P.Wc - P.Wiso, P.deficit, P.Wb - P.Wmech, P.Wmech - P.Wshaft, P.Wshaft - P.Wgen, P.Wgen - P.Wout, 0];
const LNAME = ['Auxiliares', 'Motor', 'Compresión', 'Déficit térmico', 'Hidrodinámica', 'Mecánica', 'Generador', 'Electrónica', ''];
const SEGC = ['#F59E0B', '#D97706', '#0098D4', '#0284C7', '#0FA99A', '#0FA99A', '#16A34A', '#16A34A', '#16A34A'];
const yT = 140, TH = 86, yC = 352;
const sc = TH/Math.max(P.Pin, P.Wb, P.Wiso + P.gain, 1e-9);
function th(F){ return Math.max(1.5, sc*F); }
const totalLoss = LOSS.reduce(function(a, b){ return a + Math.max(0, b); }, 0);
const RATE = 60, VEL = 125;
const quantum = P.Pin/RATE;
let parts = [], acc = 0, accG = 0, last = performance.now();
function lossPath(j){
  const lw = th(Math.max(0, LOSS[j])), ys = yT + th(FOUT[j]) + lw/2, x = XS[j] + 5;
  return [[x, ys], [x + 42, ys], [x + 48, yC - 46], [x + 48, yC]];
}
function gainPath(){
  const lg = th(P.gain), ye = yT + th(FIN[3]) + lg/2, x = XS[3] - 5;
  return [[x - 22, yC], [x - 22, yC - 46], [x - 18, ye], [x, ye]];
}
function bez(Q, t){ const u = 1 - t; return [u*u*u*Q[0][0] + 3*u*u*t*Q[1][0] + 3*u*t*t*Q[2][0] + t*t*t*Q[3][0], u*u*u*Q[0][1] + 3*u*u*t*Q[1][1] + 3*u*t*t*Q[2][1] + t*t*t*Q[3][1]]; }
function strokeBez(Q, w, col){ ctx.strokeStyle = col; ctx.lineWidth = w; ctx.beginPath(); ctx.moveTo(Q[0][0], Q[0][1]); ctx.bezierCurveTo(Q[1][0], Q[1][1], Q[2][0], Q[2][1], Q[3][0], Q[3][1]); ctx.stroke(); }
function segX(seg){ return seg < 0 ? [24, XS[0]] : seg >= 8 ? [XS[8], 1076] : [XS[seg], XS[seg + 1]]; }
function segTh(seg){ return seg < 0 ? th(P.Pin) : th(FOUT[Math.min(seg, 8)]); }
function drawStatic(){
  const g = ctx.createLinearGradient(40, 0, 1060, 0); g.addColorStop(0, '#FECACA'); g.addColorStop(1, '#FDE68A');
  ctx.fillStyle = g; rrect(ctx, 40, yC, 1020, 14, 7); ctx.fill();
  txt(ctx, 'Calor disipado → agua y ambiente: ' + fmtW(totalLoss) + ' (' + esn(100*totalLoss/Math.max(P.Pin + P.gain, 1e-9), 0) + ' % de lo que entra)', 550, yC + 32, {a:'center', s:12, w:'800', c:'#B91C1C'});
  for (let j = 0; j < 8; j++){ if (LOSS[j] > 1e-9) strokeBez(lossPath(j), th(LOSS[j]), j === 0 ? 'rgba(124,58,237,0.22)' : 'rgba(229,72,77,0.20)'); }
  if (P.gain > 1e-9){ strokeBez(gainPath(), th(P.gain), 'rgba(234,88,12,0.30)'); txt(ctx, 'Calor del agua (ΔT > 0)', XS[3] - 12 + Math.max(3, th(P.gain)/2), yC - 64, {s:9.5, w:'700', c:'#C2410C'}); txt(ctx, '+' + fmtW(P.gain), XS[3] - 12 + Math.max(3, th(P.gain)/2), yC - 50, {s:10.5, w:'800', c:'#C2410C'}); }
  for (let seg = -1; seg <= 8; seg++){
    const xr = segX(seg), h = segTh(seg), col = seg < 0 ? SEGC[0] : SEGC[Math.min(seg, 8)];
    ctx.fillStyle = col; ctx.globalAlpha = 0.20; ctx.fillRect(xr[0], yT, xr[1] - xr[0], h); ctx.globalAlpha = 1;
    if (seg >= 0 && seg < 8) txt(ctx, fmtW(FOUT[seg]), (xr[0] + xr[1])/2, yT - 12, {a:'center', s:10.5, w:'800', c:col});
  }
  ctx.fillStyle = SEGC[8]; ctx.globalAlpha = 0.35; ctx.beginPath(); const ho = th(P.Wout); ctx.moveTo(1076, yT - 6); ctx.lineTo(1094, yT + ho/2); ctx.lineTo(1076, yT + ho + 6); ctx.closePath(); ctx.fill(); ctx.globalAlpha = 1;
  for (let i = 0; i < NODES.length; i++){
    const h = Math.max(i === 0 ? th(P.Pin) : th(FIN[i]), th(FOUT[i]));
    ctx.fillStyle = '#0B2A5B'; rrect(ctx, XS[i] - 4, yT - 5, 8, h + 10, 3); ctx.fill();
    txt(ctx, NODES[i][0], XS[i], yT - 54, {a:'center', s:11, w:'800'});
    txt(ctx, NODES[i][1], XS[i], yT - 39, {a:'center', s:10, w:'600', c:'#5B6B80'});
  }
  for (let j = 0; j < 8; j++){
    if (LOSS[j] <= 1e-9 || LOSS[j]/Math.max(P.Pin, 1e-9) < 0.012) continue;
    const x = XS[j] + 53 + Math.max(3, th(LOSS[j])/2) + 6;
    txt(ctx, LNAME[j], x, yC - 30, {s:9.5, w:'700', c:'#64748B'});
    txt(ctx, '−' + fmtW(LOSS[j]), x, yC - 16, {s:10.5, w:'800', c: j === 0 ? '#6D28D9' : '#B91C1C'});
  }
}
function spawnMain(){ parts.push({m: 'main', seg: -1, x: 24, r: Math.random(), t: 0}); }
function spawnGain(){ parts.push({m: 'gain', t: 0, o: Math.random() - 0.5}); }
function step(dt){
  acc += dt*RATE; while (acc >= 1){ spawnMain(); acc -= 1; }
  if (P.gain > 0){ accG += dt*RATE*P.gain/Math.max(P.Pin, 1e-9); while (accG >= 1){ spawnGain(); accG -= 1; } }
  parts.forEach(function(q){
    if (q.m === 'main'){
      q.x += VEL*dt;
      const xr = segX(q.seg);
      if (q.x >= xr[1] && q.seg < 8){
        const j = q.seg + 1, frac = FOUT[j]/Math.max(FIN[j], 1e-12);
        if (frac < 1 && q.r > frac){ q.m = 'loss'; q.j = j; q.t = 0; q.o = (q.r - frac)/(1 - frac) - 0.5; }
        else { q.r = q.r/Math.max(frac, 1e-12); q.seg = j; if (q.r > 1) q.r = 1; }
      }
      if (q.seg >= 8 && q.x >= 1084) q.dead = true;
    } else if (q.m === 'loss'){
      q.t += dt*0.85; if (q.t >= 1){ q.m = 'heat'; q.t = 0; const e = lossPath(q.j)[3]; q.x = e[0]; q.y = yC + 7; q.vx = (Math.random() - 0.5)*30; }
    } else if (q.m === 'heat'){
      q.t += dt*1.6; q.x += q.vx*dt; if (q.t >= 1) q.dead = true;
    } else if (q.m === 'gain'){
      q.t += dt*0.85; if (q.t >= 1){ const f3 = FIN[3]/Math.max(FOUT[3], 1e-12); q.m = 'main'; q.seg = 3; q.x = XS[3]; q.r = f3 + (1 - f3)*(q.o + 0.5); }
    }
  });
  parts = parts.filter(function(q){ return !q.dead; });
}
function drawParts(){
  parts.forEach(function(q){
    let x, y, col, a = 1;
    if (q.m === 'main'){ x = q.x; y = yT + clamp(q.r, 0.02, 0.98)*segTh(q.seg); col = q.seg < 0 ? SEGC[0] : SEGC[Math.min(q.seg, 8)]; }
    else if (q.m === 'loss'){ const Q = lossPath(q.j), b = bez(Q, q.t), lw = th(LOSS[q.j]); x = b[0] + q.o*Math.min(lw, 12)*0.8*(1 - 0.3*q.t); y = b[1]; col = q.j === 0 ? '#7C3AED' : '#E5484D'; }
    else if (q.m === 'heat'){ x = q.x; y = q.y; col = '#F87171'; a = 1 - q.t; }
    else { const b = bez(gainPath(), q.t); x = b[0] + q.o*Math.min(th(P.gain), 12)*0.8; y = b[1]; col = '#EA580C'; }
    ctx.globalAlpha = a; ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x, y, 2.6, 0, 2*Math.PI); ctx.fill(); ctx.globalAlpha = 1;
  });
}
for (let i = 0; i < 600; i++) step(1/60);
function frame(now){
  if (!cv.isConnected) return;
  const dt = Math.min(0.05, (now - last)/1000); last = now;
  if (isHidden(cv)){ requestAnimationFrame(frame); return; }
  if (!paused) step(dt);
  ctx.clearRect(0, 0, W, H); ctx.fillStyle = '#F7FBFE'; ctx.fillRect(0, 0, W, H);
  txt(ctx, 'Flujo de potencia en régimen (animado)', 20, 24, {s:14.5, w:'800'});
  txt(ctx, 'Ancho de banda ∝ potencia · cada partícula ≈ ' + fmtW(quantum) + ' · en cada etapa se desvía la fracción perdida', 20, 45, {s:11, w:'600', c:'#5B6B80'});
  const ok = P.ERR >= 1;
  txt(ctx, 'ERR = ' + esn(P.ERR, 3), 1080, 24, {a:'right', s:16, w:'800', c: ok ? '#16A34A' : '#E5484D'});
  txt(ctx, 'P_neta = ' + fmtW(P.Pnet), 1080, 45, {a:'right', s:11, w:'700', c: P.Pnet >= 0 ? '#16A34A' : '#E5484D'});
  drawStatic(); drawParts();
  txt(ctx, 'Modelo genérico de primeros principios · valores de régimen a ' + esn(P.f, 2) + ' inserciones/s · clic para pausar', 20, 428, {s:10, w:'500', c:'#64748B'});
  pauseBadge(ctx, W, H, paused);
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
}
__BOOT__
})();
</script>
"""


def pv_cycle_animation_html(params: dict) -> str:
    return render(_PV_TEMPLATE, params, "pv")


def energy_flow_animation_html(params: dict) -> str:
    return render(_EF_TEMPLATE, params, "ef")
