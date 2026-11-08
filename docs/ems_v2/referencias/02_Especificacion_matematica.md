# SEEDS2: especificación matemática del EMS MILP-MPC

**Versión 1.0 · 7 de noviembre de 2026 · Propuesta para revisión científica.**

Base contrastada: `8556b71a76dd13d279a0e0ecd8ad9bd498df72f1` de `brunoolmedo22-Paraguay/EnergyMultimodelv1.5`. Este documento especifica un prototipo; no acredita una implementación, resultados ni autorización de sustitución de V1.6. Las constantes físicas deben proceder del inventario, de identificación documentada o de una decisión explícita. Un valor ausente es `null`, nunca cero o infinito implícitos.

## 1. Alcance y convenciones obligatorias

El problema es despacho energético centralizado de **una microrred aislada**, sobre un bus eléctrico equivalente, con FV/eólica, bancos BESS y unidades PEMFC/térmicas heterogéneas. No dimensiona equipos ni calcula flujo AC, tensión, frecuencia, estabilidad, intercambios entre microrredes o producción de H2. Cada banco con convertidor propio y cada unidad controlable conserva su UID. Celdas conectadas a un mismo convertidor constituyen un banco físico, no decisiones eléctricas independientes.

Se mantienen dos niveles: un modelo de planificación lineal por tramos y un modelo físico de ejecución independiente. La optimalidad MILP se refiere exclusivamente a la aproximación discretizada. No demuestra optimalidad de la planta no lineal ni estabilidad del MPC.

**Frontera:** todas las potencias del balance se expresan en kW **netos en el bus equivalente**. La disponibilidad renovable ya incluye las pérdidas del camino hasta ese bus. La PEMFC neta ya descuenta BoP y conversión en modo operativo; no se multiplica otra vez por una eficiencia. La demanda incluye las pérdidas aguas abajo que hayan sido explícitamente modeladas. Auxiliares de arranque/standby se añaden sólo si no están incluidos en las curvas. No se mezclan magnitudes de stack y bus.

Las hipótesis H1-H9 que preservan linealidad son: capacidad BESS constante; eficiencias positivas constantes por banco/ventana; potencia renovable exógena; demanda exógena; parámetros económicos exógenos; curva PEMFC de caudal H2 frente a potencia neta por tramos con dominio fijo; rampas y tiempos declarados; topología de bus único; producto de parámetros por variables únicamente. Cambiar estas hipótesis exige nueva versión del modelo.

## 2. Tiempo, índices y conjuntos

En una reoptimización en el instante absoluto $\tau_k$, se usa:

$$\mathcal T=\{0,\ldots,N-1\},\quad \mathcal K=\{0,\ldots,N\},\quad I_t=[\tau_k+t\Delta,\tau_k+(t+1)\Delta).\tag{M01}$$

$\Delta$ está en minutos; $h=\Delta/60$ en horas. Hay $N$ decisiones de intervalo y $N+1$ estados de frontera. El último estado no es un intervalo adicional. Se conserva una malla uniforme en el primer prototipo.

| Símbolo | Significado |
|---|---|
| $\mathcal R$ | Recursos renovables, por UID/arreglo o grupo eléctricamente equivalente |
| $\mathcal B$ | Bancos BESS independientes |
| $\mathcal F$ | Unidades PEMFC independientes, incluyendo unidades dentro de un equipo múltiple |
| $\mathcal G$ | Unidades térmicas independientes |
| $\mathcal U=\mathcal F\cup\mathcal G$ | Unidades con commitment |
| $\mathcal L$ | Categorías de demanda con política de interrupción explícita |
| $\mathcal S_f$ | Segmentos consecutivos de la curva de cada PEMFC |
| $\mathcal H$ | Depósitos H2, sólo si existen datos físicos de stock y conexiones |

No se crea $\mathcal H$ a partir de un catálogo de PEMFC. Si no hay depósito representado, el estudio debe declarar suministro externo de H2 sin límite de stock; ello impide afirmar autonomía de combustible.

## 3. Diccionario de parámetros

Todos los límites son finitos cuando la familia de restricciones está habilitada. Una restricción opcional deshabilitada lleva un código de motivo; no se representa con números enormes.

| Parámetro | Unidad | Origen/condición |
|---|---|---|
| $L_{\ell t}\ge0$ | kW bus | Previsión de demanda por intervalo |
| $A_{rt}\ge0$ | kW bus | Potencia renovable disponible antes de curtailment |
| $a_{it}\in\{0,1\}$ | adimensional | Disponibilidad de equipo/unidad, distinta de encendido |
| $C_b>0$ | kWh | Capacidad de referencia compatible con SOC del modelo |
| $\underline s_b,\overline s_b$ | fracción | Límites, $0\le\underline s_b<\overline s_b\le1$ |
| $\eta_b^c,\eta_b^d\in(0,1]$ | adimensional | Eficiencias totales entre bus y energía interna |
| $\overline P^c_{bt},\overline P^d_{bt}$ | kW bus | Límites validados de carga/descarga |
| $\lambda_b\ge0$ | h$^{-1}$ | Autodescarga opcional; requiere dato |
| $\underline P_{it},\overline P_{it}$ | kW bus | Límites de unidad operativa; $0\le\underline P\le\overline P$ |
| $R_i^+,R_i^-$ | kW/min | Modulación entre consignas consecutivas |
| $S_i^+,S_i^-$ | kW | Potencia máxima admitida en el primer/último intervalo operativo |
| $T_i^{up},T_i^{down}$ | min | Permanencias mínimas; no estimarlas a partir del precio |
| $u_i^{-1},p_i^{-1}$ | binario, kW | Estado y potencia previos a la ventana |
| $d_i^{on},d_i^{off}$ | min | Tiempo continuo ya transcurrido en el estado inicial |
| $e_b^0$ | kWh | Estado inicial/medido de cada banco |
| $P_{fs},Q_{fs}$ | kW, kg/h | Vértices consecutivos de caudal H2 **suministrado** |
| $m_i^{SU},m_i^{SD}$ | kg/evento | H2 adicional por evento, sólo PEMFC y sin duplicación |
| $W_i^{SU},W_i^{SD}$ | kWh/evento | Electricidad auxiliar adicional no incluida en curvas |
| $c_{H,t}$ | R$/kg | Precio H2 en moneda y fecha declaradas |
| $c^E_{it},c_b^{thr},c_r^{curt}$ | R$/kWh | O&M variable, throughput y vertimiento, respectivamente |
| $c_i^{on}$ | R$/h | Costo fijo por hora encendida, si hay dato |
| $C_i^{SU},C_i^{SD}$ | R$/evento | Costos directos de transición |
| $V_{\ell t}$ | R$/kWh | Valor de energía no suministrada, para análisis económico |
| $\overline D_t$ | kW bus | Capacidad real de disipación; cero si no existe carga de descarte |
| $E_b^{ref},\kappa_b$ | kWh, R$/kWh | Referencia terminal y costo de incumplimiento |

La moneda R$ mantiene compatibilidad con V1.6, sin convertir precios de otras monedas automáticamente. Los costos actuales de `ECON_PADRAO` son parámetros de una configuración de software, no estimaciones económicas validadas.

**Conversión de frontera BESS:** si la caracterización entrega potencia terminal $\widetilde P$ y eficiencia de convertidor $\eta^{conv}$, las potencias equivalentes son $P^d_{bus}=\eta^{conv}\widetilde P^d$ y $P^c_{bus}=\widetilde P^c/\eta^{conv}$. Con eficiencias internas $\widetilde\eta^d,\widetilde\eta^c$, usar $\eta^d=\eta^{conv}\widetilde\eta^d$ y $\eta^c=\eta^{conv}\widetilde\eta^c$. Esto aplica sólo si las eficiencias internas no incluyen ya el convertidor. Guardar la cadena de pérdidas y su procedencia.

## 4. Variables y dominios

| Variable | Dominio/unidad | Significado |
|---|---|---|
| $P^R_{rt},C^R_{rt}$ | $\mathbb R_+$, kW | Renovable usada y vertida |
| $P^c_{bt},P^d_{bt}$ | $\mathbb R_+$, kW | Carga y descarga en el bus |
| $z^b_{bt}$ | binaria | Modo carga; descarga usa su complemento |
| $e_{bk}$ | $\mathbb R_+$, kWh | Energía almacenada en frontera |
| $p_{it}$ | $\mathbb R_+$, kW | Potencia neta operativa de cada unidad |
| $u_{it},y_{it},z_{it}$ | binarias | Encendida, arranca y se detiene |
| $\delta_{fst}$ | binaria | Segmento PEMFC activo |
| $\theta_{fst}$ | $\mathbb R_+$ | Posición local en segmento activado |
| $q_{ft}$ | $\mathbb R_+$, kg/h | Caudal H2 suministrado operativo |
| $\ell_{\ell t}$ | $\mathbb R_+$, kW | Demanda interrumpida autorizada |
| $d_t$ | $\mathbb R_+$, kW | Potencia consumida por descarte físico |
| $\xi_b$ | $\mathbb R_+$, kWh | Incumplimiento de referencia terminal blanda |
| $M_{hk}$ | $\mathbb R_+$, kg | Masa H2 del depósito opcional |
| $v_{it}$ | $\mathbb R_+$, kW | Variación absoluta de consigna, opcional |

Los indicadores $y,z$ se definen aunque su costo sea cero. No se permite que una relajación continua de estos indicadores genere eventos fraccionarios. El nombre $z^b$ se distingue del apagado $z_{it}$.

## 5. Balance y renovables

Para todo intervalo:

$$\sum_{r\in\mathcal R}P^R_{rt}+\sum_{i\in\mathcal U}p_{it}+\sum_{b\in\mathcal B}(P^d_{bt}-P^c_{bt})=\sum_{\ell\in\mathcal L}(L_{\ell t}-\ell_{\ell t})+P^{aux}_t+d_t.\tag{M02}$$

$$P^R_{rt}+C^R_{rt}=A_{rt},\quad 0\le P^R_{rt}\le a_{rt}A_{rt},\quad C^R_{rt}\ge0.\tag{M03}$$

$A$ representa potencial antes de disponibilidad; si se entrega ya corregido por indisponibilidad, fijar $a=1$ y declarar esa transformación para evitar duplicación. El curtailment total puede desglosarse en indisponibilidad y limitación voluntaria. Nunca se transforma una medición ausente en $A=0$.

$$0\le\ell_{\ell t}\le\chi_{\ell t}L_{\ell t},\qquad 0\le d_t\le\overline D_t.\tag{M04}$$

$\chi$ es la fracción interrumpible autorizada, en $[0,1]$. Carga crítica sin interrupción: $\chi=0$. Si sólo existe demanda agregada, se conserva una categoría y se explicita si es interrumpible. La variable de déficit **no produce electricidad**: representa carga efectivamente desconectada. Un exceso térmico no puede desaparecer sin destino eléctrico; con $\overline D=0$, sin capacidad BESS ni reducción posible, el caso es físicamente inviable. Las holguras ilimitadas de V1.6 no se transfieren a este modo físico.

En la versión instantánea de commitment, si los consumos auxiliares se conocen como energía/evento y corresponden íntegramente al intervalo de transición:

$$P^{aux}_t=\sum_i\left(W_i^{SU}y_{it}/h+W_i^{SD}z_{it}/h+P_i^{sb}m^{sb}_{it}\right).\tag{M05}$$

Si no existe standby, omitir el último término. No incluir aquí BoP ya descontado en $p_{ft}$. Arranques de varios intervalos usan perfiles por modo de la sección 10, no M05 como sustituto de la duración real.

## 6. BESS por banco

$$0\le P^c_{bt}\le a_{bt}\overline P^c_{bt}z^b_{bt},\quad 0\le P^d_{bt}\le a_{bt}\overline P^d_{bt}(1-z^b_{bt}).\tag{M06}$$

$$e_{b,t+1}=\alpha_b e_{bt}+h\left(\eta_b^cP^c_{bt}-P^d_{bt}/\eta_b^d\right),\quad \alpha_b=\exp(-\lambda_bh).\tag{M07}$$

$\alpha_b$ se precalcula y no es variable. Si no se modela autodescarga, declarar hipótesis $\alpha_b=1$. No atribuirla a identificación. La discretización M07 aproxima la interacción continua de pérdida y flujo; con autodescarga relevante debe utilizarse el coeficiente exacto integrado del flujo constante, también precalculable, y documentar su versión.

$$C_b\underline s_b\le e_{bk}\le C_b\overline s_b\quad(k\in\mathcal K),\quad e_{b0}=e_b^0,\quad SOC_{bk}=e_{bk}/C_b.\tag{M08}$$

No aplicar clipping al propagar SOC. Una discrepancia fuera de tolerancia produce un fallo de validación. La misma fórmula M07 se aplica a los flujos implementados en el modo algebraico, conservando por separado $P^c$ y $P^d$. El modo físico usa el SOC producido por el modelo independiente y registra el error de predicción.

En ausencia de un modelo validado de temperatura, tasa C y tensión, los límites se consideran constantes conservadores dentro de un dominio declarado. La dependencia real de $P_{max}$ con SOC puede representarse mediante envolventes afines $P^d\le a_j e+b_j$ si cada desigualdad es físicamente válida en todo el dominio. No se permite construir el límite futuro repitiendo una trayectoria previa de carga/descarga ajena al despacho.

## 7. Commitment de PEMFC y térmica

El caso básico admite OFF y ON. ON significa unidad caliente y disponible para entregar potencia dentro de un intervalo; **no supone que una PEMFC fría arranque instantáneamente**. Si el dato de arranque no respalda ese supuesto, usar la sección 10 o bloquear la transición.

$$u_{it}-u_{i,t-1}=y_{it}-z_{it},\quad y_{it}+z_{it}\le1,\quad u_{it}\le a_{it},\quad u_{i,-1}=u_i^{-1}.\tag{M09}$$

$$\underline P_{it}u_{it}\le p_{it}\le\overline P_{it}u_{it}.\tag{M10}$$

Cada unidad tiene parámetros propios. El número activo es una salida: $n_{ft}^{equipo}=\sum_{i\in equipo(f)}u_{it}$, no una aproximación inferida de la potencia. Se pueden fijar estados para un ensayo, pero no se fija una sola configuración entera a toda la ventana por diseño.

### 7.1 Rampas y transiciones

$$p_{it}-p_{i,t-1}\le R_i^+\Delta\,u_{i,t-1}+S_i^+y_{it},\tag{M11a}$$
$$p_{i,t-1}-p_{it}\le R_i^-\Delta\,u_{it}+S_i^-z_{it},\quad p_{i,-1}=p_i^{-1}.\tag{M11b}$$

Las rampas se verifican incluso en $t=0$ y aunque $p_i^{-1}=0$. Con ON continuo se limita la modulación; con arranque/apagado se usa un límite específico $S^+,S^-$. Se exige coherencia entre esos límites y $P_{min}$; no se sustituye $S$ por $P_{max}$ por conveniencia. Desactivar las rampas requiere declarar que ese fenómeno está fuera de la variante ensayada.

M11 restringe diferencias entre consignas de intervalo. La interpretación como rampa continua de la planta es aproximada: no asegura que una consigna constante se alcance instantáneamente ni que el balance se cumpla a cada segundo. Para plantas en las que ese error sea relevante, introducir potencias de extremo $w_{ik}$, $\bar p_{it}=(w_{it}+w_{i,t+1})/2$ y límites $-R^-\Delta\le w_{i,t+1}-w_{it}\le R^+\Delta$, con perfiles de transición consistentes. El balance de energía usa $\bar p$ y la simulación verifica potencia instantánea. La admisión del modelo simple queda condicionada al replay físico a alta resolución.

Una indisponibilidad repentina puede hacer incompatible M11 con $u=0$. El incidente debe declararse como parada forzada con una envolvente de emergencia documentada; no se elimina silenciosamente una restricción. El modelo no promete operación ininterrumpida ante cualquier fallo.

### 7.2 Permanencias y memoria de arranque

En malla uniforme, $U_i=\lceil T_i^{up}/\Delta\rceil$ y $D_i=\lceil T_i^{down}/\Delta\rceil$. Para todo $t$:

$$\sum_{j=\max(0,t-U_i+1)}^t y_{ij}\le u_{it},\qquad \sum_{j=\max(0,t-D_i+1)}^t z_{ij}\le1-u_{it}.\tag{M12}$$

Si inicialmente ON, fijar $u=1$ durante $r_i^{on}=\max(0,\lceil(T_i^{up}-d_i^{on})/\Delta\rceil)$ intervalos; si OFF, fijar $u=0$ durante $r_i^{off}$ definido análogamente. Se limita a los intervalos presentes y se transporta el remanente. Si $U$ o $D=0$, su suma es vacía y no crea restricción. El redondeo hacia arriba es conservador y queda en metadatos.

Las obligaciones que exceden la ventana se preservan en el estado MPC. En el último instante de la misión se debe elegir explícitamente entre continuidad de la planta después de la misión, extensión de previsiones para completar las obligaciones o prohibición de nuevas transiciones que no puedan terminar. No se trunca una permanencia por terminar un archivo.

## 8. PEMFC: curva H2 lineal por tramos

### 8.1 Magnitud que debe aproximarse

El repositorio calcula caudal suministrado a partir de Faraday y utilización. En forma conceptual:

$$q_f(I)=3600\frac{N_{cell,f}I\,M_{H2}}{2F\,U_{H2,f}}\quad[\mathrm{kg/h}].\tag{M13}$$

No fijar aquí $F$, $M_{H2}$ o $U_{H2}$ con valores supuestos: el adaptador lee la configuración del modelo utilizado y su hash. El modelo eléctrico determina $P^{net}(I,T,p,\ldots)$; seleccionar una rama de funcionamiento monótona y físicamente válida para construir $q(P^{net})$.

En V1.6, se interpola $g(P)$ en kg/kWh y después se calcula $g(P)P$. Aunque $g$ sea afín por tramo, el producto no es afín. Para un MILP se ajusta directamente $q(P)$ o el costo horario $c_Hq(P)$; no se traslada ese producto a Pyomo.

### 8.2 Formulación exacta del interpolante seleccionado

Para cada segmento $s$ entre vértices $s$ y $s+1$, $P_{f,s+1}>P_{fs}\ge P_{min,f}>0$:

$$\sum_{s\in\mathcal S_f}\delta_{fst}=u_{ft},\quad 0\le\theta_{fst}\le\delta_{fst},\quad\delta_{fst}\in\{0,1\}.\tag{M14}$$

$$p_{ft}=\sum_s\left[P_{fs}\delta_{fst}+(P_{f,s+1}-P_{fs})\theta_{fst}\right],\tag{M15}$$
$$q_{ft}=\sum_s\left[Q_{fs}\delta_{fst}+(Q_{f,s+1}-Q_{fs})\theta_{fst}\right].\tag{M16}$$

Con OFF, $p=q=0$; con ON, exactamente un segmento queda activo. No hay interpolación entre $(0,0)$ y $P_{min}$: ese segmento permitiría operación continua por debajo del mínimo. M14-M16 funcionan con curvas no convexas, sin SOS2 y sin productos de variables. En un vértice puede elegirse cualquiera de sus dos segmentos vecinos sin cambiar la física. Las cotas M10 pueden restringir más el dominio si existe disponibilidad reducida validada.

Una formulación con sólo combinación convexa de todos los vértices, sin adyacencia, representa la envolvente convexa, no necesariamente la curva. Un epígrafe sin igualdad sólo es equivalente si se prueba convexidad y que el objetivo fuerza igualdad. No asumirlo al añadir depósitos, varios objetivos o precios nulos.

### 8.3 Construcción, certificación y error

Obtener puntos estacionarios del modelo neto para cada UID y conjunto de condiciones. Excluir arranque, standby, limitaciones, fallos y ramas no monótonas. Separar puntos de ajuste y puntos densos de validación, incluidos vértices y vecindades. Refinar adaptativamente 4, 8, 12 y 16 segmentos como candidatos de complejidad, no como números físicos universales.

Registrar dominio de corriente, potencia neta, temperatura, presión, utilización H2, auxiliares, versión y procedencia. Interpolar dentro del dominio; fuera de él bloquear el setpoint. Un perfil V-I de ModelLab sin número de celdas, utilización, BoP y conversión no basta para obtener consumo H2 neto.

Una envolvente superior certificada $q^{safe}(P)\ge q^{phys}(P)$ puede proteger un stock frente al error de consumo, pero sólo en el dominio y condiciones certificados. Se construye y valida explícitamente; sumar un margen arbitrario no constituye certificación. El error de potencia entregada, los transitorios y la incertidumbre del modelo siguen requiriendo pruebas separadas.

### 8.4 Contabilidad de combustible

$$m_{ft}=h q_{ft}+m_f^{SU}y_{ft}+m_f^{SD}z_{ft}\quad[\mathrm{kg/intervalo}].\tag{M17}$$

Los términos de evento no se multiplican por $h$. Si el consumo de arranque se representa por un perfil temporal de modos, no se vuelve a sumar aquí. H2 suministrado y electroquímicamente consumido se exportan con nombres distintos; para costo y stock se utiliza suministrado.

Si hay depósitos físicos y asignación fija de unidad a depósito $\mathcal F_h$:

$$M_{h,t+1}=M_{ht}+m^{in}_{ht}-\sum_{f\in\mathcal F_h}m_{ft},\quad \underline M_h\le M_{hk}\le\overline M_h,\quad M_{h0}=M_h^0.\tag{M18}$$

$m^{in}$ está en kg/intervalo y es exógeno en esta versión. Añadir caudal máximo de salida si se conoce. Sin stock inicial, capacidad y presión admisible, M18 no se habilita. La relación presión-masa sólo es lineal bajo temperatura/volumen/compresibilidad fijados; no se añade un tanque ficticio ni se garantiza presión a partir de masa sin validación.

## 9. Térmica y costo

Cada térmica usa M09-M12. El prototipo con CVU declarado adopta:

$$\dot C_{gt}=c^E_{gt}p_{gt}+c_g^{on}u_{gt}\quad[\mathrm{R\$/h}].\tag{M19}$$

Un CVU recibido en R$/MWh se divide por 1000. No se recalcula a partir de producción nula. Si existe curva de combustible o costo horario no lineal, usar M14-M16 con vértices $(P,\dot C)$ y su propio conjunto de segmentos. No multiplicar otra vez un costo horario por potencia. Costos de arranque/apagado son $C_g^{SU}y+C_g^{SD}z$ en R$.

Costos cuadráticos exactos con commitment conducen a MIQP; pérdidas AC, términos continuos bilineales y electroquímica explícita pueden conducir a MINLP. HiGHS no se considera solver para esas variantes. SLSQP con enteros fijados no resuelve globalmente el MINLP conjunto.

## 10. Extensión lineal para arranque no instantáneo

La formulación OFF/ON es suficiente sólo para el dominio admitido. Para inicio frío, standby, calentamiento o parada no instantánea, declarar un autómata finito por unidad con OFF, etapas de arranque $S_1,\ldots,S_{d_i}$, ON, standby SB y etapas de parada $D_1,\ldots,D_{v_i}$, omitiendo estados no soportados. Los arcos permitidos forman $\mathcal A_i$. $d_i=\lceil\tau_i^{start}/\Delta\rceil$ y $v_i=\lceil\tau_i^{stop}/\Delta\rceil$ requieren duraciones documentadas. Las etapas avanzan obligatoriamente a la siguiente; no tienen auto-bucles salvo que la física admita una espera. Se transporta el tiempo remanente si inicialmente ya hay una transición en curso.

Con $m_{iqt}$ modo en intervalo y $v_{iqq't}$ transición al inicio de $t$:

$$\sum_qm_{iqt}=1,\quad \sum_{q':(q,q')\in\mathcal A_i}v_{iqq't}=m_{iq,t-1},\quad \sum_{q:(q,q')\in\mathcal A_i}v_{iqq't}=m_{iq't}.\tag{M20}$$

Todos $m,v$ son binarios y $m_{iq,-1}$ se lee del estado. OFF/ON admiten auto-bucle; los modos no disponibles se fijan a cero. $u_{it}=m_{i,ON,t}$. Distinguir $y^{start}$ (arco de inicio de arranque) de $y^{run}$ (entrada a ON) y $z^{run}$ (salida de ON):

$$y^{run}_{it}=\sum_{q\ne ON}v_{i,q,ON,t},\quad z^{run}_{it}=\sum_{q'\ne ON}v_{i,ON,q',t},\quad y^{start}_{it}=\sum_{q:(q,S_1)\in\mathcal A_i}v_{i,q,S_1,t}.\tag{M20b}$$

Si no hay etapas, el arco de inicio lleva directamente a ON. En M12, la permanencia mínima ON utiliza $y^{run}$, no $y^{start}$; el tiempo OFF se limita con entradas/salidas del modo OFF y su indicador. El bloqueo de nuevos arranques se aplica a OFF durante su obligación remanente. El costo de partida y el conteo usan $y^{start}$ y se cobran una sola vez. No imponer $\sum y^{start}\le u^{ON}$ mientras la unidad todavía está en $S_j$. Si un fabricante considera standby parte del estado caliente/activo, debe definirse un indicador de ese conjunto y su permanencia propia. M20 sustituye M09; no se imponen ambas con indicadores incompatibles.

La potencia neta fuera de ON se representa mediante un perfil fijo por modo/etapa: generación no negativa $g^{mode}_{iq}m_{iqt}$ en el lado izquierdo de M02 y consumo auxiliar $a^{mode}_{iq}m_{iqt}$ en su lado derecho. Ambos son parámetros validados en kW y no se duplican con M05. El caudal adicional se añade como $q^{mode}_{iq}m_{iqt}h$ a M17, sin volver a cobrar masa/evento. Si las etapas no generan, fijar $g^{mode}=0$ como hipótesis explícita. Las rampas entre modos emplean cotas de transición coherentes; M11 no se usa ignorando modos intermedios. Si sólo se conoce duración y no consumo/perfiles, se puede ensayar una variante simplificada etiquetada, pero no declararla validación física de partida. La ausencia de esos parámetros no se resuelve inventándolos.

Una forma lineal explícita de la rampa multimodo usa la potencia neta completa $\pi_{it}=p_{it}+\sum_{q\ne ON}(g^{mode}_{iq}-a^{mode}_{iq})m_{iqt}$ y cotas por arco $B^+_{iqq'},B^-_{iqq'}$ en kW:

$$\pi_{it}-\pi_{i,t-1}\le\sum_{(q,q')\in\mathcal A_i}B^+_{iqq'}v_{iqq't},\quad \pi_{i,t-1}-\pi_{it}\le\sum_{(q,q')\in\mathcal A_i}B^-_{iqq'}v_{iqq't}.\tag{M20c}$$

Cada intervalo selecciona un arco. En ON-ON se usan $R^+\Delta,R^-\Delta$; los otros arcos requieren límites/perfiles admitidos y la potencia neta inicial real. Los $B$ son parámetros físicos de transición, no Big-M arbitrarios. M20c reemplaza M11 para esa unidad. El costo M21 suma el caudal de modos y usa los indicadores de evento correspondientes. Una implementación de la variante básica no puede declarar cumplida la variante multimodo por tener sólo las variables ON/OFF.

## 11. Objetivo y prioridad de servicio

### 11.1 Función económica escalar

Para la variante básica:

$$\begin{aligned}
J_{econ}={}&\sum_{t\in\mathcal T}\Bigg\{h\Bigg[\sum_f(c_{H,t}q_{ft}+c^E_{ft}p_{ft}+c_f^{on}u_{ft})+\sum_g\dot C_{gt}\\
&+\sum_b c_b^{thr}(P^c_{bt}+P^d_{bt})+\sum_r c_r^{curt}C^R_{rt}+\sum_\ell V_{\ell t}\ell_{\ell t}+c^{dump}_td_t\Bigg]\\
&+\sum_{i\in\mathcal U}(C_i^{SU}y_{it}+C_i^{SD}z_{it})+\sum_f c_{H,t}(m_f^{SU}y_{ft}+m_f^{SD}z_{ft})\Bigg\}\\
&+\sum_b\kappa_b\xi_b+\sum_{i,t}\gamma_i v_{it}.
\end{aligned}\tag{M21}$$

Todos los términos de M21 están en R$. $\gamma$ está en R$/kW por cambio de consigna; si el usuario quiere costo por rampa en kW/min, necesita otra definición y otra unidad. $v\ge p_t-p_{t-1}$ y $v\ge p_{t-1}-p_t$ linealizan el valor absoluto cuando $\gamma\ge0$. Este término sólo es un regularizador mientras no exista identificación de degradación; no demuestra extensión de vida útil.

No duplicar combustible de arranque dentro de $C^{SU}$ si ya incluye su compra. El throughput BESS se cobra sobre ambos flujos bus; un coeficiente definido por energía interna requiere transformar la base. La depreciación real, rainflow y electroquímica no se infieren de $c_b^{thr}$.

### 11.2 Prioridad recomendada

Una penalización finita no garantiza servicio prioritario frente a arranques caros, aunque sea 10 o 100 veces el CVU. Se recomienda resolver lexicográficamente:

$$J_{serv}=\sum_{t,\ell}h\,w_\ell\ell_{\ell t},\quad J_{serv}\le J_{serv}^{*}+\varepsilon_{serv},\quad\min J_{econ}.\tag{M22}$$

Para prioridades estrictas entre categorías, usar niveles lexicográficos separados, no pesos arbitrariamente grandes. El primer problema debe resolver su prioridad hasta una cota certificada. Si termina con incumbent y gap abierto, no puede declararse mínimo déficit probado. La segunda etapa conserva la mejor cota/solución admisible documentada y su estado. Propuesta numérica para casos analíticos: $\varepsilon_{serv}=10^{-6}$ kWh sobre escala normalizada; debe endurecerse si fuera comparable a la demanda del ensayo.

Variante de comparación con V1.6: usar sólo M21 con sus penalizaciones idénticas y sin prioridades extra. Variante de servicio duro: fijar $\ell=0$ donde se exija. Estas variantes no se mezclan en una tabla de ranking único.

## 12. Condiciones iniciales y terminales

El estado inicial incluye $e_b^0$, $u_i^{-1}$, $p_i^{-1}$, modo/etapa de arranque, tiempos ON/OFF acumulados, obligaciones remanentes y stock H2 si existe. Comprobar coherencia: OFF implica potencia operativa cero; ON debe estar en dominio; SOC debe respetar límites. Equipos inicialmente en transición requieren la extensión M20. Nunca inicializar $p^{-1}$ a cero para representar una potencia real distinta.

La política terminal debe estar versionada. Tres variantes implementables:

1. Sin término terminal, sólo para casos analíticos o ablation explícita.
2. Referencia blanda de energía: $e_{bN}+\xi_b\ge E_b^{ref}(\tau_k+Nh)$, $\xi_b\ge0$, con costo M21. La referencia es un cronograma absoluto o la referencia de cierre de misión declarada; **no se redefine como el SOC corriente en cada ventana**. En experimentos iniciales se puede usar $E_b^{ref}=e_b^{mission,0}$ como referencia constante, identificando el sesgo y haciendo sensibilidad de $\kappa$. No existe valor físico universal para $\kappa$.
3. Mínimo duro terminal $e_{bN}\ge E_b^{reserve}$, cuando la misión lo exige y los parámetros se conocen. Puede volver el problema inviable; ése es un resultado válido.

Para comparar costos entre controladores, exigir la misma energía/stock final o mostrar la diferencia y una valoración terminal común. Un controlador que agota más la batería no acredita ahorro comparable por ese solo hecho. Añadir valor terminal lineal o por tramos sólo con análisis de unidades, cota y sensibilidad. Ninguna de las políticas anteriores establece por sí sola un conjunto terminal invariante ni factibilidad recursiva.

## 13. Arquitectura temporal y reglas de interfaz

| Concepto | Definición | Propuesta provisional |
|---|---|---|
| Horizonte de previsión $H_f$ | Futuro cubierto por una emisión de previsión | Al menos $H_o$, renovado en cada ciclo |
| Horizonte de optimización $H_o$ | Futuro modelado al resolver | 60 min, a contrastar con 1-120 min |
| Discretización $\Delta$ | Duración de intervalo de decisión | 1 min |
| Reoptimización $\rho$ | Tiempo entre resoluciones | 1 min, $m=\rho/\Delta=1$ |
| Misión $T_M$ | Duración total del experimento | La elegida en el escenario; no inferirla de $N$ |
| Integración física $\delta_{phys}$ | Paso interno del simulador | El validado por cada modelo; 2 s es un candidato ya usado para PEMFC, no garantía de precisión |

La propuesta $N=60$ es un punto de partida experimental, no un óptimo bibliográfico. Para misión corta usar $N_k=\min(N,K_M-k)$ sin inventar previsiones ni eliminar intervalos finales. Con horizonte fijo más allá del fin de misión, se necesita cobertura explícita y política de obligaciones posmisión. Registrar cada acortamiento.

Reglas mínimas: $H_o=N\Delta$; $\rho=m\Delta$ con entero $1\le m\le N$; $H_f\ge H_o$ en cada emisión; misión divisible por $\Delta$ en el prototipo (si no, bloquear o adoptar explícitamente último intervalo corto en una versión posterior). La frecuencia de publicación del forecast no es la reoptimización. No realizar upsampling que finja información nueva. Pérdidas de cobertura, huecos, NaN, zona horaria ambigua o unidades desconocidas bloquean la ejecución.

| Configuración | Uso conceptual | Riesgo que debe mostrarse |
|---|---|---|
| $H_o=1$-5 min; $\Delta=1$ min | Reacción local y pruebas mínimas | Miopía energética; arranques lentos sin beneficio visible |
| $H_o=10$-30 min; $\Delta=1$-5 min | Demanda de variación rápida y primeras comparaciones | Puede no anticipar un ciclo industrial o recuperación de SOC |
| $H_o=60$-120 min; $\Delta=1$-5 min | Candidato principal para despacho operativo | Mayor tamaño entero; error de forecast acumulado |
| $\Delta=10$-30 min | Planificación de energía más agregada | Oculta picos, rampas, transiciones y simultaneidad subintervalo |
| $\Delta=60$-120 min | Nivel lento, si la misión lo permite | Inadecuado como único control de una planta rápida; requiere capa rápida |
| $\rho>\Delta$ | Implementar varios intervalos antes de resolver | Más tiempo sin corrección de forecast/estado |

Si $\Delta>H_o$ o $\rho>H_o$, bloquear. Si una rampa, pico o transición importante es más rápida que $\Delta$, advertir y exigir replay/capa rápida para admitir el ensayo. Si $H_o$ no alcanza el evento de demanda, la duración de arranque o las obligaciones mínimas, advertir sobre la miopía; no afirmar que siempre sea matemáticamente inválido. Carga industrial flexible exige tareas, ventanas, potencia y energía a conservar; el perfil agregado actual no permite inventar flexibilidad.

La etapa jerárquica futura puede planificar SOC/stock/commitment a 12-24 h y dejar la corrección a 1-120 min. Es una extensión condicionada a datos y validación: el primer prototipo tiene un único MPC. La malla multirresolución exige integrar cada intervalo con su duración y preservar restricciones/commitments entre resoluciones; no equivale a cambiar $N$.

## 14. Datos temporales y causalidad

Una serie puede contener muestras instantáneas o medias de intervalo; son contratos diferentes. Para medias, agregar conservando $\sum_t P_th_t$ mediante intersección de intervalos. Para muestras, elegir reconstrucción (ZOH o interpolación lineal) y calcular las medias del intervalo por integración de esa reconstrucción. No integrar después esas medias con trapecios. Las etiquetas UTC corresponden al inicio y fin de cada intervalo; el estado final se exporta aparte.

FV/eólica: es preferible simular a resolución suficiente y agregar **potencia** a intervalos; simular directamente el clima promediado no conserva necesariamente energía porque el modelo es no lineal. Conservar datos originales y transformaciones. Un forecast de emisión $\tau$ sólo puede usarse desde su disponibilidad declarada. El baseline de previsión perfecta se etiqueta como tal; una única trayectoria conocida de toda la misión no prueba desempeño bajo incertidumbre.

## 15. MPC y propagación de estados

En cada ciclo: obtener estado observado/simulado; construir ventana con forecast disponible en ese instante; resolver; comprobar algebra e integridad independientemente; implementar sólo los primeros $m$ intervalos; medir/simular el estado resultante; persistirlo; desplazar el reloj. El sufijo previsto no se cuenta como ejecutado ni como costo realizado.

$$x_{k+m}^{real}=\Phi_{phys}(x_k^{real},u_{k:k+m-1}^{aplicado},w_{k:k+m-1}^{real});\quad x_{0|k+m}=x_{k+m}^{real}.\tag{M23}$$

$\Phi_{phys}$ no forma parte del MILP. En el modo algebraico se utiliza M07/M18 y la máquina de estados para verificar la lógica de MPC; ese modo no se presenta como validación física. El modo físico corrige la siguiente ventana con estados reales del simulador. También transporta la potencia realmente entregada y el tiempo acumulado de modos. Un déficit de seguimiento se registra como tal; no se reescribe retroactivamente el setpoint.

La API física debe conservar toda su memoria interna. En el commit base, `_simulate_states` de la PEMFC reinicia OFF/potencia cero en cada simulación; invocarlo desde cero por minuto sería incorrecto para M23. El futuro adaptador debe exponer inicialización/checkpoint/avance continuos o demostrar equivalencia de una alternativa con una simulación monolítica, incluyendo arranque y parada. No confundir una función de simulación de perfil completo con una API `step` ya existente.

Para $m>1$, ejecutar secuencialmente los $m$ intervalos, comprobando eventos y límites en cada uno. No transportar el estado terminal de los $N$ pasos cuando sólo se ejecutaron $m$. Ante desviación que invalide el plan, reoptimizar o detener/usar una política de contingencia previamente validada, con bandera explícita. La última solución sólo puede reutilizarse si su sufijo sigue siendo factible en el estado actual.

## 16. Incertidumbre y validez

El prototipo inicial es determinista con realimentación. MPC no elimina incertidumbre ni garantiza robustez. La validación introduce sesgo, errores temporales correlacionados, rampas de demanda, nubosidad y pérdidas de disponibilidad; las amplitudes se identifican con datos o se declaran escenarios sintéticos, no probabilidades calibradas.

Extensión estocástica: escenarios $\omega$ con $\pi_\omega$, costo esperado $\sum_\omega\pi_\omega J_\omega$, restricciones físicas por escenario y no anticipatividad para **todas** las decisiones con historia común, incluyendo estados discretos. En dos etapas, al menos la primera acción debe ser común. Definir cuándo se revela la incertidumbre; dar a cada escenario conocimiento de todo su futuro crea una relajación optimista. La explosión de tamaño se mide antes de ofrecerla en la UI.

Extensión robusta: conjuntos de error o reservas de potencia y energía con tiempo de sostén explícito. Un margen porcentual fijo de potencia no demuestra reserva energética BESS ni disponibilidad de H2. Chance constraints requieren distribución y nivel de riesgo calibrados; no forman parte del prototipo aprobado.

## 17. Integridad y certificación de cada solución

Antes de aceptar un plan: todos los parámetros/variables finitos; dominios íntegros; balance M02; M03-M18 aplicables; estado inicial y obligaciones; ausencia de simultaneidad; costos reconstruidos; estado/gap/límite del solver. Comprobar también coeficientes escalados y no linealidades inadvertidas. El evaluador trabaja desde datos canónicos y tablas de resultados, sin consultar expresiones/constraints del modelo Pyomo.

Separar `solver_status`, `algebraic_feasibility`, `service_status`, `physical_validation` y `execution_state`. Una corrida técnicamente concluida puede tener servicio degradado o validación física rechazada. `time_limit` con incumbent factible no equivale a `optimal`; sin incumbent no hay plan implementable. `infeasible`, `unbounded`, error numérico e interrupción no se convierten en soluciones por clipping.

Diagnóstico de inviabilidad: primero verificar datos y estado; después, si procede, resolver una copia elástica con holguras **identificadas por familia y unidades**, únicamente para explicar conflictos. Su solución no se ejecuta ni entra como resultado factible. No prometer IIS para todas las versiones de la interfaz: probar soporte o usar diagnóstico elástico registrado.

## 18. Casos analíticos de referencia

Todos los valores siguientes son **fixtures sintéticas**, no parámetros físicos de SEEDS2.

| Caso | Entrada | Resultado analítico esperado |
|---|---|---|
| A01 | 60 kW durante 60 min, sin almacenamiento | 60 kWh; 60 intervalos y 61 estados |
| A02 | 10 kW durante un minuto | $1/6$ kWh; un intervalo |
| A03 | $C=100$ kWh, SOC=0,60, descarga bus 9 kW, $\eta^d=0,9$, 1 h | $e_1=50$ kWh, SOC=0,50 |
| A04 | Mismo estado inicial; carga bus 10 kW, $\eta^c=0,9$, 1 h | $e_1=69$ kWh, SOC=0,69 |
| A05 | FV=20 kW, carga=10 kW, BESS admite 10 kW, 1 h, terminal no vinculante | Carga BESS 10 kWh bus; aumento interno 9 kWh con $\eta^c=0,9$ |
| A06 | Segmento FC (10 kW; 0,7 kg/h)-(20 kW; 1,1 kg/h), potencia 15 kW, 1 min | $q=0,9$ kg/h, masa 0,015 kg; OFF da cero; 5 kW no pertenece al dominio ON |
| A07 | Generador con $P_{min}=20$ kW, demanda=5 kW, obligado ON, sin BESS ni descarte | Inviable; no crear 15 kW de vertimiento ficticio |
| A08 | Capacidad útil 5 kW, demanda interrumpible 10 kW, 1 h | Servicio degradado con EENS=5 kWh; con servicio duro, inviable |

## 19. Mapa de ecuaciones para implementación

| Bloque propuesto | Ecuaciones | Auditoría principal |
|---|---|---|
| `timebase` | M01 | Cardinalidad, duración y energía |
| `network` y `renewable` | M02-M05 | Frontera, balance y destinos físicos |
| `storage` | M06-M08 | Energía y exclusividad por banco |
| `commitment` | M09-M12 | Estado inicial, transiciones, rampas y memoria |
| `pemfc_pwl` | M13-M17 | Caudal directo, dominio y exactitud del interpolante |
| `hydrogen_stock` opcional | M18 | Masa y capacidad física declarada |
| `thermal` y `objective` | M19, M21-M22 | Unidades monetarias y prioridades |
| `modes` opcional | M20 | Arranque multietapa con datos |
| `mpc` | M23 | Sólo estados de acciones ejecutadas |

Estas ecuaciones constituyen el contrato propuesto. Toda restricción añadida, retirada o aproximada en un PR debe vincularse a un requisito y a un ensayo de la matriz del dossier.
