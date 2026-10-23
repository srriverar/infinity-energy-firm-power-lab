"""
core/anim_value.py — Animaciones de «Valor sistémico».

1. `ucf_stream_animation_html`: despacho bajo incertidumbre en tiempo real. Para
   cada recurso se programa W_s* = F⁻¹(q*) y en cada intervalo se liquida la
   desviación: c_u·(W − W_s)⁺ + c_o·(W_s − W)⁺. Las series son sintéticas con la
   distribución marginal EXACTA de cada modelo de la página (cópula gaussiana
   AR(1): z_t = φ z_{t−1} + √(1−φ²) ε_t, W_t = F⁻¹(Φ(z_t))), de modo que el costo
   medio realizado converge a la UCF analítica en el óptimo.
2. `fleet_animation_html`: N módulos independientes de Markov de 2 estados
   (λ = 1/MTBF, μ = 1/MTTR) frente a una unidad única de igual capacidad total y
   la misma disponibilidad, contrastados con el mismo compromiso firme.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from .anim import render
from .reliability import firm_capacity_identical
from .ucf import Resource, levelized_uncertainty_cost

QMIN, QMAX = 0.0005, 0.9995


# -----------------------------------------------------------------------------
# Payloads (Python, comprobables con pruebas)
# -----------------------------------------------------------------------------
def ucf_stream_payload(resources: list[tuple[str, str, Resource]], cu: float, co: float,
                       n_q: int = 401, n_bins: int = 40, phi: float = 0.7, sps: float = 6.0) -> dict:
    cap = float(max(res.w_max for _, _, res in resources))
    edges = np.linspace(0.0, cap, n_bins + 1)
    q = np.linspace(QMIN, QMAX, n_q)
    rows = []
    for name, color, res in resources:
        L = levelized_uncertainty_cost(res, cu, co)
        qt = res.ppf(q)
        F = np.clip(res.cdf(edges[1:-1]), 0.0, 1.0)
        probs = np.maximum(np.diff(np.concatenate([[0.0], F, [1.0]])), 0.0)
        rows.append({
            "name": name, "color": color,
            "qt": [round(float(v), 4) for v in qt],
            "ws": float(L["W_s*"]), "ucf": float(L["UCF*"]), "mean": float(L["E[W]"]),
            "hist": [round(float(v), 6) for v in probs],
        })
    return {"cap": cap, "cu": float(cu), "co": float(co), "q": float(cu / (cu + co)), "phi": float(phi),
            "sps": float(sps), "qmin": QMIN, "qmax": QMAX, "res": rows}


def sample_from_table(row: dict, u: np.ndarray, qmin: float = QMIN, qmax: float = QMAX) -> np.ndarray:
    """Réplica en Python de la interpolación usada en el navegador (para pruebas)."""
    tab = np.asarray(row["qt"], float)
    m = len(tab)
    pos = np.clip((np.asarray(u, float) - qmin) / (qmax - qmin) * (m - 1), 0, m - 1)
    i = np.minimum(np.floor(pos).astype(int), m - 2)
    f = pos - i
    return tab[i] * (1 - f) + tab[i + 1] * f


def fleet_payload(N: int, A: float, total: float, alpha: float, mtbf: float | None = None,
                  mttr: float | None = None) -> dict:
    N = int(max(1, N))
    Pm = total / N
    assumed = mtbf is None or mttr is None
    if assumed:
        mttr = 48.0
        mtbf = mttr * A / max(1.0 - A, 1e-9)
    fc = firm_capacity_identical(N, A, Pm, alpha)
    k_req = int(math.ceil(fc / Pm - 1e-9)) if fc > 0 else 0
    p_mod = float(stats.binom.sf(k_req - 1, N, A)) if k_req > 0 else 1.0
    p_one = float(A) if fc > 0 else 1.0
    hps = float(min(600.0, max(40.0, (mtbf + mttr) / 8.0)))   # ≈ un ciclo de la unidad única cada 8 s
    return {"N": N, "Pm": Pm, "total": float(total), "A": float(A), "mtbf": float(mtbf), "mttr": float(mttr),
            "assumed": bool(assumed), "alpha": float(alpha), "fc": float(fc), "pM": p_mod, "pO": p_one,
            "hps": hps, "win": 20.0 * hps, "expected": N * A * Pm}


# -----------------------------------------------------------------------------
# 1. Despacho bajo incertidumbre en tiempo real
# -----------------------------------------------------------------------------
_UCF_TEMPLATE = r"""
<div style="width:100%;font-family:Inter,Segoe UI,Roboto,Arial,sans-serif;">
<canvas id="__CID__" title="Clic para pausar o continuar" style="width:100%;max-width:1100px;height:auto;aspect-ratio:1100/650;display:block;margin:0 auto;border-radius:16px;background:#F7FBFE;border:1px solid #E3EAF2;cursor:pointer"></canvas>
</div>
<script>
(function(){
const P = __PARAMS__;
__JSLIB__
function run(cv){
const W = 1100, H = 650;
const ctx = setupCanvas(cv, W, H);
let paused = false;
cv.addEventListener('click', function(){ paused = !paused; });
const R = P.res, nR = R.length;
const LANE0 = 76, LH = 98;
const CH = {x0:168, x1:690}, HG = {x0:702, w:112}, CT = {x:834};
const NW = 90, dx = (CH.x1 - CH.x0)/NW;
const NB = R[0].hist.length;
const S = R.map(function(){ return {z: gauss(), buf: [], hist: new Array(NB).fill(0), n: 0, cum: 0, eu: 0, eo: 0, curve: [0]}; });
let acc = 0, T = 0, last = performance.now();
function qInterp(tab, u){ const m = tab.length; let pos = (u - P.qmin)/(P.qmax - P.qmin)*(m - 1); pos = clamp(pos, 0, m - 1); const i = Math.min(Math.floor(pos), m - 2), f = pos - i; return tab[i]*(1 - f) + tab[i + 1]*f; }
function push(k, count){
  const s = S[k], r = R[k];
  s.z = P.phi*s.z + Math.sqrt(1 - P.phi*P.phi)*gauss();
  const w = qInterp(r.qt, Phi(s.z));
  s.buf.push(w); if (s.buf.length > NW + 2) s.buf.shift();
  if (!count) return;
  const d = w - r.ws;
  if (d >= 0){ s.eu += d; s.cum += P.cu*d; } else { s.eo -= d; s.cum -= P.co*d; }
  s.hist[clamp(Math.floor(w/P.cap*NB), 0, NB - 1)] += 1; s.n += 1;
  s.curve.push(s.cum);
}
for (let k = 0; k < nR; k++) for (let i = 0; i < NW + 2; i++) push(k, false);
function drawHeader(){
  txt(ctx, 'Despacho bajo incertidumbre en tiempo real', 20, 22, {s:14.5, w:'800'});
  let x = 20; const y = 46;
  ctx.fillStyle = 'rgba(0,152,212,0.45)'; ctx.fillRect(x, y - 6, 14, 12); x += 20;
  x += txt(ctx, 'disponible no programada · c_u = ' + esn(P.cu, 0) + ' USD/MWh', x, y, {s:11, w:'700', c:'#0A5FA8'}) + 20;
  ctx.fillStyle = 'rgba(229,72,77,0.6)'; ctx.fillRect(x, y - 6, 14, 12); x += 20;
  x += txt(ctx, 'programada no entregada · c_o = ' + esn(P.co, 0) + ' USD/MWh', x, y, {s:11, w:'700', c:'#B91C1C'}) + 20;
  ctx.save(); ctx.setLineDash([6, 4]); ctx.strokeStyle = '#0B2A5B'; ctx.lineWidth = 1.6; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 24, y); ctx.stroke(); ctx.restore(); x += 30;
  txt(ctx, 'W_s* = F⁻¹(q*) · q* = c_u/(c_u+c_o) = ' + esn(P.q, 3), x, y, {s:11, w:'700'});
  txt(ctx, 'Potencia disponible W(t) en MW · cada barra = 1 intervalo de 1 h', CH.x0, 66, {s:10, w:'700', c:'#5B6B80'});
  txt(ctx, 'Distribución', HG.x0, 66, {s:10, w:'700', c:'#5B6B80'});
  txt(ctx, 'Costo de la desviación', CT.x, 66, {s:10, w:'700', c:'#5B6B80'});
}
function drawLane(k){
  const r = R[k], s = S[k], y0 = LANE0 + k*LH, py0 = y0 + 6, py1 = y0 + LH - 16;
  const Yw = function(w){ return py1 - (py1 - py0)*clamp(w/P.cap, 0, 1.03); };
  txt(ctx, r.name, 20, y0 + 16, {s:12.5, w:'800', c: r.color});
  txt(ctx, 'W_s* = ' + esn(r.ws, 1) + ' MW', 20, y0 + 36, {s:10.5, w:'700', c:'#0B2A5B'});
  txt(ctx, 'E[W] = ' + esn(r.mean, 1) + ' MW', 20, y0 + 52, {s:10.5, w:'600', c:'#5B6B80'});
  ctx.fillStyle = '#FFFFFF'; ctx.strokeStyle = '#E3EAF2'; ctx.lineWidth = 1;
  rrect(ctx, CH.x0 - 4, py0 - 4, CH.x1 - CH.x0 + 8, py1 - py0 + 8, 6); ctx.fill(); ctx.stroke();
  rrect(ctx, HG.x0 - 4, py0 - 4, HG.w + 12, py1 - py0 + 8, 6); ctx.fill(); ctx.stroke();
  txt(ctx, esn(P.cap, 0), CH.x0 - 9, Yw(P.cap), {a:'right', s:9.5, w:'600', c:'#94A3B8'});
  txt(ctx, '0', CH.x0 - 9, Yw(0), {a:'right', s:9.5, w:'600', c:'#94A3B8'});
  const ys = Yw(r.ws);
  ctx.save(); ctx.beginPath(); ctx.rect(CH.x0, py0 - 3, CH.x1 - CH.x0, py1 - py0 + 6); ctx.clip();
  for (let i = 0; i < s.buf.length; i++){
    const x = CH.x0 + (i - 1 - acc)*dx, w = s.buf[i], yw = Yw(w);
    ctx.fillStyle = w >= r.ws ? 'rgba(0,152,212,0.30)' : 'rgba(229,72,77,0.50)';
    ctx.fillRect(x, Math.min(ys, yw), dx + 0.6, Math.abs(yw - ys));
  }
  ctx.strokeStyle = r.color; ctx.lineWidth = 1.8; ctx.beginPath();
  for (let i = 0; i < s.buf.length; i++){ const x = CH.x0 + (i - 1 - acc)*dx, yw = Yw(s.buf[i]); if (i === 0) ctx.moveTo(x, yw); else ctx.lineTo(x, yw); ctx.lineTo(x + dx, yw); }
  ctx.stroke(); ctx.restore();
  ctx.save(); ctx.setLineDash([6, 4]); ctx.strokeStyle = '#0B2A5B'; ctx.lineWidth = 1.4;
  ctx.beginPath(); ctx.moveTo(CH.x0, ys); ctx.lineTo(CH.x1, ys); ctx.moveTo(HG.x0 - 4, ys); ctx.lineTo(HG.x0 + HG.w + 8, ys); ctx.stroke(); ctx.restore();
  const maxT = Math.max.apply(null, r.hist) || 1, sc = HG.w/(1.12*maxT);
  for (let b = 0; b < NB; b++){
    const ya = Yw(P.cap*(b + 1)/NB), yb = Yw(P.cap*b/NB), emp = s.n ? s.hist[b]/s.n : 0;
    const mid = P.cap*(b + 0.5)/NB;
    ctx.fillStyle = mid >= r.ws ? 'rgba(0,152,212,0.55)' : 'rgba(229,72,77,0.70)';
    ctx.fillRect(HG.x0, ya + 0.4, Math.min(HG.w + 6, emp*sc), Math.max(0.8, yb - ya - 0.8));
  }
  ctx.strokeStyle = '#0B2A5B'; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.moveTo(HG.x0, Yw(0));
  for (let b = 0; b < NB; b++){ const ya = Yw(P.cap*(b + 1)/NB), yb = Yw(P.cap*b/NB), L = r.hist[b]*sc; ctx.lineTo(HG.x0 + L, yb); ctx.lineTo(HG.x0 + L, ya); }
  ctx.lineTo(HG.x0, Yw(P.cap)); ctx.stroke();
  const avg = s.n ? s.cum/s.n : 0;
  txt(ctx, 'Costo medio realizado', CT.x, y0 + 12, {s:10, w:'600', c:'#5B6B80'});
  txt(ctx, esn(avg, 0) + ' USD/h', CT.x, y0 + 32, {s:15.5, w:'800', c: r.color});
  txt(ctx, 'UCF* analítico: ' + esn(r.ucf, 0) + ' USD/h (' + esn(r.ucf/Math.max(r.mean, 1e-9), 1) + ' USD/MWh)', CT.x, y0 + 52, {s:10, w:'700', c:'#0B2A5B'});
  txt(ctx, 'no programada ' + esn(s.eu, 0) + ' MWh · faltante ' + esn(s.eo, 0) + ' MWh', CT.x, y0 + 68, {s:9.5, w:'600', c:'#5B6B80'});
}
function drawCum(){
  const y0 = LANE0 + nR*LH + 2, py0 = y0 + 30, py1 = H - 36, x0 = CH.x0, x1 = 880;
  txt(ctx, 'Costo acumulado de incertidumbre (USD)', 20, y0 + 12, {s:12.5, w:'800'});
  txt(ctx, 't = ' + esn(T, 0) + ' h simuladas', x1, y0 + 12, {a:'right', s:10.5, w:'700', c:'#5B6B80'});
  ctx.fillStyle = '#FFFFFF'; ctx.strokeStyle = '#E3EAF2'; ctx.lineWidth = 1; rrect(ctx, x0 - 4, py0 - 6, x1 - x0 + 8, py1 - py0 + 12, 6); ctx.fill(); ctx.stroke();
  const tmax = Math.max(T, 48);
  let ymax = 1; for (let k = 0; k < nR; k++){ ymax = Math.max(ymax, S[k].cum, R[k].ucf*T); }
  ymax *= 1.08;
  const Xt = function(t){ return x0 + (x1 - x0)*t/tmax; }, Yc = function(v){ return py1 - (py1 - py0)*v/ymax; };
  txt(ctx, esn(ymax/1.08, 0), x0 - 9, Yc(ymax/1.08), {a:'right', s:9.5, w:'600', c:'#94A3B8'});
  txt(ctx, '0', x0 - 9, py1, {a:'right', s:9.5, w:'600', c:'#94A3B8'});
  ctx.fillStyle = 'rgba(255,255,255,0.85)'; rrect(ctx, x0 + 6, py0 - 1, 236, 18, 6); ctx.fill();
  ctx.strokeStyle = '#5B6B80'; ctx.lineWidth = 2.2; ctx.beginPath(); ctx.moveTo(x0 + 12, py0 + 8); ctx.lineTo(x0 + 30, py0 + 8); ctx.stroke();
  txt(ctx, 'realizado', x0 + 35, py0 + 8, {s:10, w:'700', c:'#5B6B80'});
  ctx.save(); ctx.setLineDash([5, 4]); ctx.lineWidth = 1.3; ctx.beginPath(); ctx.moveTo(x0 + 98, py0 + 8); ctx.lineTo(x0 + 118, py0 + 8); ctx.stroke(); ctx.restore();
  txt(ctx, 'esperado = UCF*·t', x0 + 123, py0 + 8, {s:10, w:'700', c:'#5B6B80'});
  const ends = [];
  for (let k = 0; k < nR; k++){
    const s = S[k], r = R[k], stride = Math.max(1, Math.ceil(s.curve.length/500));
    ctx.save(); ctx.setLineDash([5, 4]); ctx.strokeStyle = r.color; ctx.globalAlpha = 0.55; ctx.lineWidth = 1.3;
    ctx.beginPath(); ctx.moveTo(Xt(0), Yc(0)); ctx.lineTo(Xt(T), Yc(r.ucf*T)); ctx.stroke(); ctx.restore();
    ctx.strokeStyle = r.color; ctx.lineWidth = 2.2; ctx.beginPath();
    for (let i = 0; i < s.curve.length; i += stride){ const x = Xt(i), y = Yc(s.curve[i]); if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
    ctx.lineTo(Xt(s.curve.length - 1), Yc(s.cum)); ctx.stroke();
    ends.push({y: Yc(s.cum), k: k});
  }
  ends.sort(function(a, b){ return a.y - b.y; });
  for (let i = 1; i < ends.length; i++){ if (ends[i].y - ends[i - 1].y < 13) ends[i].y = ends[i - 1].y + 13; }
  ends.forEach(function(e){ const r = R[e.k]; txt(ctx, r.name + ' · USD ' + esn(S[e.k].cum, 0), x1 + 12, e.y, {s:10.5, w:'800', c: r.color}); });
}
function frame(now){
  if (!cv.isConnected) return;
  const dt = Math.min(0.1, (now - last)/1000); last = now;
  if (isHidden(cv)){ requestAnimationFrame(frame); return; }
  if (!paused){ acc += dt*P.sps; while (acc >= 1){ for (let k = 0; k < nR; k++) push(k, true); T += 1; acc -= 1; } }
  ctx.clearRect(0, 0, W, H); ctx.fillStyle = '#F7FBFE'; ctx.fillRect(0, 0, W, H);
  drawHeader();
  for (let k = 0; k < nR; k++) drawLane(k);
  drawCum();
  txt(ctx, 'Series sintéticas con la distribución exacta de cada modelo (cópula gaussiana AR(1), φ = ' + esn(P.phi, 2) + ') · W_s* óptimo de cada recurso · el promedio converge a la UCF* · clic para pausar', 20, H - 12, {s:10, w:'500', c:'#64748B'});
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
# 2. Flota modular vs unidad única (Markov de 2 estados)
# -----------------------------------------------------------------------------
_FLEET_TEMPLATE = r"""
<div style="width:100%;font-family:Inter,Segoe UI,Roboto,Arial,sans-serif;">
<canvas id="__CID__" title="Clic para pausar o continuar" style="width:100%;max-width:1100px;height:auto;aspect-ratio:1100/480;display:block;margin:0 auto;border-radius:16px;background:#F7FBFE;border:1px solid #E3EAF2;cursor:pointer"></canvas>
</div>
<script>
(function(){
const P = __PARAMS__;
__JSLIB__
function run(cv){
const W = 1100, H = 480;
const ctx = setupCanvas(cv, W, H);
let paused = false;
cv.addEventListener('click', function(){ paused = !paused; });
const TEAL = '#0FA99A', NAVY = '#0B2A5B', RED = '#E5484D', MUTED = '#5B6B80';
const N = P.N, lam = 1/P.mtbf, mu = 1/P.mttr;
const up = new Uint8Array(N), fl = new Float32Array(N);
let k = 0;
for (let i = 0; i < N; i++){ up[i] = Math.random() < P.A ? 1 : 0; k += up[i]; }
let one = Math.random() < P.A ? 1 : 0, flOne = 0;
let simH = 0, okM = 0, okO = 0, defM = 0, defO = 0, ensM = 0, ensO = 0, failM = 0, failO = 0;
const hist = [];
let last = performance.now();
const GB = {x:34, y:96, w:286, h:142};
let cell = clamp(Math.floor(Math.sqrt(GB.w*GB.h/N)), 3, 64), cols = Math.max(1, Math.floor(GB.w/cell)), rows = Math.ceil(N/cols);
while (rows*cell > GB.h && cell > 3){ cell -= 1; cols = Math.max(1, Math.floor(GB.w/cell)); rows = Math.ceil(N/cols); }
const gap = cell >= 8 ? 1.5 : (cell >= 5 ? 1 : 0.4);
const gx0 = GB.x + (GB.w - cols*cell)/2, gy0 = GB.y + (GB.h - rows*cell)/2;
const lm = lam + mu;
function simulate(dh){
  const e = 1 - Math.exp(-lm*dh), pf = lam/lm*e, pr = mu/lm*e;   // transiciones exactas de la cadena de 2 estados
  for (let i = 0; i < N; i++){
    if (up[i]){ if (Math.random() < pf){ up[i] = 0; k -= 1; failM += 1; fl[i] = 1; } }
    else if (Math.random() < pr){ up[i] = 1; k += 1; }
  }
  if (one){ if (Math.random() < pf){ one = 0; failO += 1; flOne = 1; } }
  else if (Math.random() < pr){ one = 1; }
  const cm = k*P.Pm, c1 = one*P.total;
  simH += dh;
  if (cm + 1e-9 >= P.fc) okM += dh; else { defM += dh; ensM += (P.fc - cm)*dh; }
  if (c1 + 1e-9 >= P.fc) okO += dh; else { defO += dh; ensO += (P.fc - c1)*dh; }
  hist.push([simH, cm, c1]);
  while (hist.length > 2 && hist[1][0] < simH - P.win) hist.shift();
}
function drawLeft(){
  ctx.fillStyle = '#FFFFFF'; ctx.strokeStyle = '#E3EAF2'; ctx.lineWidth = 1;
  rrect(ctx, 20, 62, 314, 206, 10); ctx.fill(); ctx.stroke();
  txt(ctx, 'Planta modular · ' + esn(N, 0) + ' × ' + (P.Pm >= 1 ? esn(P.Pm, 2) + ' MW' : esn(P.Pm*1000, 0) + ' kW'), 34, 80, {s:12.5, w:'800', c: TEAL});
  for (let i = 0; i < N; i++){
    const cx = gx0 + (i % cols)*cell, cy = gy0 + Math.floor(i/cols)*cell;
    ctx.fillStyle = up[i] ? TEAL : (fl[i] > 0 ? '#F97316' : RED);
    ctx.fillRect(cx + gap/2, cy + gap/2, cell - gap, cell - gap);
  }
  txt(ctx, 'Disponibles ' + esn(k, 0) + '/' + esn(N, 0) + ' → ' + esn(k*P.Pm, 1) + ' MW', 34, 254, {s:11.5, w:'800', c: NAVY});
  ctx.fillStyle = '#FFFFFF'; ctx.strokeStyle = '#E3EAF2'; rrect(ctx, 20, 280, 314, 186, 10); ctx.fill(); ctx.stroke();
  txt(ctx, 'Unidad única · 1 × ' + esn(P.total, 0) + ' MW', 34, 298, {s:12.5, w:'800', c: NAVY});
  ctx.fillStyle = one ? NAVY : (flOne > 0 ? '#F97316' : RED); rrect(ctx, 34, 314, 286, 92, 8); ctx.fill();
  txt(ctx, one ? 'EN SERVICIO' : 'EN REPARACIÓN', 177, 352, {a:'center', s:16, w:'800', c:'#FFFFFF'});
  txt(ctx, one ? esn(P.total, 1) + ' MW disponibles' : '0 MW disponibles', 177, 376, {a:'center', s:11.5, w:'700', c:'rgba(255,255,255,0.9)'});
  txt(ctx, 'Misma disponibilidad A, MTBF y MTTR que cada módulo', 34, 426, {s:10.5, w:'600', c: MUTED});
  txt(ctx, 'Fallas: módulos ' + esn(failM, 0) + ' · unidad única ' + esn(failO, 0), 34, 446, {s:10.5, w:'700', c: NAVY});
}
function drawChart(){
  const X0 = 424, X1 = 1072, Y0 = 92, Y1 = 278;
  txt(ctx, 'Capacidad disponible (MW) · ventana móvil de ' + esn(P.win, 0) + ' h', X0 - 8, 72, {s:12, w:'800'});
  ctx.fillStyle = '#FFFFFF'; ctx.strokeStyle = '#E3EAF2'; ctx.lineWidth = 1; rrect(ctx, X0 - 8, Y0 - 8, X1 - X0 + 16, Y1 - Y0 + 16, 8); ctx.fill(); ctx.stroke();
  const ymax = P.total*1.08;
  const Yc = function(c){ return Y1 - (Y1 - Y0)*c/ymax; }, Xt = function(t){ return X1 - (X1 - X0)*(simH - t)/P.win; };
  [0, 0.5, 1].forEach(function(f){ const y = Yc(P.total*f); ctx.strokeStyle = '#EEF2F7'; ctx.beginPath(); ctx.moveTo(X0, y); ctx.lineTo(X1, y); ctx.stroke(); txt(ctx, esn(P.total*f, 0), X0 - 12, y, {a:'right', s:9.5, w:'600', c:'#94A3B8'}); });
  ctx.save(); ctx.beginPath(); ctx.rect(X0, Y0 - 6, X1 - X0, Y1 - Y0 + 12); ctx.clip();
  for (let i = 1; i < hist.length; i++){
    const xa = Xt(hist[i - 1][0]), xb = Xt(hist[i][0]);
    if (hist[i][2] + 1e-9 < P.fc){ ctx.fillStyle = 'rgba(229,72,77,0.16)'; ctx.fillRect(xa, Yc(P.fc), xb - xa + 0.5, Yc(hist[i][2]) - Yc(P.fc)); }
    if (hist[i][1] + 1e-9 < P.fc){ ctx.fillStyle = 'rgba(229,72,77,0.55)'; ctx.fillRect(xa, Yc(P.fc), xb - xa + 0.5, Yc(hist[i][1]) - Yc(P.fc)); }
  }
  ctx.strokeStyle = 'rgba(11,42,91,0.80)'; ctx.lineWidth = 1.6; ctx.beginPath();
  for (let i = 0; i < hist.length; i++){ const x = Xt(hist[i][0]), y = Yc(hist[i][2]); if (i === 0) ctx.moveTo(x, y); else { ctx.lineTo(x, Yc(hist[i - 1][2])); ctx.lineTo(x, y); } }
  ctx.stroke();
  ctx.strokeStyle = TEAL; ctx.lineWidth = 2.2; ctx.beginPath();
  for (let i = 0; i < hist.length; i++){ const x = Xt(hist[i][0]), y = Yc(hist[i][1]); if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
  ctx.stroke();
  ctx.restore();
  ctx.save(); ctx.setLineDash([7, 4]); ctx.strokeStyle = RED; ctx.lineWidth = 1.8; ctx.beginPath(); ctx.moveTo(X0, Yc(P.fc)); ctx.lineTo(X1, Yc(P.fc)); ctx.stroke();
  ctx.setLineDash([2, 4]); ctx.strokeStyle = '#64748B'; ctx.lineWidth = 1.4; ctx.beginPath(); ctx.moveTo(X0, Yc(P.expected)); ctx.lineTo(X1, Yc(P.expected)); ctx.stroke(); ctx.restore();
  let x = X0 - 8; const y = 302;
  ctx.fillStyle = TEAL; ctx.fillRect(x, y - 2, 18, 4); x += 24; x += txt(ctx, 'Planta modular', x, y, {s:10.5, w:'700', c: TEAL}) + 16;
  ctx.fillStyle = NAVY; ctx.fillRect(x, y - 1.5, 18, 3); x += 24; x += txt(ctx, 'Unidad única', x, y, {s:10.5, w:'700', c: NAVY}) + 16;
  ctx.save(); ctx.setLineDash([7, 4]); ctx.strokeStyle = RED; ctx.lineWidth = 1.8; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 22, y); ctx.stroke(); ctx.restore(); x += 28;
  x += txt(ctx, 'Compromiso C_f = ' + esn(P.fc, 1) + ' MW (firme modular al ' + esn(100*P.alpha, 2).replace(/,?0+$/, '') + ' %)', x, y, {s:10.5, w:'700', c:'#B91C1C'}) + 16;
  ctx.save(); ctx.setLineDash([2, 4]); ctx.strokeStyle = '#64748B'; ctx.lineWidth = 1.4; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 22, y); ctx.stroke(); ctx.restore(); x += 28;
  txt(ctx, 'N·A·P_m', x, y, {s:10.5, w:'700', c:'#64748B'});
  if (P.fc <= 0){ const m = 'C_f = 0: con esta configuración no se puede garantizar potencia al nivel de confianza exigido', mw = tw(ctx, m, 11, '800') + 24;
    ctx.fillStyle = 'rgba(255,255,255,0.92)'; ctx.strokeStyle = '#FCA5A5'; ctx.lineWidth = 1; rrect(ctx, (X0 + X1)/2 - mw/2, (Y0 + Y1)/2 - 14, mw, 28, 8); ctx.fill(); ctx.stroke();
    txt(ctx, m, (X0 + X1)/2, (Y0 + Y1)/2, {a:'center', s:11, w:'800', c:'#B91C1C'}); }
}
function drawTable(){
  const x0 = 416, y0 = 318, w = 664, c1 = x0 + 428, c2 = x0 + 584;
  ctx.fillStyle = '#FFFFFF'; ctx.strokeStyle = '#E3EAF2'; ctx.lineWidth = 1; rrect(ctx, x0, y0, w, 148, 10); ctx.fill(); ctx.stroke();
  txt(ctx, 'Planta modular', c1, y0 + 18, {a:'center', s:11.5, w:'800', c: TEAL});
  txt(ctx, 'Unidad única', c2, y0 + 18, {a:'center', s:11.5, w:'800', c: NAVY});
  const pc = function(v){ return esn(100*v, 2) + ' %'; };
  const rows = [
    ['Tiempo con capacidad ≥ C_f (simulado)', simH ? pc(okM/simH) : '—', simH ? pc(okO/simH) : '—', null],
    ['Probabilidad teórica P(capacidad ≥ C_f)', pc(P.pM), pc(P.pO), null],
    ['Horas con déficit frente a C_f', esn(defM, 0) + ' h', esn(defO, 0) + ' h', null],
    ['Energía no suministrada frente a C_f', esn(ensM, 0) + ' MWh', esn(ensO, 0) + ' MWh', null]
  ];
  rows.forEach(function(r, i){
    const y = y0 + 44 + i*23;
    if (i % 2 === 0){ ctx.fillStyle = '#F6F9FC'; ctx.fillRect(x0 + 8, y - 11, w - 16, 22); }
    txt(ctx, r[0], x0 + 16, y, {s:11, w:'600', c: MUTED});
    txt(ctx, r[1], c1, y, {a:'center', s:11.5, w:'800', c: NAVY});
    txt(ctx, r[2], c2, y, {a:'center', s:11.5, w:'800', c: NAVY});
  });
  txt(ctx, 'Tiempo simulado ' + esn(simH, 0) + ' h (' + esn(simH/8760, 2) + ' años) · ' + esn(P.hps, 0) + ' h por segundo · clic para pausar', x0 + 16, y0 + 136, {s:10, w:'600', c:'#64748B'});
}
let frameAcc = 0;
function frame(now){
  if (!cv.isConnected) return;
  const dt = Math.min(0.05, (now - last)/1000); last = now;
  if (isHidden(cv)){ requestAnimationFrame(frame); return; }
  if (!paused){
    const dh = dt*P.hps, n = Math.max(1, Math.ceil(dh/4));
    for (let j = 0; j < n; j++) simulate(dh/n);
    for (let i = 0; i < N; i++) if (fl[i] > 0) fl[i] = Math.max(0, fl[i] - dt/0.2);
    if (flOne > 0) flOne = Math.max(0, flOne - dt/0.2);
  }
  ctx.clearRect(0, 0, W, H); ctx.fillStyle = '#F7FBFE'; ctx.fillRect(0, 0, W, H);
  txt(ctx, 'Simulación en vivo: módulos independientes vs una unidad del mismo tamaño total', 20, 22, {s:14.5, w:'800'});
  txt(ctx, 'Markov de 2 estados por unidad: falla con λ = 1/MTBF y se repara con μ = 1/MTTR · MTBF = ' + esn(P.mtbf, 0) + ' h · MTTR = ' + esn(P.mttr, 0) + ' h' + (P.assumed ? ' (supuesto)' : '') + ' · A = ' + esn(P.A, 3), 20, 44, {s:11, w:'600', c: MUTED});
  drawLeft(); drawChart(); drawTable();
  pauseBadge(ctx, W, H, paused);
  requestAnimationFrame(frame);
}
for (let j = 0; j < 400; j++) simulate(P.win/400);
simH = 0; okM = okO = defM = defO = ensM = ensO = failM = failO = 0;
const shift = hist.length ? hist[hist.length - 1][0] : 0;
hist.forEach(function(h){ h[0] -= shift; });
requestAnimationFrame(frame);
}
__BOOT__
})();
</script>
"""


def ucf_stream_animation_html(payload: dict) -> str:
    return render(_UCF_TEMPLATE, payload, "ucfa")


def fleet_animation_html(payload: dict) -> str:
    return render(_FLEET_TEMPLATE, payload, "fleet")
