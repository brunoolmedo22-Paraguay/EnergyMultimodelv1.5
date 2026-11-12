# CONTINUAÇÃO IMEDIATA — INSTRUÇÕES PARA O PRÓXIMO AGENTE

> Seção viva: atualizada a CADA checkpoint publicado do Piso 3D-B2. Se a sessão anterior foi interrompida, este bloco e o
> último commit publicado bastam para continuar. Histórico das entregas anteriores: logo abaixo e em `PARAMIJEFE.md`.

| Item | Estado |
|---|---|
| **Branch** | `claude/stoic-meitner-2vs91m` (base `main` `724d235`) |
| **PR** | Draft [#24](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/24) contra `main` — **NÃO FAZER MERGE** sem autorização expressa do responsável |
| **Último checkpoint publicado** | ver `git log -1` da branch; tabela «Checkpoints do 3D-B2» abaixo |
| **Missão em curso** | Piso **3D-B2** — integração visual da plataforma (autorizado pelo responsável após aprovar o 3D-B3 no HEAD `590b826`, CI verde nos dois ambientes) |

## Checkpoints do 3D-B2

| # | Unidade | Estado | Commit |
|---|---|---|---|
| C0 | Três correções focalizadas pedidas antes da expansão: (A) N/D × não aplicável por EVIDÊNCIA (`termo`/`declarado`, `F.objetivo.termos`), (B) zero negativo só na formatação (`nf`/`ne`), (C) limpeza garantida dos servidores E2E (`tools/e2e/servidor.sh`) | **concluído** | `d4f7780` |
| B2-A | Barra lateral compacta (hover/foco), barra inferior no celular, paleta neutra da Partitura no tema, navegação anterior preservada, estável em reruns | **concluído** (ver «B2-A — o que existe») | commit «B2-A» |
| B2-B | Catálogo integrado ao Gestor + Planta com barramento equivalente (hover/foco/seleção, dados reais do inventário e da rodada, abrir painéis por UID; sem fluxos inventados) | não iniciado | — |
| B2-C | Caderno de Ensaios (cenários e rodadas: versões, motores, estados, datas, integridade; locais e Arquivo Científico; V1.6 compatível) | não iniciado | — |
| B2-D | Folha de Ensaio (organização aprovada no protótipo sobre os formulários longos; parâmetros, validações, estados iniciais e preflight intactos) | não iniciado | — |

## B2-A — o que existe (implementado e verificado)

- `seeds2/ui/static/trama/sidebar.js` + regras `.pt.sb` em `trama.css`: componente v2 `seeds_sidebar` (trilho fixo de 56 px que se expande por cima do conteúdo com hover/foco; ≤ 760 px vira barra inferior só com os itens `movel`). Só navega: devolve `{type:"nav", view, tab}` ou `{type:"switch"}`.
- `seeds2/ui/trama.py`: `_pagina(nome)` (fábrica dos componentes de PÁGINA na linguagem Partitura: `trama.js` + `<nome>.js` + `trama.css`), `sidebar()`, `RAIL_CSS` (variável `--seeds-rail`; o conteúdo recua a largura do trilho). `trama.js` ganhou `raizPt`, `temaPt`, `icoPt` (raiz/tema/ícone comuns).
- `seeds2/ui/shell.py`: `sidebar_items()` (tabela de destinos por contexto: sem microrrede / comissionamento / microrrede ativa), `_on_sidebar()`, `sidebar()`; **a barra lateral é desenhada dentro de `shell.topbar()`**.
- `.streamlit/config.toml`: paleta neutra da Partitura (claro e escuro) e raios; cores categóricas dos gráficos nativos inalteradas.
- Testes: `tests/test_piso3db_plataforma.py` (destinos por contexto, retorno do componente, estáticos, tema); navegador: `tools/e2e/e2e_piso3db_plataforma.js` (21 verificações; fase 3 de `run_piso3db.sh`).
- Verificado neste checkpoint: suítes AppTest de todos os pisos + Partitura + guardas ⇒ **150 passed** (`tests/test_app_smoke.py tests/test_seeds2_*app.py tests/test_piso3d*_app.py tests/test_piso3db_{plataforma,trama,nd}.py tests/ems_v2/test_piso3db_guardas.py`); auditoria do diff `ok: true`. **Regressão completa com e sem solver ainda NÃO executada sobre este checkpoint** (última: `590b826`); executar no fim do B2-B.
- **Restrição descoberta (não contornar):** `seeds2/ui/main.py`, `seeds2/ui/operations.py`, `seeds2/operation/runner.py` e `thermal_app.py` estão FIXADOS por SHA-256 na guarda de estabilização (`tests/fixtures/stabilization_scope_v1.json`). Não podem ser alterados. Consequência para o 3D-B2: **páginas novas não podem ganhar uma `view` nova em `main.py`**; entram como `tab` do Centro de Operação (`view=operacao&tab=…`, despachadas em `operation_center.render`) ou dentro de `gestor.render()`.
- Pendências visuais conhecidas do B2-A: restam acentos verde-azulados fixos no CSS de algumas páginas (`gestor.py`, `operation_center.py`: chip do herói, gradiente); a barra superior anterior quebra mal a 400 px (já era assim antes do B2); a barra lateral ainda não tem os destinos Planta/Caderno/Folha (entram com B2-B/C/D).

## Próxima tarefa exata (B2-B) e critérios de aceitação

1. **Catálogo** dentro de `seeds2/ui/gestor.py` (acima da lista atual, que continua inteira): componente de página `catalogo.js` com um cartão por microrrede (nome, assinatura do barramento a partir do inventário real, natureza/modo, cenários e rodadas por estado, kWp/kW/kWh instalados, prontidão) e a prateleira de estudos do Arquivo Científico; clique abre a microrrede pelo fluxo existente (`session.open_microgrid`). Catálogo vazio ⇒ estado vazio com «Nova microrrede».
2. **Planta** como `tab=planta` do Centro de Operação: barramento equivalente; um nó por equipamento do inventário (UID, nome, TAG, nominal), demanda e PCC; hover/foco/seleção; com uma rodada V2 concluída escolhida, valores gravados do instante (marco `trama_frame`); clique abre o painel do recurso na Partitura (gravar `{ex, uid}` em `sessionStorage["seeds2.partitura.<run>"]` e navegar para `tab=rodada&run=`). **Sem setas nem fluxos nas ligações.** Inventário vazio e vários equipamentos por tecnologia têm de funcionar.
3. Aceitação: testes de modelo (Node) + AppTest + E2E em navegador real (clique, hover, UID, inventário vazio); barra lateral ganha «Planta»; nenhum teste anterior alterado para passar; auditoria do diff `ok`.

## Como retomar

1. `git fetch origin && git checkout claude/stoic-meitner-2vs91m && git pull`; ler `CLAUDE.md`, este bloco e `docs/seeds2/PARTITURA_3DB.md`.
2. Ambientes: Python 3.13 + `pip install -r requirements.txt -r requirements-ems_v2.txt pytest` (com solver) e outro só com
   `requirements.txt pytest` (sem solver). Node 22 + Chromium/Playwright para a bancada e os E2E. Sempre `PYTHONDONTWRITEBYTECODE=1`.
3. Testes focalizados do Piso 3D-B (≈ 6 min com solver):
   `python -m pytest tests/test_piso3db_trama.py tests/test_piso3db_nd.py tests/test_piso3db_lentes.py tests/test_piso3db_app.py tests/test_piso3db_e2e_servidor.py tests/ems_v2/test_piso3db_guardas.py -q -p no:cacheprovider`
4. Navegador real: `tools/e2e/run_piso3db.sh <python com solver> <pasta nova>`; auditoria do diff: `python tests/ems_v2/piso3db_guard_policy.py` (tem de dar `ok: true`).
5. Regressão completa (com solver ≈ 16 min; sem solver ≈ 9 min): `python -m pytest tests/ -q -p no:cacheprovider` nos dois ambientes, **no HEAD final de cada entrega importante**.

## Referência visual e fontes do protótipo aprovado

A linguagem visual é a **Partitura V2 aprovada** (não criar outra): tokens e classes em `seeds2/ui/static/trama/trama.css`
(tudo sob `.pt`; paleta neutra, painéis de raio 14 com linha de acento, diálogo de raio 18). O protótipo navegável aprovado
(barra lateral, Catálogo, Planta, Caderno, Folha) NÃO está no repositório: foi entregue ao responsável como artefato; a
descrição das telas está em `docs/seeds2/PARTITURA_3DB.md` §8 (plano do 3D-B2).

## Restrições e decisões já aprovadas (não reabrir)

- Não alterar `ems_v2/`, modelos físicos (`models/`, `h2_pemfc/`, `simulation/`, `config/`, `ems_integration/`, `reference_models/`), contratos nem persistência sem autorização. Auditoria nominal: `tests/ems_v2/piso3db_guard_policy.py` (todo arquivo NOVO de teste precisa entrar em `TESTES_3DB`/`ADICIONADOS`).
- **R-1, R-2 e R-3 continuam pendentes e separados desta missão** (não corrigir).
- Nenhum fluxo anterior pode desaparecer durante a migração; a vista clássica da rodada V2 fica num expansor recolhido (C-3DB-05); não enfraquecer asserções de testes de interface.
- N/D em três estados no JavaScript (C-3DB-04) e, desde o C0, «não aplicável» só com evidência (C-3DB-07).
- A interface descreve; não atribui causas; a Planta não pode inventar fluxos físicos nas conexões.
- Checkpoints frequentes: commit + push + este bloco atualizado ANTES de começar outra funcionalidade.

---

> **PISO 3D-B3 — N/D EN EL NAVEGADOR + LENTES DECISIÓN / ECONOMÍA / EVIDENCIA (2026-11-12, misma rama `claude/stoic-meitner-2vs91m`, mismo PR Draft [#24](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/24), SIN merge):** el responsable aprobó el checkpoint 3D-B0/B1 **solo para continuidad** y pidió, en este orden: (1) **corrección N/D en JavaScript** — hecha: tres estados que no se confunden (número = grabado; `null` = AUSENTE ⇒ «N/D», no se suma ni se dibuja como cero y vuelve N/D todo derivado; `undefined` = NO APLICABLE ⇒ se omite), en el modelo de vista, en el motor Trama y en los paneles (antes había `|| 0`, `fill(0)` y `100 * null`); (2) **lentes** Decisión (tapete de decisiones, selección de ventana, plan MPC × plan largo × ejecutado, V(E) solo con puntos grabados, ventanas sin señal explícitas, lo que se sabía × lo que ocurrió después), Economía (costo realizado por intervalo/acumulado/componente, bloque previsto × realizado, objetivo MILP ≠ costo ≠ valor futuro) y Evidencia (verificación del SERVIDOR, tres aceptaciones, auditoría, solver por decisión, procedencia, archivos con SHA-256, tablas originales, advertencias y limitaciones); (3) **vista clásica plegada por defecto** en un expansor identificado cuando la Partitura se dibuja (contenido íntegro, `_vista_classica`); (4) **cobertura**: dos bancos y dos unidades PEMFC por UID, contrato v1, ventanas sin señal, cambio de lente sin perder el instante, cambio de rodada, sesión nueva sin solver, 12 h / 24 h (m = 2) / paso de 30 min, microrred aislada. Marco `seeds2-trama-frame` **v2** (solo añade lecturas de archivos ya grabados: planos, coordinaciones, auditoría, tablas). Sin cambios en `ems_v2/`, modelos físicos, contratos ni persistencia. Hallazgos propios corregidos: clave de caché del marco para estudios archivados (C-3DB-06) y columna ancha de la lente Decisión en móvil. Hallazgo ajeno registrado: el guion `tools/e2e/e2e_piso3da_v2.js` ya estaba desactualizado en `main` (etiqueta del formulario renombrada en un piso posterior); se actualizó solo esa etiqueta. **R-1, R-2 y R-3 siguen sin corregir.** Verificado sobre `6bef66c`: regresión completa **con solver 2284 passed, 2 skipped** (= 2249 + 35) y **sin solver 1769 passed, 172 skipped**; E2E real `run_piso3db.sh` **103 verificaciones** con servidor sin solver y motor/modelos saboteados (registro vacío); E2E 3D-A (106), 3D-A2-R y 3D-A2-H (60) aprobados con la vista clásica plegada; auditoría explícita del diff `ok`. Detalle: `PARAMIJEFE.md` Entrega 17; diseño y decisiones C-3DB-04…06: [`docs/seeds2/PARTITURA_3DB.md`](../seeds2/PARTITURA_3DB.md). **Próximo paso (solo tras revisar este checkpoint):** 3D-B2 — barra lateral, Catálogo, Planta, Caderno de Ensaios, Folha de Ensaio.

> **PISO 3D-B0/B1 — PARTITURA + MOTOR TRAMA (2026-11-11, rama `claude/stoic-meitner-2vs91m` desde `main` `724d235`, PR Draft contra `main` SIN merge):** dirección de diseño **Partitura V2 aprobada por el responsable** e implementación autorizada. Integrado en la aplicación real: marco de datos `seeds2-trama-frame` (`integracao_v2/trama_frame.py`, solo lectura de los datos persistidos, sin solver ni modelos), motor gráfico Trama en SVG sin dependencias (`seeds2/ui/static/trama/`), componente v2 `seeds2/ui/trama.py` y el instrumento en la página de la rodada V2 (local y estudio archivado): lente **Operación**, inspector, y **explorador de recursos** con los siete paneles (PEMFC con sus tres vistas). La vista clásica permanece debajo. **No integrado todavía (solo prototipo):** lentes Decisión/Economía/Evidencia, barra lateral, Catálogo, Planta, Caderno, Folha, exportación de figuras, series climáticas en los paneles solar/eólico. Verificado: 15 tests nuevos; E2E real `tools/e2e/run_piso3db.sh` con **40 verificaciones** sobre servidor sin solver y con motor/modelos saboteados (registro de llamadas vacío); regresión completa con solver **2249 passed, 2 skipped** (= 2234 + 15). Guardas: excepción nominal C-3DB-01. Pendientes técnicas R-1/R-2/R-3 registradas y NO corregidas. Detalle: [`docs/seeds2/PARTITURA_3DB.md`](../seeds2/PARTITURA_3DB.md) y `PARAMIJEFE.md` Entrega 16. **Próximo paso propuesto:** 3D-B2 (navegación: barra lateral, Catálogo, Planta, Caderno, Folha) o 3D-B3 (lentes Decisión, Economía, Evidencia), a decisión del responsable.

> **PISO 3D-A2-H (2026-11-11, rama `claude/adoring-newton-jzfmfx` desde `main` `0c9df80`, PR contra `main` SIN merge):** PEMFC/H₂ no EMS V2 — curva q_H₂(P_líq) do modelo físico gerada UMA vez por configuração e reutilizada em toda a missão, certificado B04 verificável no núcleo (C-3DA2H-01 autorizado), verificação dinâmica, persistência v3 e bancada H₂. **Política B04 `b04-proposta-2` APROVADA pelo responsável** (commit `8be5de4`; certificação MATEMÁTICA da PWL, não validação experimental); decisões C-3DA2H-02…05/08…11 aprovadas; verificações finais A (malha densa) e B (fluxo completo sem aprovação simulada) concluídas; **C-3DA2H-12 aprovada** (resíduo das rampas de descida aceito, sem termo de rampa no MILP, 7 condições). Alcance 3D-A2-H tecnicamente aceito para ENSAIOS reproduzíveis; integração em `main` só com autorização expressa do responsável. Relevo: [`RELEVO_3DA2H.md`](RELEVO_3DA2H.md); documento técnico: [`INTEGRACAO_3DA2H.md`](../ems_v2/INTEGRACAO_3DA2H.md); seção «Piso 3D-A2-H» no fim deste arquivo. 3D-A2-T e 3D-B NÃO autorizados.

> **PISO 3D-A2-R (2026-11-11, rama `claude/adoring-newton-jzfmfx` desde `main` `7eb29e5`, PR [#22](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/22) contra `main` SIN merge):** FV (por arranjo) e eólica (por registro) no EMS V2, com potencial derivado pelos modelos físicos do SEEDS2 sobre o clima previsto, persistência v2 por UID e reabertura sem modelos nem solver. Relevo: [`RELEVO_3DA2.md`](RELEVO_3DA2.md); documento técnico: [`INTEGRACAO_3DA2R.md`](../ems_v2/INTEGRACAO_3DA2R.md); seção «Piso 3D-A2-R» no fim deste arquivo. 3D-A2-H, 3D-A2-T e 3D-B NÃO autorizados.

> **PISO 3D-A — PUBLICADO COMO DRAFT, SIN MERGE (2026-11-11):** rama `claude/adoring-newton-jzfmfx` desde `main` `a636350`; **PR Draft [#21](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/21)**. Integración operativa del EMS V2 jerárquico (GATE 0 + GATE 1 del paquete maestro 3D). Relevo completo para otro agente: [`RELEVO_3DA.md`](RELEVO_3DA.md); resumen en la sección **«Piso 3D-A — integración operativa del EMS V2»** al final de este archivo. Desarrollo DETENIDO por orden del responsable: la auditoría y las correcciones siguientes se coordinan externamente. No iniciar 3D-B/3D-C; sin merge.

> **MATH-01 (2026-11-10, rama `claude/admiring-ritchie-pj4fn9`, PR contra `main` sin merge):** correcciones P1-1 (signo del ajuste terminal en `hierarquia/comparadores.efeito`: d − p·ΔE) y P1-2 (`hierarquia/planejador.Planejador3C4.sinal`: cola agotada antes del fin de misión ⇒ señal `indisponivel`, replanificación/degradación existentes; b = fin = K_M sigue Φ_L exacto) de la auditoría matemática independiente sobre `9ebd760` (dictamen: aprobado para 3D con condiciones; sin P0). Formulación, MILP, MPC, políticas numéricas, fixtures y referencias intactos. Tests `tests/ems_v2/test_ems_v2_3c4_math01.py` (4 de 5 fallaban antes). Verificado: 3C-4 focalizado 252 passed; suite completa con Pyomo/HiGHS `python -m pytest tests/ -q` **2080 passed** (= 2075 + 5), 9 warnings, 128 subtests, 571 s; guardias de isolamento/estabilización sin cambios. Detalle: `PARAMIJEFE.md` § MATH-01. Condiciones 3D pendientes (no son defectos): N·Δ >= max(T_on, T_off) por unidad; costo térmico M19 no implementado (excluir térmicas del 1er caso 3D o implementarlo); parámetros reales (Φ_L, D07, PCC/tarifas, estimador de estado). **Próximo paso:** revisión humana del PR y decisión de inicio de 3D.

> **Estado combinado del PR #18:** PR #17 / 3C-4 ya integrado en main `19aa3ac328f337e31ec4c36baa837c056299a57a`. Se conserva íntegro a continuación su HANDOFF científico original como registro de la entrega. La ampliación eólica permanece en revisión en PR #18, sin merge en main; cierre y nueva regresión en [INTEGRACAO_3C4_PR18.md](../eolica/INTEGRACAO_3C4_PR18.md).

# SEEDS2 — Cuaderno de relevo entre agentes (HANDOFF)

> **Fuente de continuidad operativa.** Leer junto con [CLAUDE.md](../../CLAUDE.md) antes de comenzar cualquier sesión. Mantener breve, con hechos verificables, fecha y referencias a PRs. El código y los tests son la fuente de verdad funcional.

**Actualización:** 2026-11-09 · **rama:** `ccr-50f8fad7-s073ob` · **PR:** [#17](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/17) contra `main`, sin merge · **auditoría del PR #17 (commit `9630e73`): A01, A02 y hotfix B3C4-01 aplicados en `c964a2e`; 2ª auditoría (HEAD `8f48aed`): hotfix autorizado B3C4-10 aplicado en `8efc927`; cierre A03 (HEAD `8dd8edb`) en `322ffa6`** · **estado:** **Piso 3C-4 — EMS jerárquico MILP–MPC (planificador de largo plazo, costo de continuación y valor futuro)** implementado y verificado en la rama; **no integrado** (sin UI/runtime/catálogo; algebraico, fixtures y tarifas sintéticas). **No iniciar 3D.**

> **Informe técnico vigente: [`PARAMIJEFE.md`](../../PARAMIJEFE.md) — Entrega 12**; formulación, método, decisiones D-3C4-* y contradicciones C-3C4-* en [`docs/ems_v2/FORMULACAO_3C4.md`](../ems_v2/FORMULACAO_3C4.md); trazabilidad y hashes protegidos en [`MATRIZ_3C4.md`](../ems_v2/MATRIZ_3C4.md); evidencia en [`EVIDENCIA_3C4_EJECUCION.md`](../ems_v2/EVIDENCIA_3C4_EJECUCION.md); brechas en [`BRECHAS_3C4.md`](../ems_v2/BRECHAS_3C4.md); transición en [`TRANSICAO_3C4_3D.md`](../ems_v2/TRANSICAO_3C4_3D.md).

## 1. Estado actual

- `main` (`10365c5`): V1.6 + PR #1–#16 (3A, 3B-P, 3C-0, 3C-1, 3C-2 y 3C-3 integrados). Línea de base `tests/ems_v2` medida en esta sesión antes de cambiar nada: **1080 passed** (con `requirements.txt` + `requirements-ems_v2.txt` instalados).
- Rama `ccr-50f8fad7-s073ob` desde `main`: **Piso 3C-4** (sección 2). Desde `10365c5` NINGÚN archivo existente de `ems_v2` fue modificado; solo 4 guardias de tests ajustadas nominalmente (C-3C4-02). V1.6, `seeds2`, aplicación y `requirements*.txt` intactos; la aplicación no referencia `ems_v2`.

## 2. Última entrega — Piso 3C-4 (esta rama)

- **Implementado:** `ems_v2/hierarquia/` (solo biblioteca estándar): `contrato` (TermoTerminal3C4, SinalValorFuturo sellado, EntradaHierarquica3C4, ConfiguracaoPlanejador3C4, validaciones de señal × entrada × ventana), `valor` (evaluación exacta: interpolante 1D, envolvente 2D, lineal local), `auditor` (auditor terminal independiente), `planejador` (plan largo + V^tail por reoptimización paramétrica auditada, PWL con refinamiento y dominio de factibilidad, 2D convexo verificado, sensibilidad local, referencias), `mpc` (`ControladorMPCHierarquico`, `ResolvedorMILP3C4`, registros de coordinación/vínculo/misión), `auditoria` (auditoría integral + retomada verificada), `comparadores` (reoptimización × anticipación × información perfecta con condiciones terminales), `experimentos`; `ems_v2/milp/{modelo,solver,resultado,evidencia}_3c4.py`; `ems_v2/fixtures_3c4.py`.
- **Verificado (2026-11-09):** 101 tests nuevos (`tests/ems_v2/test_ems_v2_3c4_*.py`); `tests/ems_v2` **1181 passed** (sin Pyomo: 794 passed, 42 skipped); suite completa **1635 passed, 7 warnings, 128 subtests** (445,4 s) = 1534 + 101. Evidencia: `python -m ems_v2.milp.evidencia_3c4` (salida en `EVIDENCIA_3C4_EJECUCION.md`).
- **Resultados clave (sintéticos):** H2 anticipación R$ 10,2 con condiciones terminales iguales (60,4 × 50,2); H1/H3 ⇒ 0; H7/H8 (tarifa plana, límite/indisponibilidad del PCC) MPC sin señal INVIABLE × jerárquico concluye; H17 dos bancos R$ 5,3; reoptimización 0 en todas las instancias; local indisponible en quiebres.
- **Hallazgos:** C-3C4-01 (visión núcleo `ResultadoNucleo3C3De3C4`), C-3C4-02 (guardias nominales), **C-3C4-03 / B3C4-01: deriva numérica HEREDADA de la energía ejecutada (C + 2 ulp) que la validación sin recorte convierte en interrupción — NO corregida, requiere autorización** (reproducida en `test_h9_linha_de_base_*`), C-3C4-04 (campo 3C-0 `valor_futuro` intacto). B3C4-02: `cumprir_na_janela` cuesta R$ 2,0 en H9.
- **Auditoría del PR #17 (commit `9630e73`; arquitectura favorable)** — los tres defectos reproducidos antes de corregir (EVIDENCIA_3C4 §4):
  - **A01:** el registro final de misión re-sellado con contagens/energías/valoración/hash de red/`missao_uid`/tiempos falsos pasaba la auditoría integral; ahora cada campo se confronta con su fuente (objetos de configuración obligatorios; tiempos = suma de mediciones selladas, no reproducibles).
  - **A02:** `inviavel` solo con certificado de cobertura (MILP con energía inicial libre, `resolver_cobertura_3c4`); sin él `dominio_indeterminado` ⇒ señal indisponible; `diagnostico_modos`; dominio = aproximación interna; convexidad 2D "en la muestra".
  - **B3C4-01 (hotfix AUTORIZADO):** proyección numérica de la energía al límite si exceso ≤ min(tolE, 16·u·S), reconstruible bit a bit; archivos protegidos modificados: `ems_v2/ponte/execucao.py`, `ems_v2/rede/execucao.py` (guardia de diff). E1–E8/G1–G15/3C-0/3C-1 idénticos.
  - **B3C4-10:** `P_imp = −8,88e-16` del solver rechazado por la regla C-01 del 3C-3 ⇒ H9 3C-3 sin señal y referencia dura se detenían en k = 10 (corregido en la 2ª auditoría, abajo).
  - Verificado: suite `test_ems_v2_3c4_auditoria_pr17.py` 38 passed; 3C-4 139 passed; `tests/ems_v2` **1220 passed (= 1181 + 38 + 1 guardia del hotfix)** (sin Pyomo 812 passed, 63 skipped); suite completa **1674 passed, 7 warnings, 128 subtests (449,9 s) = 1635 + 39**.
- **2ª auditoría del PR #17 (HEAD `8f48aed`) — hotfix AUTORIZADO B3C4-10 (`8efc927`):** política `residuo_numerico_pcc_v1` SOLO en la extracción de `resolver_3c3`/`resolver_3c4`: v < 0 del SOLVER con |v| ≤ min(16·u·S_t, 1e-7, tolP D07) ⇒ 0,0 con registro (resultado, resolución sellada, registro 3C-0 aviso + hash) y reconstrucción en la auditoría (`reconstruir_normalizacoes_pcc`); mayores ⇒ solución rechazada. **C-01 idéntica a la base** (guardia AST): consignas/programas externos negativos/NaN/Inf/bool/incompletos siguen rechazados. Protegidos modificados: `rede/execucao.py`, `milp/solver_3c3.py`, `milp/resultado_3c3.py`, `rede/mpc.py` (FORMULACAO_3C4 §10c). H9 × 5: todas concluyen con E = 0, PEMFC encendida, sin obligaciones; sin señal 129,8; PWL/dura/blanda 129,6; horizonte completo 127,6 (brecha 2,0 = B3C4-02). Verificado: nueva suite 66 passed; `tests/ems_v2` **1287 passed** (sin Pyomo 859 passed, 83 skipped); suite completa **1741 passed, 7 warnings, 128 subtests (451,8 s)**.
- **Cierre C-3C4-A03 (HEAD `8dd8edb`, `322ffa6`):** A03-1 — las tres evidencias de una normalización (código en la resolución sellada, avisos y hash en el registro 3C-0) todas presentes y coherentes o todas ausentes; A03-2 — verificador único `rede/auditoria.reconstruir_normalizacoes_pcc` (sin dependencia de `hierarquia`) en la auditoría integral 3C-3 (sección `normalizacoes_pcc`), reutilizado/espejado por la 3C-4. Política B3C4-10 y C-01 intactas (guardia contra `8dd8edb`); registro histórico G11 de `10365c5` aceptado sin obligación nueva. Verificado: suite A03 18 passed; `tests/ems_v2` **1308 passed** (sin Pyomo 862 passed, 101 skipped); suite completa **1762 passed, 7 warnings, 128 subtests (458,3 s)**.
- **Decisiones:** D-3C4-01..08 (FORMULACAO_3C4 §10).
- **No implementado (fuera de alcance):** >2 bancos o 2D no convexo, incertidumbre estocástica del valor futuro, segunda resolución temporal, modos con obligación residual elegible, integración (3D).

## 3. Próxima misión propuesta

Re-auditoría del PR #17 tras el cierre A03 y decisión de integración por el responsable (sin merge automático). 3D (integración con catálogo/UI/runtime) **no autorizado**; interfaces en `TRANSICAO_3C4_3D.md`.

---

## Histórico — entrega anterior: Piso 3C-3 · Red eléctrica e intercambio (PR #16, integrado en `10365c5`)

- `ems_v2/rede/` (PCC, tarifas, auditor, ejecución programado × realizado, anexo 3C-3, MPC conectado, retomada, auditoría integral/analítica) + `ems_v2/milp/*_3c3.py` + `ems_v2/fixtures_3c3.py`; correcciones C-01/C-02/C-03 de la auditoría aplicadas. Verificado entonces: `tests/ems_v2` 1080 passed; suite 1534 passed. Informe: `PARAMIJEFE.md` Entrega 11.

## Histórico — entrega anterior: Piso 3C-2 · MPC recedente (PR #15, integrado en `a4c6b1c`)

- `ems_v2/mpc/` (reloj, K6, previsión por ventana, orquestador, registros, retomada, auditoría, métricas, comparadores, E1–E8) + `ems_v2/fixtures_3c2.py`; correcciones C-01/C-02 de la auditoría aplicadas. Verificado entonces: `tests/ems_v2` 824 passed; suite 1278 passed. Informe: `PARAMIJEFE.md` Entrega 10.

## Histórico — entrega anterior: Piso 3C-1 · Unit Commitment dinámico (PR #14, integrado en `55440f4`)

- `ems_v2/compromisso/` (contrato embrulho, discretización, memoria, preflight, auditor independiente) + `ems_v2/milp/*_3c1.py` (`resolver_3c1`) + `ems_v2/ponte/compromisso.py` y `registro_3c1.py`; auditorías A-01..A-03, B-01/B-02 y B-03 aplicadas. Verificado entonces: `tests/ems_v2` 717 passed; suite 1171 passed. Informe: `PARAMIJEFE.md` Entrega 9.

## Histórico — entrega anterior: Piso 3C-0 · Puente científico (PR #13, integrado en `81aa09c`)

- `ems_v2/ponte/` (inventario por UID, requisitos, escenario/previsión/realización, proyección, plan → ejecución → estado, preflight, registro sellado, instrumentación) y `ems_v2/ponte_seeds2/leitor.py` (solo lectura, C-3C0-01 aceptada condicionalmente); auditorías H-01..H-04 y C-01..C-03 aplicadas. Verificado entonces: `tests/ems_v2` 535 passed; suite 989 passed. Informe: `PARAMIJEFE.md` Entrega 8.

## Histórico — entrega anterior: Piso 3B-P · Primer MILP Pyomo + HiGHS (PR #12, integrado en `3c65d98`)

- `ems_v2/milp/` con `resolver(entrada, configuracao, compromisso_fixo)`: MILP de una ventana (M02, M03-v1.1, M04, M06–M08, M10 con compromiso fijo constante, M14–M16 PWL sin SOS), clasificación de terminación y aceptación solo tras auditor independiente; correcciones C-3B-01/02/03. Verificado entonces: `tests/ems_v2` 416 passed; suite 870 passed. Informe: `PARAMIJEFE.md` Entrega 7.

## Histórico — entrega anterior: Piso 3A · Fundaciones del EMS MILP–MPC (PR #11, integrado en `f6d009d`)

- Contratos canónicos por UID, malla N/N+1, referencia racional exacta, auditor independiente, catálogo M01–M23 + v1.1 (150 símbolos, 42 ecuaciones); auditoría favorable con correcciones C-3A-01..04. Verificado entonces: `tests/ems_v2` 268 passed; suite 722 passed. Informe: `PARAMIJEFE.md` Entrega 6.

## Histórico — entrega anterior: Piso 2D-B · Relatórios Científicos e Exportações (PR #10, integrado en `8556b71`)

- `RunDossier` unificado (rodada local × archivada), PDF científico/diagnóstico, Excel completo (doubles con `repr`; Excel garantiza 15 dígitos), figuras PNG/SVG y ZIP `seeds2-figures`; auditoría favorable + corrección C-04. Verificado entonces: 454 passed; E2E 2D-B 57/57 + 157/157 descargas. Informe: `PARAMIJEFE.md` Entrega 5.

## Histórico — entrega anterior: Piso 2D-A · Arquivo Científico Portátil (PR #9, integrado en `3b73971`)

- Paquete `seeds2-study` v1 (`.seeds2study.zip`), inspección de paquetes no confiables, Arquivo Científico de la instalación (banco propio, importación atómica, identidad local ≠ origen), consulta histórica sin recalcular; auditoría favorable + corrección C-03. Verificado entonces: 407 passed; E2E 2D-A 62/62. Informe: `PARAMIJEFE.md` Entrega 4.

## Histórico — entrega anterior: Piso 2C · Execução EMS e Persistência Científica (PR #8, integrado en `34a8b52`)

- Etapas 03 Estrategia EMS y 04 Ejecución; preflight (fases A/B) que BLOQUEA lo no representable; runner en thread propio; persistencia v4 (`scenario_runs` + `scenario_run_data`) con manifiesto inmutable y series completas; auditoría favorable + corrección C-02. Verificado entonces: 355 passed; E2E 2C 55/55. Informe: `PARAMIJEFE.md` Entrega 3.

## Histórico — entrega anterior: Piso 2B · Previsões e Dados (PR #7, integrado en `43ee6f5`)

- Etapa 02 del Centro de Operação: demanda y clima (manual/CSV/sintético/referencia V1.6), pre-visualización Plotly, calidad, fusos explícitos, blobs en la misma transacción de la versión del escenario. Verificado entonces: 308 passed; E2E 2B 58/58, 2A 51/51, Gestor 52/52, Piso 1 66/66. Informe: `PARAMIJEFE.md` Entrega 2.

## Histórico — entrega anterior: Piso 2A · Centro de Operação (PR #6, integrado en `4709f0c`)

- Centro de Operação como inicio de la microrred comisionada; escenarios operativos versionados (append-only, concurrencia optimista, vínculo con la revisión del inventario, deriva + `rebase`); Inicialización con erro/aviso/pendente; contratos 2B/2C/2D; corrección de auditoría **C-01** (avisos de alcance del backup ZIP y consentimiento específico en la exclusión). Verificado entonces: 276 passed; E2E Piso 2A 50/50, Gestor 52/52, Piso 1 66/66. Informe: `PARAMIJEFE.md` Entrega 1.

## Histórico — entrega anterior: Gestor de microrredes (PR #5, integrado en `50ef4d6`)


**Implementado**
- **Catálogo** (`MicrogridRegistry`): `registry.db` (uid PK validado, estado `ready/deleting`, origen `new/legacy/import/copy`, procedencia de copias) + `microgrids/<uid>/seeds2.db` (el mismo `MicrogridStore` del Piso 1, con `CHECK(id = 1)`). Operaciones con varios archivos recuperables: preparación en `.staging` → confirmación (rename + INSERT bajo `BEGIN IMMEDIATE` del catálogo); exclusión `deleting → .trash → DELETE`; `recover()` concluye interrupciones. Rutas derivadas solo del UID validado.
- **Adopción del `seeds2.db` anterior al Gestor**: una vez, idempotente, segura entre procesos, copia **de solo lectura** vía API de backup SQLite (original byte a byte intacto), migración de la copia, verificación de conteos; fallo → error claro y ninguna microrred creada.
- `MicrogridStore`: `must_exist` (no recrea microrredes eliminadas), `fixed_uid` (sin cambio de identidad), `import_inspected`, `inspect_backup_data`, `sqlite_backup_copy(read_only=…)`, `ensure_wal` (corrige "database is locked" en aperturas concurrentes de bases nuevas).
- **Interfaz**: página inicial GESTOR DE MICRORREDES (estado vacío; tarjetas con estado *Em configuração / Ativa / Atenção* separado de la compatibilidad con el EMS; FV calculada × declarada, eólica de catálogo, almacenamiento con su base); ＋ NOVA MICRORREDE (comisionamiento reutilizado íntegro; se registra al guardar la etapa 01), ABRIR, ZIP y PDF **sin abrir** la microrred, IMPORTAR (nueva / restaurar en la existente / copia independiente con `installation.copied_from`; nunca sobrescribe en silencio), EXCLUIR (resumen, ZIP previo, nombre exacto, credencial). TROCAR MICRORREDE en la barra superior; nombre de la microrred activa siempre visible.
- **Sesión**: microrred activa por sesión de navegador (`mg_active_uid`, `?mg=` para recarga); abrir/cambiar limpia todo el `session_state` (incluido el console V1.6); microrred eliminada por otra sesión → vuelta al Gestor sin recrearla.
- **Procedencia**: `microgrid_uid` en el plan, en `orq_mg_applied` y en el resumen de cada rodada; resultado de otra microrred señalado como tal; rodadas persistidas mostradas al volver.
- **Protección de la exclusión**: `SEEDS2_ADMIN_PASSWORD` / Streamlit Secrets `seeds2_admin_password` (verificación en servidor, tiempo constante); sin credencial, `SEEDS2_DEV_MODE=1` habilita la exclusión solo para uso local; por defecto **desactivada**.

**Hotfix H-01 — exclusión concurrente (auditoría del PR #5)**
- *Causa raíz:* `delete()` tomaba y soltaba el bloqueo de escritura de la microrred antes de marcar `deleting` y mover el directorio; una escritura de otra sesión en ese intervalo se confirmaba y luego se perdía en silencio (reproducido en `ad1d736`). Instancias `MicrogridStore` antiguas no se invalidaban; una microrred eliminada y reimportada con el mismo UID podía recibir la edición pendiente de una sesión antigua.
- *Corrección:* lápide `meta.lifecycle` grabada bajo el bloqueo L2 de la microrred y verificada por TODA transacción/lectura del `MicrogridStore` dentro de su `BEGIN IMMEDIATE`; protocolo lápide (L2) → `deleting` (L1, un único ganador) → remoción física (L1), sin bloqueos anidados; incarnación por entrada (catálogo v2 + `meta.incarnation`, con relleno de las existentes) y sesión ligada a ella; conexiones `mode=rw`; `recover()` idempotente que solo concluye exclusiones con lápide y lleva directorios sin fila a `.quarantine`; la interfaz vuelve al Gestor si la microrred se elimina durante una página. Detalle: `docs/seeds2/ARMAZENAMENTO.md` §H-01.
- *Pruebas:* `tests/test_seeds2_concorrencia.py` (17, deterministas con `Event`/`Barrier`, 10 ejecuciones consecutivas idénticas) + 1 de interfaz. Mapa escenario → prueba: `docs/seeds2/VERIFICACAO_PISO1.md` §H-01.

**Auditoría independiente del PR #5 — H-02 y H-03 (ambos reproducidos en `b8f721c` antes de corregir)**
- *H-02 (alta):* una exclusión obsoleta (validada sobre la incarnación I1) podía grabar la lápide, reivindicar y borrar la microrred **reimportada** con el mismo UID (I2). Corrección: exclusión vinculada a una incarnación en la lápide (L2), en `ready→deleting` (L1), en la remoción física y en `recover()`; `StaleDeletionError` sin tocar la nueva; diálogo del Gestor vinculado a la incarnación mostrada. Sin bloqueos anidados ni global.
- *H-03 (media):* `_read()` comprobaba la lápide y consultaba en instantáneas distintas (leyó la revisión 2 de una base ya con lápide). Corrección: transacción de lectura cuyo instantáneo WAL nace en la propia comprobación (lectura anterior a la lápide → estado anterior válido; posterior → rechazada); `export_backup` en un solo instantáneo.
- Detalle: `docs/seeds2/ARMAZENAMENTO.md` §H-02/§H-03; pruebas y reproducciones: `docs/seeds2/VERIFICACAO_PISO1.md` §H-02/H-03.

**Validado (por Claude Code, 2026-11-05)**
- `python -m pytest tests/ -q` → **237 passed, 0 failed, 0 skipped** tras H-02/H-03 (226 tras H-01; 208 antes). Nuevos: `test_seeds2_gestor.py` (32), `test_seeds2_gestor_app.py` (15), `test_seeds2_concorrencia.py` (27). Mapa requisitos 1–25 → pruebas: `docs/seeds2/VERIFICACAO_PISO1.md` §G.
- Despacho y costo idénticos a `main` (hash de `P_kW`, R$ 417,684638) con la configuración por defecto V1.6 y con una microrred del catálogo.
- Tras el hotfix H-01, E2E repetidos desde cero en Chromium: Gestor **52/52** y Piso 1 **66/66** (simulación EMS real), sin errores de JavaScript.
- Tras H-02/H-03 (`c4aade6`), E2E repetidos desde cero: Gestor **52/52** y Piso 1 **66/66**, sin errores de JavaScript y sin residuos en `.trash`/`.staging`/`.quarantine`; EMS idéntico a `main`.
- Chromium: `tools/e2e/e2e_gestor_microrredes.js` **52/52** (multi → reinicio del servidor → tablet/oscuro → legado) y `tools/e2e/e2e_piso1_microrrede.js` **66/66** (ahora desde el Gestor; rodada EMS real). Capturas revisadas.
- Rodada EMS real desde una microrred seleccionada = despacho y costo de la V1.6.
- **Sin CI.**

### Decisiones (con origen) — Gestor

- **Responsable:** varias microrredes por instalación; catálogo central + base independiente por microrred; eliminación definitiva real (no ocultar), protegida en despliegues compartidos; textos en portugués; no tocar ciencia ni EMS.
- **Claude Code (técnica, a revisar):** estado `deleting` + `.trash` en lugar de borrar en el lugar; staging + rename bajo el bloqueo del catálogo; el catálogo no guarda datos técnicos (tarjetas calculadas de la configuración guardada); `seeds2.db` anterior se conserva como respaldo (no se borra automáticamente); limpieza **total** del `session_state` al cambiar de microrred (más seguro que listas de claves); exclusión desactivada por defecto sin credencial; nombre de exportación incluye 8 dígitos del UID; la restauración dentro de Gestão solo acepta backups de la misma identidad.

### Pendencias / observaciones — Gestor (vigentes salvo indicación)

- Sin autenticación/roles: cualquier sesión puede crear, editar, importar y restaurar; solo la exclusión definitiva tiene protección. La credencial es única (no hay auditoría por usuario).
- El `seeds2.db` anterior queda en `SEEDS2_DATA_DIR` tras la adopción; eliminarlo manualmente después de conferir.
- Las series completas del despacho no se persisten (solo el resumen de cada rodada); al volver a una microrred no se reconstruyen resultados.
- ~~Escritura concurrente con una exclusión podía perderse~~ → **corregido por H-01** (escrituras confirmadas antes de la lápide o rechazadas explícitamente). Límite restante: la exclusión espera como máximo 30 s por una escritura en curso y, si no obtiene el bloqueo, desiste sin alterar nada; la edición pendiente de una sesión cuya microrred fue eliminada no se graba (comportamiento pretendido).
- **Deuda técnica para la fase científica:** persistir las series temporales completas del despacho EMS (hoy solo el resumen de cada rodada en `simulation_runs`).
- Heredadas: decisiones científicas (perfil V–I del ModelLab; equipos heterogéneos; >1 térmica), red sin import/export, MIX inaccesible, `__pycache__/` versionado, README V1.5, sin CI.

### (Propuesta de entonces) Piso 2: Centro de Operação → **iniciado en el Piso 2A** (rama `claude/seeds2-piso2a-centro-operacao`).

## 4. Ritual de actualización y histórico

Actualizar **este archivo en el mismo PR** con: fecha, rama, PR y commit, alcance, tests realmente ejecutados, decisiones, pendencias y próxima misión. Nunca incluir contraseñas, tokens o datos sensibles.

**Histórico:**
- PR [#1](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/1) — tests UI V1.6 + `CLAUDE.md` (merge `5ffe2ee`).
- PR #2 — protocolo de relevo (`f70dd94`).
- PR [#3](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/3) — SEEDS2 v2.0 Piso 1 (merge `67a7a6f`). Regla entonces vigente: **"una instalación = una microrred"** (directriz del prompt maestro del Piso 1; sustituyó la idea anterior de "cadastro/seleção").
- PR [#4](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/4) — refinamiento del Piso 1 + backup `.bak-v<N>` consistente con WAL (merge `05e29ef`; 163 passed, E2E 64/64 reportados entonces).
- PR [#5](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/5) — Gestor de microrredes + H-01/H-02/H-03 (merge squash `50ef4d6`, 2026-11-06; 237 passed, E2E Gestor 52/52 y Piso 1 66/66 reportados entonces). La regla de microrred única queda **sustituida por autorización del responsable**.
- PR [#6](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/6) — Piso 2A, Centro de Operação + C-01 (merge `4709f0c`); inicia el protocolo `PARAMIJEFE.md`.
- PR [#7](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/7) — Piso 2B, Previsões e Dados (merge `43ee6f5`): `PARAMIJEFE.md` Entrega 2.
- PR [#8](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/8) — Piso 2C, Execução EMS e Persistência Científica + C-02 (merge `34a8b52`): `PARAMIJEFE.md` Entrega 3.
- PR [#9](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/9) — Piso 2D-A, Arquivo Científico Portátil + C-03 (merge `3b73971`): `PARAMIJEFE.md` Entrega 4.
- PR [#10](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/10) — Piso 2D-B, Relatórios Científicos, Excel e Figuras (merge `8556b71`): `PARAMIJEFE.md` Entrega 5.
- PR [#11](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/11) — Piso 3A (merge `f6d009d`): Entrega 6. PR [#12](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/12) — Piso 3B-P (merge `3c65d98`): Entrega 7.
- PR [#13](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/13) — Piso 3C-0, Puente científico (merge `81aa09c`): Entrega 8.
- PR [#14](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/14) — Piso 3C-1, Commitment dinámico (merge `55440f4`): Entrega 9.
- Piso 3C-2 — MPC de horizonte recedente (rama `ccr-2529baa8-16lz1j`; PR [#15](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/15), pendiente de auditoría): Entrega 10.

**Lectura obligatoria al entrar:** `CLAUDE.md` → este `HANDOFF.md` → `PARAMIJEFE.md` → estado real de `main` y PRs recientes. En caso de conflicto, reportar; no improvisar decisión científica.


## Missão eólica Codex — catálogo de sete equipamentos e potência de referência × pico

Base verificada `10365c5478b4dd137906b58819cd7f71d8de9cea`, rama exclusiva `codex/eolica-siete-curvas-potencias`. Autorização explícita do usuário para ciência eólica; não é parte do Piso 3C-4 de Claude. Nenhum arquivo EMS alterado nesta implementação. Sem merge.

Catálogo único com 13 entradas: três tabelas de fabricante (Vergnet C275, V47 de um gerador, V52 OptiSpeed 104,2 dB(A)) simuláveis em domínio restrito; quatro tabelas secundárias (Excel 10/15, e400nb, SWIFT) disponíveis para análise fiel, mas integração energética bloqueada até cotejo primário/densidade/variantes e contabilidade no balanço. Não se recortam os picos à referência e não se apagam negativos. Domínio real/equivalente explícito, sem extrapolação nova. Os seis registros e saídas históricas são exatamente iguais nos perfis fixados antes da implementação.

Dossier: [formulação](../eolica/FORMULACAO_POTENCIA_REFERENCIA_MAXIMA.md), [rastreabilidade](../eolica/RASTREABILIDAD_7_EQUIPOS.md), [validação](../eolica/VALIDACION_7_EQUIPOS.md), [resultados](../eolica/RESULTADOS_REGRESION.md). Pacote Work original preservado com sete CSV e fontes; validador `python -m tools.validate_wind_catalog` não transforma integridade numérica em certificação.

110 testes novos passaram. Duas provas históricas foram delimitadas aos seis originais com autorização expressa, preservando asserções. Três guardias antigas que proíbem qualquer edição eólica foram identificadas; o resultado integral e o eventual ajuste autorizado estão em RESULTADOS_REGRESION.md. Pendência de rede para informes primários/API GitHub. Não sobrescrever nem reinterpretar entregas EMS anteriores com esta seção.


### Missão eólica — autorização posterior para três guardias nominais

O usuário autorizou expressamente o ajuste EXCLUSIVO das três guardias históricas de ponte/3C-2/3C-3. Foram inseridos filtros por arquivos e estados exatos, mantendo todas as asserções anteriores. Originais em `10365c5` e implementação eólica já publicada em `5bc4283` fixados por SHA-256; nenhum hash regenerado pelo teste. Arquivos autorizados continuam congelados integralmente, e os seis registros históricos também são conferidos por digest e regressão numérica independente.

Nenhum byte de `ems_v2/` mudou; a nova verificação global rejeita alterações e adições EMS, inclusive em caminho 3C-4. A quarta guarda de ausência de integração continua intacta; suporte novo em `tests/ems_v2/`. Lote de guardias/adversariais: **128 passed**. Históricos separados: **12 passed** e **9 passed**. Detalhes e lista nominal completa: [guardias e hashes](../eolica/GUARDIAS_REGRESION_EOLICA.md); resultado integral atualizado em `docs/eolica/RESULTADOS_REGRESION.md`. Não tocar a rama simultânea de Claude; sem merge.

**Regressão final da continuação eólica autorizada:** `1758 passed, 0 failed, 0 skipped, 7 warnings` em `415.84s (0:06:55)`. Nenhum código EMS modificado; PR ainda bloqueado pela API GitHub. Ver `docs/eolica/RESULTADOS_REGRESION.md`.


### C-EOL-01 — PR #18: corregir el alcance temporal de las guardias eólicas

La política anterior congelaba indirectamente todo EMS contra `10365c5`. Se separó la auditoría explícita base/head del PR de las comprobaciones permanentes. Estas mantienen los hashes eólicos y las seis máquinas históricas, pero leen evidencia auditada retenida para las entregas anteriores; permiten cambios EMS de otro PR y no dependen de commits antiguos disponibles localmente. La prueba Git de los subárboles EMS de `10365c5` y `9621543` conserva su identidad sin red.

Lote focalizado **135 passed**; en un clon real de profundidad 1 las guardias ejecutan **14 passed, 0 skipped**, antes y después de integrar centinelas de una rama 3C-4 independiente. Modificar una curva después sigue fallando. Ningún código de producción, curva, parámetro o regla física cambió. Dossier: `docs/eolica/AUDITORIA_C_EOL_01.md`; suite completa en `docs/eolica/RESULTADOS_REGRESION.md`. El PR #18 fue creado externamente; esta corrección se entrega en su misma rama, sin merge. La descripción anterior de una congelación global permanente queda sustituida por C-EOL-01.

**Cierre verificado C-EOL-01:** suite completa **1765 passed, 0 failed, 0 skipped, 7 warnings**, 411,59 s; lote focalizado **135 passed**. Se entrega un commit correctivo en la misma rama del PR #18; sin merge. Producción EMS y física eólica intactas.


## PR #18 — integración combinada con 3C-4 de main

Por autorización expresa, se incorpora `origin/main` en `19aa3ac328f337e31ec4c36baa837c056299a57a` mediante merge en la rama eólica, preservando todos los commits documentales. Se conserva completa la entrega científica 3C-4 de PR #17 y el registro eólico. No se hace merge del PR #18 en main.

Los conflictos de PARAMIJEFE y las tres guardias se resuelven combinando las garantías de ambas entregas: C-EOL-01, ADICOES_3C4 y B3C4-01. La guardia propia de 3C-4 mantiene todas sus comprobaciones científicas ACTIVAS; solo reconoce excepciones eólicas nominales verificadas. La producción `ems_v2/` es idéntica al nuevo main, no al main anterior. La auditoría explícita del diff combinado debe usar `19aa3ac`, nunca exigir igualdad del EMS final frente a `10365c5`.

Nueva regresión y lista completa de archivos respecto de main: `docs/eolica/INTEGRACAO_3C4_PR18.md`. No se reutiliza el resultado 1765 anterior como evidencia combinada. Los seis aerogeneradores históricos y las siete incorporaciones se mantienen intactos. No se inicia 3D.

**Cierre de la integración combinada:** **2004 passed, 0 failed, 0 skipped, 7 warnings**, 501.77s (0:08:21); 3C-4 **228 passed**, 3C-1/2/3 **545 passed**, sin solver EMS **994 passed/101 skipped** por ausencia de solver y eólica **119 passed**. Conflictos resueltos; producción EMS idéntica al main `19aa3ac`. Detalle y lista completa de archivos relativos al nuevo main en `docs/eolica/INTEGRACAO_3C4_PR18.md`.


## Estabilización integral posterior a PR #17/#18 — 2026-11-10

Base comprobada `5e6267833538716678125ab962fc645cfee53eb0`; rama `codex/estabilizacion-aceptacion-integral`; producción en `02d898d819e752c0ebd89c8564376eb200db33fd`. Transferencia fallida bloqueada con rollback/reintento; manual separado del store; consentimiento de exclusiones vinculado a identidad/revisión; huella cubre preparación V1.6; errores de arranque/térmica controlados. Solo cuatro archivos de aplicación; EMS, modelos, catálogos y datos históricos intactos. Guardias científicas activas; nuevas excepciones nominales verificadas mediante evidencia independiente, sin directorios/tolerancias ni cambios de fixtures anteriores.

Resultado nuevo: **2044 passed / 0 failed / 0 skipped / 9 warnings**; EMS separado **1458 passed**; sin solver real **1598 passed / 101 skips**, con lista individual de 446 casos no ejecutados. Cuatro algoritmos antes/después exactos. Navegador real en seis bancadas y protocolos completos del Gestor, escenarios, reinicios/interrupción, Archivo e informes. P0/consentimiento: 24 verificaciones; catálogo: 103; descargas: 157.

[Dictamen y evidencias](../estabilizacao/VEREDICTO_FINAL.md). Conservados los límites: cuatro eólicas solo curvas, MIX sin enlace normal, V2 experimental sin integración operativa, backup convencional distinto del científico, uso local/de confianza. Rama publicada; API GitHub `Forbidden` impide confirmar la creación del PR. Próximo paso: abrir/revisar el PR y auditoría matemática independiente; **sin merge y sin 3D**. Esta sección no sustituye ninguna entrega científica previa.


## Hotfix CI-01 — reproducibilidad eólica, PR #19 — 2026-11-10

Diagnóstico controlado: con/sin Pyomo/HiGHS los doce hashes y KPI son exactos en la misma CPU; desactivar AVX-512 reproduce seis divergencias weather, máximo 8 ULP / 5.4569682106375694e-12 kW, con los doce KPI exactos. Se conserva el JSON histórico, las curvas y todo código científico. Revisión nominal de la comparación weather: SHA canónico primero; en otra ruta CPU, máximo 16 ULP tanto contra los arrays autenticados por el SHA original como contra Decimal independiente de 80 dígitos; KPI estrictos y boundaries exactos. 31 nuevos adversariales y soporte de guardia con archivos explícitos, sin actualizar hashes anteriores ni tocar las tres guardias históricas/EMS. Validación enfocada: 291 passed; completas y aceptación remota pendientes. [Informe CI-01](docs/estabilizacao/HOTFIX_CI01_REPRODUCIBILIDAD_EOLICA.md) (ruta desde raíz). Misma rama/PR #19, sin merge ni 3D. Esta sección preserva las entregas científicas anteriores.


**CI-01 — resultados comprobados:** código correctivo `5c69543`; suite nueva **2075 passed**, venv sin solver **1629 passed / 101 skips**, mismas identidades de omisión y nueve advertencias. 31 adversariales añadidos; cuatro algoritmos con series/resumen exactos; 98 archivos EMS intactos. Run remoto `42751027096`: true y false **success**. Publicación adicional de recibos numéricos/CPU y conteos en anotaciones para verificar el diagnóstico sin API. Informe HOTFIX_CI01_REPRODUCIBILIDAD_EOLICA y evidencia post-fix, mismo PR #19, sin merge.


**Cierre CI-01:** HEAD científico/CI validado `79cb4540f89020f3b03537578ffeef546c2ead2a`, run `42812301019`, ambos jobs success: true **2075 passed**, false **1629 passed / 101 skips**. EPYC 7763 sin AVX-512, mismo binario NumPy y arrays exactos entre jobs; seis SHA weather identifican la reproducción portátil, KPI y boundaries históricos exactos. Evidencia completa y comparaciones en HOTFIX_CI01_REPRODUCIBILIDAD_EOLICA.md y ci01_evidencia/post-fix/remote. Commit final solo documental, sin nueva suite manual; workflow automático documental no se declara terminado anticipadamente. Sin bloqueos científicos conocidos, sin merge.


## Piso 3D-A — integración operativa del EMS V2 — 2026-11-11

**Estado:** publicado como **PR Draft [#21](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/21), sin merge**; rama `claude/adoring-newton-jzfmfx` desde `main` `a636350`; último SHA de código `5e2a4581c6453e19f24617d0bf1a1c148fb06e85`. Desarrollo detenido por orden del responsable. Relevo completo (archivos, comandos, pendientes, próximos pasos): [`RELEVO_3DA.md`](RELEVO_3DA.md). Informe técnico: `PARAMIJEFE.md` Entrega 13. Contratos, mapa de datos y contradicciones C-3DA-01…07: [`INTEGRACAO_3DA.md`](../ems_v2/INTEGRACAO_3DA.md).

- **Implementado:** paquete `integracao_v2/` (estrategia versionada, montaje por UID, preflight V2, runner V2, registro/verificación, UI mínima); despacho por motor en 4 archivos de `seeds2`; `ems_v2/` idéntico a `main` (árbol `58cc13b6de0abff0f0cff824d469f2fb3f4ed3d7`); V1.6 intacto y motor por omisión. Flujo real: Gestor → Centro de Operação → escenario versionado → preflight V2 → Pyomo/HiGHS → rodada inmutable → reapertura verificada sin optimizador → Archivo Científico.
- **Verificado sobre `5e2a458`:** focalizadas con solver **40 passed, 1 skipped**; sin solver **24 passed, 17 skipped**; E2E de navegador `tools/e2e/run_piso3da.sh` **106 verificaciones, exit 0** (operar 65, reinicio tras `kill -9` 14, tablet 8, importar en instalación limpia sin solver 19; registro de llamadas al motor vacío). Costo realizado R$ 50,20 = oráculo analítico; segunda microrred aislada R$ 55,10. Registros en `docs/ems_v2/evidencia_3da/`.
- **Verificado antes de los últimos cambios menores (no repetido):** regresión completa con solver **2116 passed, 1 skipped**; sin solver **1652 passed, 120 skipped**.
- **Auditoría explícita del diff** (`python tests/ems_v2/piso3da_guard_policy.py`): aprobada sobre `12221d0` en un clon limpio; en un workspace donde ya se ejecutó la aplicación falla por los `__pycache__/*.pyc` versionados regenerados (no forman parte del diff publicado; `RELEVO_3DA.md` §8).
- **Sin confirmar:** CI remoto del PR #21 (run `42963356574`, en curso al cierre); regresión global sobre el HEAD final.
- **Decisión pendiente del responsable:** excepción nominal de guardias **C-3DA-01**.
- **Límites:** sólo demanda + ≤2 bancos + PCC declarado, contexto de ensayo (simulación offline algebraica, no validación física); FV/eólica/PEMFC/térmica ⇒ bloqueo; informes 2D-B rechazan rodadas V2; capturas PNG del E2E no versionadas.
- **Próximo paso:** auditoría externa del PR #21 y pasos de `RELEVO_3DA.md` §10. **No iniciar 3D-B/3D-C; no hacer merge.**


## Piso 3D-A2-R — FV e eólica no EMS V2 — 2026-11-11

**Estado:** implementado e validado localmente; PR [#22](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/22) contra `main` sem merge. Base `main` `7eb29e5`.
`ems_v2/`, modelos físicos, `seeds2/` e V1.6 intactos.

- **Implementado:**
  - `integracao_v2/renovaveis.py`;
  - estratégia formato 2 (formato 1 legível);
  - preflight com FV/eólica por UID e bloqueios legíveis;
  - persistência `seeds2-milp-mpc-run-data` v2 (v1 legível) com `v2/renovaveis.json` comprometido no manifesto;
  - UI mínima;
  - exceção nominal de guardas C-3DA2R-01;
  - E2E em navegador.
- **Verificado:**
  - testes 3D-A2-R: 20 + 13 + 3 UI passed (sem solver: 20 passed, 13 skipped);
  - 3D-A focalizados: 40 passed, 1 skipped;
  - guardas: 203 passed, 2 skipped;
  - auditoria explícita do diff: aprovada;
  - E2E: 43 verificações, exit 0, registro de chamadas a motor/modelos vazio;
  - regressão completa com solver **2157 passed, 2 skipped**, 9 warnings (719 s); sem solver **1678 passed, 136 skipped**, 9 warnings (509 s).
- **Decisões pendentes do responsável:** C-3DA2R-01 (exceção nominal) e C-3DA2R-02…08 (`INTEGRACAO_3DA2R.md` §8).
- **Limites:**
  - realização renovável = previsão;
  - uma série climática por cenário;
  - GHI no plano; vento no cubo; sem esteira; η de inversor declarado;
  - PEMFC e térmica bloqueadas (matriz PEMFC e lacuna M19 documentadas, não implementadas).
- **Próximo passo:** auditoria externa do PR; CI remoto; só então 3D-A2-H/3D-A2-T/3D-B com nova autorização.


## Piso 3D-A2-H — PEMFC/H₂ no EMS V2 — 2026-11-11

**Estado:** implementado e demonstrado; **produção BLOQUEADA até a aprovação da política B04** (`b04-proposta-2`,
congelada). PR contra `main` sem merge. Base `main` `0c9df80`.

- **Implementado:**
  - `integracao_v2/curva_h2.py`: curva do modelo estacionário, identidade SHA-256, cache, validação independente, massa
    no tempo em 6 perfis, generalização e certificado;
  - `integracao_v2/pemfc_dinamica.py`: massas de partida/parada e verificação a posteriori pelo modelo dinâmico;
  - estratégia formato 3;
  - preflight PEMFC;
  - contrato de dados v3 (`v2/pemfc.json`, `v2/pemfc_dinamica.json`, colunas por unidade);
  - UI;
  - bancada `h2_app.py`;
  - núcleo C-3DA2H-01 (4 arquivos, autorizado);
  - E2E.
- **Verificado:** ver `RELEVO_3DA2H.md` §4. Caso híbrido FV + eólica + bateria + PEMFC + PCC concluído e auditado (aprovação
  simulada): custo R$ 116,00 (H₂ 65,70), PEMFC 100,54 kWh / 6,570 kg, dinâmica coerente.
- **Decisões pendentes do responsável:**
  - aprovação B04;
  - C-3DA2H-02 (`massas_h2_eventos`, extensão a confirmar);
  - C-3DA2H-03 (rampa única);
  - C-3DA2H-04 (D05);
  - C-3DA2H-05 (IDLE × P_mín).
- **Limites:**
  - condições físicas constantes por missão;
  - tanque de H₂ não modelado;
  - M20 não implementado;
  - verificação dinâmica não realimenta o despacho;
  - modelo aproximado, sem validação física;
  - relatórios 2D-B recusam rodadas V2.
- **Auditoria externa do PR #23 (revisão de `68fd055`) — aplicada em `0a2a6e5`, `0055e68` e `d0bee62`:**
  - A: massas por evento ADICIONAIS pela integração temporal do modelo dinâmico (m_SU = 0, m_SD = 0,0064 kg; antes
    dupla contagem na partida);
  - B: aceitação SEPARADA algébrica × dinâmica × física, testes negativos, rótulo verificado na reabertura;
  - C: autoridade B04 = registro do núcleo por identidade do conteúdo (autodeclaração rejeitada);
  - D: P_mín < IDLE, rampa acima do modelo e transitórios incompatíveis BLOQUEIAM;
  - E2E do fluxo completo com aprovação SIMULADA (8 + 14 + 9 verificações). Detalhes: `RELEVO_3DA2H.md` §2b.
  - regressão completa sobre `d0bee62` (depois só documentação): com solver **2229 passed, 2 skipped**; sem solver
    **1736 passed, 150 skipped**; 0 falhas.
- **Decisão do responsável (PR #23):** B04 APROVADA (`8be5de4`, commit independente; limiares/identidade/versão
  inalterados) e C-3DA2H-02…05/08…11 aprovadas com alcance delimitado. Verificações finais:
  - A (`efa05c8`): `tests/verificacao_massas_3da2h.py`, malha densa em 6 configurações — eventos e rampas de subida nunca
    subestimam; rampas de DESCIDA subestimam (máximos OBSERVADOS 0,0044 kg e 0,72 % nos casos ensaiados, não cotas
    universais), sem garantia global; reportado por intervalo/unidade/acumulado e verificado na reabertura;
  - **C-3DA2H-12 APROVADA** (resíduo quantificado; termo de rampa NÃO autorizado; condições em
    `INTEGRACAO_3DA2H.md` §5b: visibilidade, não universalidade, classificação independente, custos MILP ≠ operação
    transitória, magnitude econômica no TCC, incoerência ⇒ revisão, Δ = 60 min não extrapolado);
  - B (`0058902`): E2E sem aprovação simulada — bancada 6 + fluxo 20 + reabertura 16 + conferência 18; chamadas VAZIO;
    rodadas legadas v1/v2 legíveis.
  - regressão completa sobre `0058902` (depois só documentação): com solver **2234 passed, 2 skipped**; sem solver
    **1741 passed, 150 skipped**; 0 falhas.
- **Próximo passo:** fechamento formal do PR #23 pelo supervisor quando o responsável confirmar expressamente a
  autorização (sem merge automático); 3D-A2-T/3D-B não iniciados — só com nova autorização.
