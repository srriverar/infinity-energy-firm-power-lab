# Nota técnica — Firm Power Lab

*Plataforma de evaluación científica para la Convocatoria de Expresiones de Interés de Infinity Energy.*
Versión 1.0 · octubre de 2026 · Idioma de la interfaz: español.

## 0. Alcance y postura

Esta nota documenta los modelos implementados. Su propósito no es certificar ni refutar la tecnología, sino:
(i) fijar **cotas de primeros principios**; (ii) cuantificar el **valor sistémico** que tendría una fuente firme y
modular si se valida; y (iii) diseñar un **protocolo de validación falsable** para los MVP.
Todos los parámetros del módulo Infinity Energy (IE) son supuestos de escenario. El esquema físico es genérico y no
representa el diseño patentado.

---

## 1. Modelo físico del ciclo

**Hidrostática.** $p(z)=p_0+\rho g z$, con $p_0$ por altitud (ISA) y $\rho(T)$ del agua dulce.
Razón de presiones $r=p_H/p_0$.

**Aire por inserción.** $V_0$ (litros a $p_0$, $T_a$). A profundidad: $V_H=V_0\,(p_0/p_H)(T_w/T_a)$.

**Trabajo de flotación** (ascenso cuasiestático e isotérmico a $T_w$):

$$W_{flot}=\int_0^H\rho g V(z)\,dz=\int_{p_0}^{p_H}V\,dp=\frac{T_w}{T_a}\,p_0V_0\ln r .$$

**Trabajo de inserción** (flujo estacionario, ideal): isotérmico $W_{iso}=p_0V_0\ln r$; politrópico/adiabático
$W_n=\frac{n}{n-1}p_0V_0\left[r^{(n-1)/n}-1\right]$. Real: $W_c=W_n/\eta_c$; eléctrico $E_{ins}=W_c/\eta_m$.

**Cadena de conversión.** $W_{out}=\eta_{cap}\,\eta_t\,\eta_g\,\eta_{pe}\,W_{flot}$.
Potencias: $P_{in}=fE_{ins}+P_{aux}$, $P_{out}=fW_{out}$.

**Indicador en frontera completa.**

$$\mathrm{ERR}=\frac{E_{salida\ útil}}{E_{ABIS}+E_{aux}-\Delta E_{alm}} .$$

**Teorema de la frontera.** Con $T_w=T_a$ y compresión isotérmica reversible, $W_{flot}=W_{iso}$ para todo $H$ y
$V_0$. Toda irreversibilidad reduce el cociente, luego en un ciclo cerrado sin flujo energético adicional
$\mathrm{ERR}\le 1$ (primera y segunda ley). El ascenso equivale a una expansión entre $p_H$ y $p_0$; la inserción, a
una compresión. Un cuerpo rígido de volumen $V_0$ produciría $\rho gHV_0$ pero exigiría el mismo trabajo de inserción.
Verificado numéricamente con 2 000 combinaciones aleatorias de parámetros (`tests/test_core.py`).

**Hipótesis de aporte térmico.** Si $T_w>T_a$ (calor externo), $\mathrm{ERR}_{ideal}=T_w/T_a$ y la eficiencia
térmica está acotada por Carnot $1-T_a/T_w$. Con componentes de clase mundial ($\eta$ total ≈ 0,82) el equilibrio
requeriría $\Delta T\approx 65$ K.

**Dinámica electromecánica.** Referida al eje principal:

$$J_{eq}\dot\omega=T_{flot}(t)-\tfrac12\rho C_dA\,u^2N_{sum}\,r_s-(T_c\tanh(\omega/\omega_0)+b\omega)-T_e(\omega),\qquad J_{eq}=J_m+G^2(J_g+J_{vol}).$$

Cangilones discretos (paso $s$) que se llenan al pasar por el punto de inserción (consumo $E_{ins}$ por evento) y se
vacían en superficie; derrame si $V(z)>V_b$. Generador equivalente con FEM $K_e\omega_g$, resistencia $R_s$ y carga
$R$. El modelo reproduce el **sesgo por energía almacenada**: con cangilones precargados, el ERR acumulado de los
primeros segundos puede superar 1 aunque el régimen sea $\approx 0{,}4$.

---

## 2. Funciones de costo de incertidumbre (UCF)

Para potencia disponible aleatoria $W$ (PDF $f_W$, CDF $F_W$) y potencia programada $W_s$:

$$C_u=c_u\,\mathbb E[(W-W_s)^+],\qquad C_o=c_o\,\mathbb E[(W_s-W)^+],\qquad \mathrm{UCF}=C_u+C_o .$$

**Marginal y convexidad.** $\mathrm{MUCF}=(c_u+c_o)F_W(W_s)-c_u$; $\mathrm{UCF}''=(c_u+c_o)f_W\ge0$.
**Óptimo (cuantil crítico):** $W_s^*=F_W^{-1}\!\big(c_u/(c_u+c_o)\big)$ (cuantil generalizado si hay masas puntuales).
Identidad usada: $(w-W)^+=(w-W)+(W-w)^+$.

**Modelos y formas cerradas** (momentos parciales $M_k(a,b)=\int_a^b x^kf(x)\,dx$):

| Recurso | Variable primaria | Curva de potencia | Momento parcial |
|---|---|---|---|
| FV | irradiancia log-normal $(\mu,\sigma)$ | cuadrática bajo $R_c$, lineal hasta $G_{std}$, saturada | $e^{k\mu+k^2\sigma^2/2}[\Phi(\cdot)]_a^b$ |
| Eólica | viento Weibull $(k,c)$; $k=2$ Rayleigh | 0 / lineal $v_{in}$–$v_r$ / nominal / corte | $c^n\Gamma(1+n/k)[P(1+n/k,(x/c)^k)]_a^b$ |
| PCH filo de agua | caudal Gumbel (máximos) | $P=\rho g h\eta_t\eta_g\eta_c Q$ saturada | con integral exponencial $E_1$ |
| VE / carga controlable | Normal | identidad | $(\mu-w)(1-\Phi)+\sigma\phi$ |
| Planta modular (IE) | $K\sim\mathrm{Bin}(N,A)$ módulos disponibles × Normal recortada | suma | mezcla de normales |
| Uniforme | $U(a,b)$ | identidad | $(b-w)^2/2(b-a)$ |

**Verificación.** Analítico vs cuadratura adaptativa: error < $10^{-4}$ relativo; vs Monte Carlo (200 000 muestras):
< 2 %. El método analítico es órdenes de magnitud más rápido, lo que permite usarlo dentro de despachos y flujos
óptimos.

**Costo de incertidumbre nivelado.** $\mathrm{UCF}^*/\mathbb E[W]$ (USD/MWh), comparable entre tecnologías.

**Despacho económico con UCF.** $\min\sum_i(a_i+b_iP_i+c_iP_i^2)+\sum_j[d_jW_j+\mathrm{UCF}_j(W_j)]$ s.a.
$\sum P+\sum W=D$. KKT: $b_i+2c_iP_i=\lambda$; $d_j+(c_u+c_o)F_j(W_j)-c_u=\lambda\Rightarrow
W_j=F_j^{-1}((\lambda-d_j+c_u)/(c_u+c_o))$. Se resuelve por bisección en $\lambda$.
*Nota:* si $c_o<\lambda$, conviene programar los recursos variables a su máximo; en la práctica la penalización de
sobreestimación (reserva + desvío) supera el precio marginal, por eso el valor por defecto es $c_o=300$ USD/MWh.

**Aproximación cuadrática** $\mathrm{UCF}\approx\alpha+\beta W+\gamma W^2$ por mínimos cuadrados (compatible con QP).

**Horizonte de pronóstico.** Recursos variables: $\sigma(\tau)=\sigma_{DA}\sqrt{\tau/24}$. Planta modular: probabilidad
de falla durante $\tau$ con Markov de dos estados, $P_f(\tau)=\frac{\lambda}{\lambda+\mu}(1-e^{-(\lambda+\mu)\tau})$.

---

## 3. Confiabilidad

**COPT binomial** para $N$ módulos idénticos de disponibilidad $A=\mathrm{MTBF}/(\mathrm{MTBF}+\mathrm{MTTR})$.
**Capacidad firme** al nivel $\alpha$: $\max\{kP_m:\ P(K\ge k)\ge\alpha\}$.
**ELCC (Garver, 1966):**
$\mathrm{ELCC}=m\ln\frac{\sum_te^{(L_t-L_p)/m}}{\sum_te^{(L_t-L_p)/m}\,\mathbb E[e^{-X_t/m}]}$, con
$\mathbb E[e^{-X/m}]_{IE}=[(1-A)+Ae^{-P_m/m}]^N$. Para una unidad: $\mathrm{ELCC}=C-m\ln(1-q+qe^{C/m})$.
Aplicado al perfil reconstruido del 14-jun-2026 (ilustrativo; un estudio formal requiere años de datos).

---

## 4. Metrología y regla de decisión

- **Canales:** especificaciones como límites rectangulares ($u=a/\sqrt3$): medidor, relación de TC/TT, desfase × $\tan\varphi$,
  armónicos/ancho de banda.
- **Cociente:** $(u_{ERR}/ERR)^2=u_o^2+u_i^2-2r\,u_ou_i$.
- **Tipo A:** desviación entre ventanas / $\sqrt{n_{ef}}$ con $n_{ef}=n(1-\rho_1)/(1+\rho_1)$.
- **Decisión (aceptación protegida):** se declara $\mathrm{ERR}>1$ solo si $\mathrm{ERR}-U>1$, $U=2u_c$.
- **Potencia estadística:** $n\ge\sigma_w^2/[(\delta/(z_{1-\alpha}+z_{1-\beta}))^2-u_B^2]$; si el denominador es ≤ 0, la
  incertidumbre sistemática impide detectar $\delta$ con cualquier número de repeticiones.
- **Almacenamientos:** exergía de depósito $V[p\ln(p/p_0)-(p-p_0)]$; volante $\tfrac12J\omega^2$; baterías por SoC.
- **Autosostenimiento:** duración mínima $t\ge k\,E_{almacenable}/P_{neta}$.

---

## 5. Tecno-economía

$\mathrm{LCOE}=\frac{\mathrm{CAPEX}\cdot\mathrm{CRF}+\mathrm{O\&M}_{fijo}}{8{,}76\,CF}+\mathrm{O\&M}_{var}$,
$\mathrm{CRF}=\frac{r(1+r)^n}{(1+r)^n-1}$. CAPEX de equilibrio despejando el LCOE objetivo (incluido el costo de
incertidumbre). FV+BESS firme: dimensionamiento diario periódico con perfil FV sintético y días de autonomía.
Térmica de alquiler CR: $\approx$ USD 320 M / (273 MW × 2,5 años) ≈ 469 USD/kW-año + combustible.

---

## 6. Datos

- `data/cr_despacho_2026-06-14_reconstruido.csv`: digitalización por color del gráfico DOCSE-ICE mostrado en el video
  (15 min; error estimado ±15–25 MW por banda; geotermia fija; sin importaciones). Energía diaria ≈ 35,7 GWh,
  coherente con el promedio 2025 (35,6 GWh/día).
- Cifras de contexto: capacidad 2025 (3 658,6 MW), demanda 2025 (12 995 GWh), pico histórico 2 040,9 MW (29-jun-2026),
  273 MW térmicos de alquiler 2027–2029, Moín IV 200 MW (2029).

## 7. Animaciones: qué se calcula en el navegador

Las animaciones reciben de Python valores ya calculados por los mismos modelos de las páginas; el navegador solo
interpola, muestrea y dibuja (canvas HTML5 autocontenido, sin recursos externos).

- **Ciclo p–V (Física).** Estados del ciclo ideal: 1 $(V_0,p_0,T_a)$ → 2 compresión $pV^k=\text{cte}$ ($k=1$, $n$ o
  $\gamma$) → 3 equilibrio isobárico con el agua a $p_H$, $V_3=V_0\frac{p_0}{p_H}\frac{T_w}{T_a}$ → 4 ascenso isotérmico a
  $T_w$, $V_4=V_0T_w/T_a$ → liberación a $p_0$. Las áreas sombreadas son $\int V\,dp$ sobre cada curva y coinciden con
  `W_comp_ideal` y `W_buoy` del modelo (`tests/test_anim.py`). Su cociente es la cota del ciclo ideal; las barras aplican
  las eficiencias para obtener el ERR de frontera completa.
- **Flujo de potencia animado.** Partículas de igual potencia $P_{in}/R$; en la etapa $j$ se desvía hacia el colector de
  calor la fracción $L_j/F_j$ (pérdida / flujo entrante), lo que reproduce en promedio el balance del Sankey.
- **Despacho bajo incertidumbre en tiempo real (UCF).** Para cada recurso, $z_t=\varphi z_{t-1}+\sqrt{1-\varphi^2}\,
  \varepsilon_t$ y $W_t=F^{-1}(\Phi(z_t))$ con $\varphi=0{,}7$ (cópula gaussiana): la marginal es exactamente $F$, por lo
  que el costo medio realizado converge a la UCF* en $W_s^*$; la autocorrelación solo hace más lenta la convergencia
  (varianza del promedio inflada hasta $\approx(1+\varphi)/(1-\varphi)$). $F^{-1}$ se tabula con `Resource.ppf`
  (401 cuantiles) y se interpola linealmente.
- **Flota modular (Firmeza).** Cada unidad es una cadena de Markov de 2 estados en tiempo continuo, muestreada con las
  probabilidades de transición exactas $P_{1\to0}=\frac{\lambda}{\lambda+\mu}\left(1-e^{-(\lambda+\mu)\Delta t}\right)$,
  $P_{0\to1}=\frac{\mu}{\lambda+\mu}\left(1-e^{-(\lambda+\mu)\Delta t}\right)$, que preservan $A=\mu/(\lambda+\mu)$ para
  cualquier $\Delta t$. Si la disponibilidad se fija directamente, se supone MTTR = 48 h y MTBF = MTTR·A/(1−A). El
  compromiso $C_f$ es la capacidad firme modular al nivel $\alpha$ (COPT); el cumplimiento simulado se compara con
  $P(K\ge\lceil C_f/P_m\rceil)$ y, para la unidad única, con $A$.

---

## 8. Limitaciones

Modelo físico genérico (no el diseño patentado); un solo día de despacho; costos IE desconocidos; distribuciones de
recurso ilustrativas; los resultados no sustituyen estudios del operador (CENCE) ni validación de laboratorio
acreditado.

## Referencias

1. ICE-DOCSE. *Informe de atención de demanda y producción de electricidad con fuentes renovables 2025*; *Producción y
   demanda — Informe anual 2025*.
2. TV Legislativa (2026). Presentación del despacho del 14/06/2026 (DOCSE-ICE). <https://youtu.be/j5LNATUHgT4>
3. La Nación (22-oct-2026); Semanario Universidad (may-2026); CRHoy (21-oct-2026); Delfino (dic-2025); CET-CR (may-2026).
4. IRENA (2025). *Renewable Power Generation Costs in 2024*. IRENA (2026). *24/7 renewables: The economics of firm solar and wind*.
5. Garver, L. L. (1966). Effective load carrying capability of generating units. *IEEE Trans. PAS*, 85(8), 910–919.
6. Hetzer, J., Yu, D. C., Bhattarai, K. (2008). An economic dispatch model incorporating wind power. *IEEE Trans. Energy Conversion*, 23(2), 603–611.
7. Literatura de funciones de costo de incertidumbre (UCF) y sus expresiones marginales para generación solar, eólica,
   pequeñas centrales hidroeléctricas, vehículos eléctricos y cargas controlables en despacho económico estocástico.
8. JCGM 100:2008. *Evaluation of measurement data — Guide to the expression of uncertainty in measurement (GUM)*.
9. IEC 62053-22; IEC 61869-2/-3; IEC 61000-4-30; IEC 60034-2-1; ISO 1217; ISO 50015; ISO/IEC 17025; IEEE 519; IEEE 1588.
10. Hunt, J. D. et al. (2021). Buoyancy Energy Storage Technology. *Journal of Energy Storage*, 40, 102746.
