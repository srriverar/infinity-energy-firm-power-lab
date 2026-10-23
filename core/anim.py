"""
core/anim.py — Animaciones en canvas HTML5 (sin recursos externos).

* `cycle_animation_html`: convertidor por flotabilidad GENÉRICO (esquema conceptual,
  no representa el diseño patentado de Infinity Energy).
* `render` + `JS_LIB`: infraestructura común para las demás animaciones
  (core/anim_physics.py y core/anim_value.py): se insertan con
  `st.html(..., unsafe_allow_javascript=True)`.
"""
from __future__ import annotations

import hashlib
import json
import re

_TEMPLATE = r"""
<div style="width:100%;font-family:Inter,Segoe UI,Roboto,Arial,sans-serif;">
<canvas id="cv___UID__" style="width:100%;max-width:1100px;height:auto;aspect-ratio:1100/600;display:block;margin:0 auto;border-radius:16px;background:#F7FBFE;border:1px solid #E3EAF2"></canvas>
</div>
<script>
(function(){
const P = __PARAMS__;
function run(cv){
const W = 1100, H = 600;
const dpr = Math.min(window.devicePixelRatio || 1, 2);
cv.width = W*dpr; cv.height = H*dpr;
const ctx = cv.getContext('2d'); ctx.scale(dpr, dpr);

// ---------------- geometría ----------------
const T = {x0:120, x1:360, yTop:40, ySurf:104, yBot:548};
const S = {cx:240, cyT:126, cyB:470, R:40};
const Lv = S.cyB - S.cyT, Ls = Math.PI*S.R, Lloop = 2*Lv + 2*Ls;
const nCups = 24, spacing = Lloop/nCups;
const fVis = Math.max(0.05, P.f_ins) * P.speed;          // inserciones visibles por segundo
const uPx = fVis * spacing;                              // velocidad de la cadena en px/s
const nozzle = {x: S.cx + S.R + 16, y: S.cyB + 34};
let sPos = 0, last = performance.now(), insAcc = 0, rotor = 0, dash = 0, tGlob = 0;
let bubbles = [], ripples = [];
const rnd = (a,b)=>a+Math.random()*(b-a);

function pressureRatioAt(y){ // p(z)/p0 a la altura de pantalla y
  const z = P.H * Math.min(1, Math.max(0, (y - T.ySurf)/(T.yBot - T.ySurf)));
  return 1 + (P.ratio - 1) * z / P.H;
}
function pathPoint(xi){
  xi = ((xi % Lloop) + Lloop) % Lloop;
  if (xi < Lv) return {x:S.cx+S.R, y:S.cyB-xi, tx:0, ty:-1, nx:1, ny:0, side:'up', xi:xi};
  let r = xi - Lv;
  if (r < Ls){ const th=r/S.R; return {x:S.cx+S.R*Math.cos(th), y:S.cyT-S.R*Math.sin(th), tx:-Math.sin(th), ty:-Math.cos(th), nx:Math.cos(th), ny:-Math.sin(th), side:'top', xi:xi}; }
  r -= Ls;
  if (r < Lv) return {x:S.cx-S.R, y:S.cyT+r, tx:0, ty:1, nx:-1, ny:0, side:'down', xi:xi};
  r -= Lv;
  const th=r/S.R; return {x:S.cx-S.R*Math.cos(th), y:S.cyB+S.R*Math.sin(th), tx:Math.sin(th), ty:Math.cos(th), nx:-Math.cos(th), ny:Math.sin(th), side:'bottom', xi:xi};
}
function cupPt(p,a,b){ return [p.x + a*p.tx + b*p.nx, p.y + a*p.ty + b*p.ny]; }

// ---------------- dibujo ----------------
function roundRect(x,y,w,h,r){ ctx.beginPath(); ctx.moveTo(x+r,y); ctx.arcTo(x+w,y,x+w,y+h,r); ctx.arcTo(x+w,y+h,x,y+h,r); ctx.arcTo(x,y+h,x,y,r); ctx.arcTo(x,y,x+w,y,r); ctx.closePath(); }
function label(t,x,y,opt){ opt=opt||{}; t=String(t).replace(/(\d)\.(\d)/g,'$1,$2'); ctx.font=(opt.w||'600')+' '+(opt.s||12)+'px Inter,Segoe UI,Arial'; ctx.fillStyle=opt.c||'#0B2A5B'; ctx.textAlign=opt.a||'left'; ctx.textBaseline=opt.b||'middle'; ctx.fillText(t,x,y); }
function fmtW(w){ const a=Math.abs(w); if(a>=1e6) return (w/1e6).toFixed(2)+' MW'; if(a>=1e3) return (w/1e3).toFixed(2)+' kW'; return w.toFixed(0)+' W'; }

function drawTower(){
  // agua con gradiente de presión
  const g = ctx.createLinearGradient(0,T.ySurf,0,T.yBot);
  g.addColorStop(0,'#C9EEFF'); g.addColorStop(0.5,'#5DB8EC'); g.addColorStop(1,'#0A4F8F');
  ctx.fillStyle = g; ctx.fillRect(T.x0, T.ySurf, T.x1-T.x0, T.yBot-T.ySurf);
  // aire sobre la superficie
  ctx.fillStyle = 'rgba(255,255,255,0.65)'; ctx.fillRect(T.x0, T.yTop, T.x1-T.x0, T.ySurf-T.yTop);
  // superficie ondulada
  ctx.strokeStyle='rgba(255,255,255,0.9)'; ctx.lineWidth=2; ctx.beginPath();
  for(let x=T.x0;x<=T.x1;x+=4){ const y=T.ySurf+2*Math.sin((x+tGlob*60)/18); if(x===T.x0) ctx.moveTo(x,y); else ctx.lineTo(x,y);} ctx.stroke();
  // paredes de acero
  ctx.strokeStyle='#7A8797'; ctx.lineWidth=6; roundRect(T.x0-3,T.yTop-3,T.x1-T.x0+6,T.yBot-T.yTop+6,10); ctx.stroke();
  ctx.strokeStyle='#B7C2CF'; ctx.lineWidth=1; for(let y=T.yTop+40;y<T.yBot;y+=55){ ctx.beginPath(); ctx.moveTo(T.x0-3,y); ctx.lineTo(T.x1+3,y); ctx.stroke(); }
  // eje de profundidad y presión
  ctx.strokeStyle='#94A3B8'; ctx.lineWidth=1; ctx.beginPath(); ctx.moveTo(T.x0-24,T.ySurf); ctx.lineTo(T.x0-24,T.yBot); ctx.stroke();
  for(let i=0;i<=4;i++){
    const y=T.ySurf+(T.yBot-T.ySurf)*i/4; ctx.beginPath(); ctx.moveTo(T.x0-30,y); ctx.lineTo(T.x0-18,y); ctx.stroke();
    label((P.H*i/4).toFixed(1)+' m', T.x0-34, y-7, {a:'right', s:11, c:'#5B6B80'});
    label((P.p0*(1+(P.ratio-1)*i/4)/1000).toFixed(0)+' kPa', T.x0-34, y+7, {a:'right', s:10, w:'500', c:'#0A5FA8'});
  }
  label('profundidad / presión', T.x0-112, T.ySurf-22, {s:10, w:'600', c:'#5B6B80'});
}

function drawChain(){
  ctx.strokeStyle='#334155'; ctx.lineWidth=3;
  ctx.beginPath(); ctx.moveTo(S.cx+S.R,S.cyB); ctx.lineTo(S.cx+S.R,S.cyT); ctx.arc(S.cx,S.cyT,S.R,0,Math.PI,true);
  ctx.lineTo(S.cx-S.R,S.cyB); ctx.arc(S.cx,S.cyB,S.R,Math.PI,0,true); ctx.stroke();
  [S.cyT,S.cyB].forEach(cy=>{
    ctx.fillStyle='#CBD5E1'; ctx.beginPath(); ctx.arc(S.cx,cy,S.R-6,0,2*Math.PI); ctx.fill();
    ctx.strokeStyle='#475569'; ctx.lineWidth=2; ctx.stroke();
    const ang = sPos/S.R;
    for(let k=0;k<6;k++){ const a=ang+k*Math.PI/3; ctx.beginPath(); ctx.moveTo(S.cx,cy); ctx.lineTo(S.cx+(S.R-8)*Math.cos(a), cy-(S.R-8)*Math.sin(a)); ctx.stroke(); }
    ctx.fillStyle='#334155'; ctx.beginPath(); ctx.arc(S.cx,cy,5,0,2*Math.PI); ctx.fill();
  });
}

function drawCups(){
  for(let k=0;k<nCups;k++){
    const p = pathPoint(k*spacing + sPos);
    const a0=-9, a1=9, b0=4, b1=27;
    // aire atrapado (lado ascendente): crece con la altura (ley de Boyle)
    if (p.side==='up' && p.y < S.cyB-6){
      const frac = Math.min(1, P.eta_cap * pressureRatioAt(S.cyB) / pressureRatioAt(p.y) / P.ratio * 1.0 + 0.0);
      const fr = Math.max(0.12, Math.min(1, frac));
      const c1=cupPt(p,a1-18*fr,b0+1), c2=cupPt(p,a1,b0+1), c3=cupPt(p,a1,b1-1), c4=cupPt(p,a1-18*fr,b1-1);
      ctx.fillStyle='rgba(255,255,255,0.95)'; ctx.beginPath(); ctx.moveTo(c1[0],c1[1]); ctx.lineTo(c2[0],c2[1]); ctx.lineTo(c3[0],c3[1]); ctx.lineTo(c4[0],c4[1]); ctx.closePath(); ctx.fill();
    }
    // contorno del cangilón (abierto hacia atrás)
    const q1=cupPt(p,a0,b0), q2=cupPt(p,a1,b0), q3=cupPt(p,a1,b1), q4=cupPt(p,a0,b1);
    ctx.strokeStyle = p.side==='up' ? '#0B2A5B' : '#1E3A5F'; ctx.lineWidth=2.2;
    ctx.beginPath(); ctx.moveTo(q1[0],q1[1]); ctx.lineTo(q2[0],q2[1]); ctx.lineTo(q3[0],q3[1]); ctx.lineTo(q4[0],q4[1]); ctx.stroke();
  }
}

function spawnInsertion(){
  bubbles.push({x:nozzle.x, y:nozzle.y, vy:-90*P.speed, r:4+5*Math.cbrt(P.V0_L/20)/Math.cbrt(P.ratio), life:0, kind:'ins', ttl:0.42/Math.max(P.speed,0.5)});
  if (Math.random() < (1-P.eta_cap)){
    for(let i=0;i<3;i++) bubbles.push({x:nozzle.x+rnd(-6,10), y:nozzle.y-rnd(10,30), vy:-rnd(150,210)*Math.sqrt(P.speed), r:rnd(1.5,3), life:0, kind:'slip', ttl:99});
  }
}
function spawnRelease(){
  for(let i=0;i<4;i++) bubbles.push({x:S.cx+S.R+rnd(6,26), y:T.ySurf+rnd(4,18), vy:-rnd(30,60), r:rnd(2,4), life:0, kind:'rel', ttl:0.5});
  ripples.push({x:S.cx+S.R+16, r:3, a:0.8});
}

function drawBubbles(dt){
  bubbles.forEach(b=>{
    b.life += dt; b.y += b.vy*dt;
    if (b.kind==='slip'){ b.x += Math.sin((b.life+b.y)/9)*0.4; }
    const grow = b.kind==='slip' ? Math.cbrt(P.ratio / pressureRatioAt(b.y)) : 1;
    const r = b.r*grow;
    ctx.fillStyle='rgba(255,255,255,0.85)'; ctx.strokeStyle='rgba(255,255,255,1)'; ctx.lineWidth=1;
    ctx.beginPath(); ctx.arc(b.x,b.y,r,0,2*Math.PI); ctx.fill(); ctx.stroke();
    if (b.kind==='slip' && b.y <= T.ySurf+2){ b.ttl=0; ripples.push({x:b.x, r:2, a:0.6}); }
  });
  bubbles = bubbles.filter(b=> b.life < b.ttl && b.y > T.yTop);
  ripples.forEach(r=>{ r.r += 30*dt; r.a -= 0.9*dt; ctx.strokeStyle='rgba(255,255,255,'+Math.max(r.a,0)+')'; ctx.lineWidth=1.5; ctx.beginPath(); ctx.ellipse(r.x,T.ySurf,r.r,r.r*0.3,0,0,2*Math.PI); ctx.stroke(); });
  ripples = ripples.filter(r=>r.a>0);
}

function flowLine(pts, color, speed, width, labelTxt, lx, ly){
  ctx.save(); ctx.strokeStyle=color; ctx.lineWidth=width; ctx.setLineDash([10,8]); ctx.lineDashOffset=-dash*speed;
  ctx.beginPath(); ctx.moveTo(pts[0][0],pts[0][1]); for(let i=1;i<pts.length;i++) ctx.lineTo(pts[i][0],pts[i][1]); ctx.stroke(); ctx.restore();
  if (labelTxt) label(labelTxt, lx, ly, {s:11.5, w:'700', c:color});
}
function box(x,y,w,h,title,sub,fill,stroke){
  ctx.fillStyle=fill||'#FFFFFF'; ctx.strokeStyle=stroke||'#94A3B8'; ctx.lineWidth=1.5; roundRect(x,y,w,h,10); ctx.fill(); ctx.stroke();
  label(title, x+w/2, y+(sub?h/2-8:h/2), {a:'center', s:13, w:'800'}); if(sub) label(sub, x+w/2, y+h/2+9, {a:'center', s:10.5, w:'500', c:'#5B6B80'});
}
function meter(x,y,txt,color){
  ctx.fillStyle='#fff'; ctx.strokeStyle=color; ctx.lineWidth=2; ctx.beginPath(); ctx.arc(x,y,13,0,2*Math.PI); ctx.fill(); ctx.stroke();
  label(txt, x, y, {a:'center', s:10, w:'800', c:color});
}

function drawPlant(dt){
  // eje y transmisión
  ctx.strokeStyle='#475569'; ctx.lineWidth=5; ctx.beginPath(); ctx.moveTo(S.cx,S.cyT); ctx.lineTo(395,S.cyT); ctx.stroke();
  box(395, S.cyT-24, 72, 48, 'KEM', 'eje / caja', '#F1F5F9', '#64748B');
  ctx.strokeStyle='#475569'; ctx.lineWidth=4; ctx.beginPath(); ctx.moveTo(467,S.cyT); ctx.lineTo(500,S.cyT); ctx.stroke();
  // generador
  const gx=535, gy=S.cyT;
  ctx.fillStyle='#E2E8F0'; ctx.strokeStyle='#334155'; ctx.lineWidth=2; ctx.beginPath(); ctx.arc(gx,gy,34,0,2*Math.PI); ctx.fill(); ctx.stroke();
  rotor += dt * Math.min(P.rpm_gen, 900)/60 * 2*Math.PI * 0.08 * P.speed;
  ctx.strokeStyle='#0098D4'; ctx.lineWidth=4; for(let k=0;k<3;k++){ const a=rotor+k*2*Math.PI/3; ctx.beginPath(); ctx.moveTo(gx,gy); ctx.lineTo(gx+24*Math.cos(a), gy+24*Math.sin(a)); ctx.stroke(); }
  ctx.fillStyle='#0B2A5B'; ctx.beginPath(); ctx.arc(gx,gy,5,0,2*Math.PI); ctx.fill();
  label('Generador', gx, gy+48, {a:'center', s:11, w:'700'});
  // PDU
  ctx.strokeStyle='#475569'; ctx.lineWidth=3; ctx.beginPath(); ctx.moveTo(569,S.cyT); ctx.lineTo(610,S.cyT); ctx.stroke();
  box(610, S.cyT-30, 100, 60, 'PDU', 'conversión · red', '#ECFDF5', '#0FA99A');
  // carga / red
  box(930, 62, 145, 96, 'Carga / Red', 'frontera de medición', '#FFFFFF', '#0B2A5B');
  // salida útil
  const yo = S.cyT - 6;
  const sp = 0.6 + Math.log10(1+Math.abs(P.P_out))/2;
  flowLine([[710,yo],[930,yo]], '#0FA99A', sp, 4, 'Salida útil  ' + fmtW(P.P_out), 770, yo-14);
  meter(870, yo, 'M2', '#0FA99A');
  // ABIS
  box(430, 478, 120, 58, 'ABIS', 'inserción de aire', '#FFF7ED', '#F59E0B');
  ctx.save(); ctx.strokeStyle='#94A3B8'; ctx.lineWidth=4; ctx.setLineDash([6,5]); ctx.lineDashOffset=dash*1.2;
  ctx.beginPath(); ctx.moveTo(430,522); ctx.lineTo(T.x1+6,522); ctx.lineTo(nozzle.x+22, nozzle.y+12); ctx.lineTo(nozzle.x, nozzle.y); ctx.stroke(); ctx.restore();
  ctx.fillStyle='#64748B'; ctx.beginPath(); ctx.arc(nozzle.x,nozzle.y,4,0,2*Math.PI); ctx.fill();
  label('aire', 392, 536, {s:10.5, w:'600', c:'#64748B'});
  // entrada eléctrica del ABIS
  const sp2 = 0.6 + Math.log10(1+Math.abs(P.P_abis))/2;
  if (P.closed_loop){
    ctx.fillStyle='#0FA99A'; ctx.beginPath(); ctx.arc(745,yo,5,0,2*Math.PI); ctx.fill();
    flowLine([[745,yo],[745,492],[550,492]], '#F59E0B', sp2, 4, '', 0, 0);
    label('Recirculación al ABIS  ' + fmtW(Math.min(P.P_abis, P.P_out)), 560, 478, {s:11, w:'700', c:'#B45309'});
    if (P.P_net < 0){
      flowLine([[1040,158],[1040,520],[550,520]], '#E5484D', sp2, 3, 'Déficit suministrado por la red  ' + fmtW(-P.P_net), 770, 536);
    } else {
      label('Excedente neto exportado  ' + fmtW(P.P_net), 770, 536, {s:12, w:'800', c:'#16A34A'});
    }
  } else {
    flowLine([[1040,158],[1040,520],[550,520]], '#F59E0B', sp2, 4, 'Entrada ABIS desde la red  ' + fmtW(P.P_abis), 770, 536);
  }
  meter(960, 520, 'M1', '#F59E0B');
  // CMS + auxiliares
  box(600, 404, 120, 54, 'CMS', 'control · datos', '#EEF2FF', '#7C3AED');
  ctx.save(); ctx.strokeStyle='#7C3AED'; ctx.lineWidth=1.1; ctx.setLineDash([3,4]);
  [[S.cx+S.R+34, S.cyB-40],[gx,gy+34],[660,S.cyT+30],[490,478]].forEach(pt=>{ ctx.beginPath(); ctx.moveTo(630,404); ctx.lineTo(pt[0],pt[1]); ctx.stroke(); });
  ctx.restore();
  flowLine([[1062,158],[1062,431],[720,431]], '#7C3AED', 0.7, 2, 'Auxiliares ' + fmtW(P.P_aux), 790, 446);
  meter(990, 431, 'M3', '#7C3AED');
  if (P.dT > 0.05){
    ctx.fillStyle='rgba(229,72,77,0.14)'; ctx.fillRect(T.x0, T.ySurf, 10, T.yBot-T.ySurf);
    label('aporte térmico ΔT = '+P.dT.toFixed(1)+' K', T.x0+14, T.yBot-12, {s:10.5, w:'800', c:'#FFFFFF'});
  }
}

function drawPanel(){
  const x=768, y=180, w=255, h=228;
  ctx.fillStyle='rgba(255,255,255,0.97)'; ctx.strokeStyle='#E3EAF2'; ctx.lineWidth=1; roundRect(x,y,w,h,12); ctx.fill(); ctx.stroke();
  label('Lecturas del modelo (régimen)', x+14, y+18, {s:12, w:'800'});
  const rows = [
    ['Entrada total (ABIS + aux)', fmtW(P.P_in)],
    ['Salida eléctrica útil', fmtW(P.P_out)],
    ['Balance neto', fmtW(P.P_net)],
    ['Inserciones', P.f_ins.toFixed(2)+' Hz · '+P.V0_L.toFixed(0)+' L'],
    ['pH/p0 · W flotación', P.ratio.toFixed(3)+' · '+(P.W_b).toFixed(0)+' J'],
  ];
  rows.forEach((r,i)=>{ label(r[0], x+14, y+40+i*19, {s:11, w:'500', c:'#5B6B80'}); label(r[1], x+w-14, y+40+i*19, {s:11.5, w:'800', a:'right', c: (i===2 ? (P.P_net>=0?'#16A34A':'#E5484D') : '#0B2A5B')}); });
  const gx = x+w/2, gy = y+h-30, R=44;
  ctx.lineWidth=10; ctx.lineCap='round';
  const a0=Math.PI, a1=2*Math.PI, maxv=1.5;
  ctx.strokeStyle='#E2E8F0'; ctx.beginPath(); ctx.arc(gx,gy,R,a0,a1); ctx.stroke();
  const v=Math.max(0,Math.min(maxv,P.ERR));
  ctx.strokeStyle= P.ERR>=1 ? '#16A34A' : '#0098D4'; ctx.beginPath(); ctx.arc(gx,gy,R,a0,a0+(a1-a0)*v/maxv); ctx.stroke();
  ctx.lineCap='butt';
  const am=a0+(a1-a0)*1/maxv; ctx.strokeStyle='#0B2A5B'; ctx.lineWidth=2; ctx.beginPath(); ctx.moveTo(gx+(R-10)*Math.cos(am), gy+(R-10)*Math.sin(am)); ctx.lineTo(gx+(R+9)*Math.cos(am), gy+(R+9)*Math.sin(am)); ctx.stroke();
  label('1', gx+(R+16)*Math.cos(am), gy+(R+16)*Math.sin(am), {a:'center', s:10.5, w:'800'});
  label('ERR = '+P.ERR.toFixed(3), gx, gy-8, {a:'center', s:16, w:'800'});
  label('E_salida / E_entrada', gx, gy+12, {a:'center', s:9.5, w:'600', c:'#5B6B80'});
}

function tag(t, x, y, color){
  ctx.font='700 11px Inter,Segoe UI,Arial'; const w = ctx.measureText(t).width + 14;
  ctx.fillStyle='rgba(255,255,255,0.92)'; ctx.strokeStyle='#E3EAF2'; ctx.lineWidth=1; roundRect(x, y-11, w, 22, 8); ctx.fill(); ctx.stroke();
  label(t, x+7, y, {s:11, w:'700', c:color||'#0B2A5B'});
}

function frame(now){
  if (!cv.isConnected) return;
  const dt = Math.min(0.05, (now-last)/1000); last = now; tGlob += dt; dash += dt*40;
  const prev = sPos; sPos += uPx*dt;
  // eventos: inserción (paso por la base del lado ascendente) y liberación en la superficie
  for(let k=0;k<nCups;k++){
    const a = ((k*spacing+prev)%Lloop+Lloop)%Lloop, b = ((k*spacing+sPos)%Lloop+Lloop)%Lloop;
    if (b < a) spawnInsertion();
    if (a < Lv && b >= Lv) spawnRelease();
  }
  ctx.clearRect(0,0,W,H);
  ctx.fillStyle='#F7FBFE'; ctx.fillRect(0,0,W,H);
  drawTower(); drawChain(); drawCups(); drawBubbles(dt); drawPlant(dt); drawPanel();
  label(P.title, 20, 22, {s:14, w:'800'});
  label('Esquema conceptual genérico · no representa el diseño patentado · animación ×'+P.speed.toFixed(1), 20, H-14, {s:10.5, w:'500', c:'#64748B'});
  if (P.labels){
    tag('↑ ascenso: aire atrapado en cangilones', 378, 214, '#0B2A5B');
    tag('   el volumen crece al subir (Boyle)', 378, 240, '#0A5FA8');
    tag('↓ descenso: cangilones con agua', 378, 266, '#334155');
    tag('burbujas libres = aire no capturado', 378, 292, '#64748B');
  }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
}
(function boot(a){
  const c = document.getElementById('cv___UID__');
  if (!c) { if (a < 600) setTimeout(function(){ boot(a+1); }, 50); return; }
  if (c.dataset.started) return;
  c.dataset.started = '1';
  run(c);
})(0);
})();
</script>
"""


def _dompurify_safe(html: str) -> str:
    """DOMPurify elimina <script> cuyo texto contiene '<' seguido de letra/dígito/'/'
    (protección mXSS). Se separan esas comparaciones para conservar el script intacto."""
    head, rest = html.split("<script>", 1)
    js, tail = rest.split("</script>", 1)
    js = re.sub(r"<(?=[\w/])", "< ", js)
    return f"{head}<script>{js}</script>{tail}"


def cycle_animation_html(params: dict) -> str:
    payload = json.dumps(params, sort_keys=True).replace("<", "\\u003c")
    uid = hashlib.md5(payload.encode()).hexdigest()[:10]
    return _dompurify_safe(_TEMPLATE.replace("__PARAMS__", payload).replace("__UID__", uid))


# -----------------------------------------------------------------------------
# Infraestructura común para las animaciones adicionales
# -----------------------------------------------------------------------------
JS_LIB = r"""
const DPR = Math.min(window.devicePixelRatio || 1, 2);
const FONT = 'Inter,Segoe UI,Roboto,Arial,sans-serif';
function setupCanvas(cv, W, H){ cv.width = W*DPR; cv.height = H*DPR; const c = cv.getContext('2d'); c.setTransform(DPR,0,0,DPR,0,0); return c; }
function rrect(c, x, y, w, h, r){ r = Math.max(0, Math.min(r, w/2, h/2)); c.beginPath(); c.moveTo(x+r,y); c.arcTo(x+w,y,x+w,y+h,r); c.arcTo(x+w,y+h,x,y+h,r); c.arcTo(x,y+h,x,y,r); c.arcTo(x,y,x+w,y,r); c.closePath(); }
function esn(v, d){
  if (!isFinite(v)) return '—';
  d = (d === undefined) ? 0 : d;
  const neg = v < 0 && Math.abs(v) >= 0.5*Math.pow(10, -d);
  const parts = Math.abs(v).toFixed(d).split('.');
  let ip = parts[0];
  if (ip.length > 3) ip = ip.replace(/\B(?=(\d{3})+(?!\d))/g, '\u202f');
  return (neg ? '−' : '') + ip + (parts[1] ? ',' + parts[1] : '');
}
function fmtW(w){ const a = Math.abs(w); if (a >= 1e6) return esn(w/1e6, 2) + ' MW'; if (a >= 1e3) return esn(w/1e3, 2) + ' kW'; return esn(w, 0) + ' W'; }
function txt(c, t, x, y, o){ o = o || {}; t = String(t).replace(/(\d)\.(\d)/g, '$1,$2'); c.font = (o.w || '600') + ' ' + (o.s || 12) + 'px ' + FONT; c.fillStyle = o.c || '#0B2A5B'; c.textAlign = o.a || 'left'; c.textBaseline = o.b || 'middle'; c.fillText(t, x, y); return c.measureText(t).width; }
function tw(c, t, s, w){ c.font = (w || '600') + ' ' + (s || 12) + 'px ' + FONT; return c.measureText(String(t)).width; }
function clamp(v, a, b){ return Math.max(a, Math.min(b, v)); }
function lerp(a, b, t){ return a + (b - a)*t; }
function ease(t){ t = clamp(t, 0, 1); return t*t*(3 - 2*t); }
function isHidden(cv){ return cv.offsetParent === null; }
function chip(c, t, x, y, bg, fg, s){ s = s || 11; const w = tw(c, t, s, '700') + 16; c.fillStyle = bg; rrect(c, x, y - 11, w, 22, 11); c.fill(); txt(c, t, x + 8, y, {s: s, w: '700', c: fg}); return w; }
function pauseBadge(c, W, H, paused){
  if (!paused) return;
  c.fillStyle = 'rgba(11,42,91,0.80)'; rrect(c, W/2 - 120, 10, 240, 28, 14); c.fill();
  txt(c, '❚❚  En pausa · clic para continuar', W/2, 24, {a: 'center', s: 12, w: '700', c: '#FFFFFF'});
}
function hatchPattern(c, color, bg){
  const k = document.createElement('canvas'); const n = 10; k.width = n*DPR; k.height = n*DPR;
  const g = k.getContext('2d'); g.scale(DPR, DPR);
  if (bg){ g.fillStyle = bg; g.fillRect(0, 0, n, n); }
  g.strokeStyle = color; g.lineWidth = 1.4;
  [[0, n, n, 0], [-n/2, n/2, n/2, -n/2], [n/2, 3*n/2, 3*n/2, n/2]].forEach(function(s){ g.beginPath(); g.moveTo(s[0], s[1]); g.lineTo(s[2], s[3]); g.stroke(); });
  const pat = c.createPattern(k, 'repeat');
  if (pat && pat.setTransform && window.DOMMatrix) pat.setTransform(new DOMMatrix([1/DPR, 0, 0, 1/DPR, 0, 0]));
  return pat;
}
function wrap(c, t, x, y, maxW, lh, o){
  o = o || {}; const words = String(t).split(' '); let line = '', yy = y;
  for (let i = 0; i < words.length; i++){
    const test = line ? line + ' ' + words[i] : words[i];
    if (line && tw(c, test, o.s, o.w) > maxW){ txt(c, line, x, yy, o); line = words[i]; yy += lh; } else { line = test; }
  }
  if (line) txt(c, line, x, yy, o);
  return yy;
}
function gauss(){ let u = 0, v = 0; while (u === 0) u = Math.random(); while (v === 0) v = Math.random(); return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v); }
function erf(x){ const s = x >= 0 ? 1 : -1; x = Math.abs(x); const t = 1/(1 + 0.3275911*x);
  const y = 1 - (((((1.061405429*t - 1.453152027)*t) + 1.421413741)*t - 0.284496736)*t + 0.254829592)*t*Math.exp(-x*x); return s*y; }
function Phi(z){ return 0.5*(1 + erf(z/Math.SQRT2)); }
"""

_BOOT = r"""
(function boot(a){
  const c = document.getElementById('__CID__');
  if (!c) { if (a < 600) setTimeout(function(){ boot(a+1); }, 50); return; }
  if (c.dataset.started) return;
  c.dataset.started = '1';
  run(c);
})(0);
"""


def render(template: str, params: dict, prefix: str) -> str:
    """Inserta parámetros, biblioteca JS y arranque en una plantilla de animación.

    La plantilla debe contener `__PARAMS__`, `__JSLIB__`, `__BOOT__` y un canvas con
    id="__CID__"; la función JS `run(cv)` recibe el canvas.
    """
    payload = json.dumps(params, sort_keys=True).replace("<", "\\u003c")
    uid = hashlib.md5((prefix + payload).encode()).hexdigest()[:10]
    cid = f"{prefix}_{uid}"
    html = (template.replace("__JSLIB__", JS_LIB).replace("__BOOT__", _BOOT)
            .replace("__PARAMS__", payload).replace("__CID__", cid))
    return _dompurify_safe(html)
