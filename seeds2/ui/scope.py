"""Alcance: o que o SEEDS2 (Piso 1) faz e, explicitamente, o que ainda não faz."""
from __future__ import annotations

import streamlit as st

from . import session, shell


def render() -> None:
    shell.hero("Alcance desta versão", "O que o SEEDS2 faz — e o que ainda não faz",
               "Transparência sobre capacidades implementadas, hipóteses e limitações, para que nenhum resultado seja "
               "interpretado além do que os modelos calculam.")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("""
#### Implementado no Piso 1
- **Gestor de microrredes**: várias microrredes independentes por instalação do SEEDS2 (catálogo), cada uma com
  armazenamento, revisões, dados importados e rodadas próprios; criar, abrir, exportar ZIP, gerar PDF, importar
  (nova, restauração ou cópia independente) e excluir definitivamente (com confirmação e proteção administrativa).
- **Comissionamento** por microrrede, retomável, identidade estável e manutenção da configuração.
- **Identificação e localização** opcionais da instalação; a localização automática usa apenas o navegador,
  por clique do usuário, sem geocodificação externa (cidade/estado/endereço nunca são inferidos).
- **Inventário** de equipamentos solares, eólicos, baterias, PEMFC e térmicos (várias unidades por tecnologia),
  com referências técnicas dos catálogos existentes e procedência declarada. A FV é registrada como
  **usina → arranjos**, com valores nominais STC por arranjo homogêneo (estimativas com hipóteses explícitas).
- **Esquema lógico do balanço energético**: mostra quais equipamentos entram no balanço do EMS; não é um
  diagrama elétrico (sem barramentos, tensões ou acoplamentos).
- **Importação de dispositivos do PEMFC ModelLab** (pacote validado e preservado no backup), registrada como
  *pendente de integração científica*: não altera a simulação.
- **Exportação** da configuração (ZIP verificável) e **relatório técnico em PDF**, gerados localmente.
- **Persistência local** em SQLite: revisões imutáveis, controle de concorrência, backups verificáveis.
- **Adaptador** inventário → contrato agregado do orquestrador V1.6, com identificação explícita de
  equipamentos não representáveis e procedência (revisão + impressão digital) de cada rodada.
- **Simulação/otimização** pelo EMS existente (GA/GWO/NGO + refino SLSQP), sem alterações científicas.
""")
    with c2:
        st.markdown("""
#### Não implementado (fora do alcance atual)
- **Operação em tempo real**, aquisição de medições ou comando de equipamentos (Centro de Operação: próximo piso).
- **Fluxo de potência**, tensões, proteções, acoplamentos ou transitórios elétricos — o esquema de balanço é lógico.
- **Importação/exportação com a rede e tarifas**: declarar conexão à rede não as habilita no EMS; um déficit do
  EMS não equivale a uma compra de energia da rede.
- **Agregação de equipamentos heterogêneos** da mesma tecnologia no EMS (são identificados e excluídos, nunca omitidos).
- **Usina termelétrica de grande porte** no runtime integrado (somente na bancada Térmica).
- **Simulação com perfis calibrados do PEMFC ModelLab**: o dispositivo importado é guardado, mas a simulação
  continua usando o perfil equivalente do catálogo (não se inventam parâmetros dinâmicos/BoP).
- **Autenticação e perfis de acesso**: qualquer usuário da aplicação pode alterar as microrredes (que são
  registros da instalação, compartilhados entre sessões); só a exclusão definitiva tem proteção administrativa.
- **Otimização conjunta ou intercâmbio de energia entre microrredes**: cada rodada do EMS usa uma única microrrede.
- **Validação física experimental** dos modelos nesta instalação; o relatório PDF não é certificação nem laudo.
- **Simulação de arranjos FV heterogêneos agregados**: apenas arranjos homogêneos são agregados no EMS; a potência
  instalada pode diferir da potência simulada (a diferença é mostrada).
""")
    st.markdown("#### Dados e procedência")
    st.markdown("""
- Perfis *walk-forward* e COPEL B1 são **conjuntos de referência** incluídos no software, não medições da instalação.
- O clima **sintético** é explícito e serve para demonstração; para estudo, use CSV climático real.
- Presets de CVU térmico são **acadêmicos**; baterias são **células de referência** (não produtos comerciais validados);
  a PEMFC é um **perfil equivalente aproximado** sem validação no equipamento instalado.
""")
    st.caption(f"Armazenamento desta instalação do SEEDS2: `{session.registry().root}` (catálogo `registry.db` e um "
               "banco por microrrede em `microgrids/`).")
