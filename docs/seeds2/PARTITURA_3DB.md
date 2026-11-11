# Partitura e motor gráfico Trama — Piso 3D-B (entregas B0 e B1)

Direção de design aprovada pelo responsável: **Partitura V2** (uma linha do tempo, lentes, inspetor sincronizado e
explorador de recursos). Este documento descreve o que está **integrado na aplicação Streamlit real** nesta entrega, o
que ainda existe só no protótipo e como verificar.

## 1. O que está integrado

| Peça | Onde | Estado |
|---|---|---|
| Marco de dados `seeds2-trama-frame` v1 | `integracao_v2/trama_frame.py` | integrado |
| Motor gráfico Trama (SVG, sem dependências) | `seeds2/ui/static/trama/trama.js` | integrado |
| Instrumento Partitura: lente **Operação**, inspetor, barra de estado, temas | `seeds2/ui/static/trama/partitura.js` + `trama.css` | integrado |
| Explorador de recursos: **Solar, Eólica, Bateria, PEMFC (Operação · Curva q(P) e B04 · Verificação dinâmica), Rede/PCC, Carga, Custos**, com seleção por UID | idem | integrado |
| Componente v2 | `seeds2/ui/trama.py` (`st.components.v2.component("seeds_partitura", …)`) | integrado |
| Página da rodada V2 (local **e** estudo arquivado) | `integracao_v2/ui.py::_partitura`, chamada no início de `run_results` | integrado |
| Vista clássica (tabelas, Plotly, descargas, procedência) | mesma página, logo abaixo | **mantida** |

Ainda **só no protótipo** (não integrado): lentes Decisão, Economia e Evidência; barra lateral compacta; Catálogo; Planta;
Caderno de ensaios; Folha de ensaio; exportação de figuras; séries climáticas nos painéis solar e eólico (hoje N/D).

## 2. Fluxo de dados

```
MicrogridStore | StudyView ──run_data──▶ integracao_v2.registro (ler_csv / ler_json / verificar)
                                              │  só leitura, sem solver, sem modelos
                                              ▼
                               integracao_v2.trama_frame.montar(source, run)
                                              │  dict JSON estrito (sem NaN), com hash
                                              ▼
                 seeds2.ui.trama.partitura(frame)  ──data──▶  componente v2 (navegador)
```

* O marco contém **os valores gravados, sem arredondamento**: colunas de `v2/intervalos.csv` (N valores de intervalo),
  `v2/fronteiras.csv` (N + 1 estados de fronteira), linhas de `v2/janelas.csv`, parâmetros e diagnósticos de
  `v2/renovaveis.json`, curva/certificado de `v2/pemfc.json`, verificação de `v2/pemfc_dinamica.json`, resumo selado,
  aceitação, avisos, declarações da estratégia (limites, preços) do manifesto e o resultado de `registro.verificar`.
* Coluna inexistente ou célula vazia vira `None` → a interface mostra **N/D**. Nenhuma série é sintetizada.
* O marco **não agrega nem acumula**. Somas por tecnologia, acumulados, participação na demanda, classificação de
  comportamento da bateria e a diferença PWL − modelo são calculadas no navegador e **rotuladas como «derivado»**.
* Nomes e TAG dos equipamentos vêm do `inventory_ref` da versão do cenário executada, quando a origem o expõe
  (`get_scenario`); senão o painel mostra o tipo e o UID.
* Só rodadas V2 **concluídas** e com **evidência verificada** recebem a Partitura. Rodada falha/interrompida, evidência com
  problemas ou erro de leitura ⇒ a página mostra apenas a vista clássica (com a mensagem do motivo).

## 3. Motor Trama

* Um script (`trama.js`) com funções puras de escala e desenho: `trama(host, opções)` desenha raias sobre uma malha de N
  intervalos e N + 1 fronteiras; `xy(host, opções)` desenha gráficos não temporais (curva q(P), erro da PWL).
* Semântica por construção: `stack`/`step`/`strip`/`dots` desenham grandezas de **intervalo** (ocupam `[τ_g, τ_g+1)`);
  `front` desenha **estados de fronteira** em `τ_k`. Nada é interpolado para exibir números.
* Um barramento de eventos por instrumento sincroniza o cursor entre o gráfico principal e o painel aberto.
* Interações sem servidor: passar o mouse (cursor), clique/Enter (fixa o instante), setas (movem), foco por recurso
  (as outras séries recuam), zoom por período (tudo, metade, um quarto da missão), dicas com unidade.
* Persistência do contexto: `sessionStorage` por rodada (instante, fixação, zoom, painel aberto, vista, UID escolhido) e
  `localStorage` para o tema. Um **rerun** do Streamlit com o mesmo marco (mesmo `hash`) não redesenha nada.

## 4. Isolamento de estilos e temas

* O componente usa o **isolamento padrão** do `st.components.v2` (raiz de sombra): as regras de `trama.css` não alcançam a
  aplicação e o CSS da aplicação não entra no componente. Além disso, todo seletor começa por `.pt` (teste
  `test_estaticos_sem_recursos_externos_e_estilos_sob_o_prefixo`), de modo que desligar o isolamento no futuro não
  contaminaria outras telas.
* `isolate_styles=False` (usado pelo ProgE-Web) não foi necessário: o painel amplo é um elemento `position: fixed` dentro
  do próprio componente e cobre a janela (verificado no navegador: 1748 × 833 px numa janela de 1768 × 853).
* Sem fontes nem scripts externos: a pilha tipográfica cai em Source Sans (a fonte do próprio Streamlit).
* Tema: detectado a partir do tema efetivo do Streamlit (luminância do fundo da página) e alternável no botão do
  instrumento; os dois temas têm paleta própria, validada para daltonismo.
* A única regra emitida para fora do componente é a largura da página da rodada (`trama.WIDE_CSS`, `.block-container`),
  aplicada só quando a Partitura é desenhada.

## 5. Decisões e contradições

* **C-3DB-01 — guardas nominais.** `tests/ems_v2/piso3db_guard_policy.py` autoriza, por nome e status, os arquivos novos
  do componente e dos testes; `piso3da2h_guard_policy.py` só encadeia o novo filtro. `ems_v2/`, modelos físicos, motor
  V1.6, armazenamento e contratos estão em `INTOCADOS` (auditoria: `python tests/ems_v2/piso3db_guard_policy.py`).
* **C-3DB-02 — convivência.** A Partitura é desenhada **antes** da vista clássica e vem ao topo da janela ao abrir; a vista
  clássica permanece inteira e expandida abaixo, porque os testes de interface e os roteiros E2E dos pisos anteriores a
  inspecionam. Recolhê-la ou retirá-la é decisão futura do responsável.
* **C-3DB-03 — sem contrato novo.** Nenhum arquivo persistido mudou. O marco é derivado sob demanda e não é gravado.
* **Dependência registrada:** séries climáticas por intervalo (GHI, temperatura, vento) estão na previsão do cenário
  (blob por SHA-256), não nos dados da rodada. Lê-las exige ligar o marco à leitura de blobs do cenário, inclusive em
  estudos arquivados; até lá os painéis solar e eólico declaram N/D.

## 6. Pendências técnicas independentes (não corrigidas)

Achados da investigação anterior, mantidos fora do escopo visual:

1. **R-1** — resíduo numérico do solver na potência aplicada da PEMFC desligada (≈ ±10⁻¹⁵ kW) faz a entrada da janela
   seguinte ser recusada (`quantidade_negativa` / `off_com_potencia`) e interrompe a missão; observado com m = 1.
2. **R-2** — `custo_partida/parada` declarados pelo utilitário de testes produzem `unidade_incompativel` (`R$` × `R$/evento`)
   no preflight; não verificado pelo caminho da interface.
3. **R-3** — com a tolerância de interpolação de 10⁻⁶ R$ e 9 pontos, o sinal de valor futuro fica indisponível na maioria
   das janelas; a degradação declarada funciona, mas a interface anterior não o tornava visível.

## 7. Como verificar

```bash
python -m pytest tests/test_piso3db_trama.py tests/test_piso3db_app.py tests/ems_v2/test_piso3db_guardas.py -q
tools/e2e/run_piso3db.sh <python com Pyomo/HiGHS> <pasta vazia>     # navegador real; servidor sem solver, sabotado
python tests/ems_v2/piso3db_guard_policy.py                          # auditoria explícita do diff da missão
```

Evidência desta entrega: `docs/seeds2/evidencia_3db/` (registro do E2E com 40 verificações e capturas da aplicação real).
