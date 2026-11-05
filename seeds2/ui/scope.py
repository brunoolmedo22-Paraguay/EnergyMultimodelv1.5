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
- **Uma microrrede por instalação** do SEEDS2: comissionamento, identidade estável e manutenção da configuração.
- **Inventário** de equipamentos solares, eólicos, baterias, PEMFC e térmicos (várias unidades por tecnologia),
  com referências técnicas dos catálogos existentes e procedência declarada.
- **Topologia simplificada** de barramento comum (declarativa), coerente com o balanço de potência do EMS.
- **Persistência local** em SQLite: revisões imutáveis, controle de concorrência, backups verificáveis.
- **Adaptador** inventário → contrato agregado do orquestrador V1.6, com identificação explícita de
  equipamentos não representáveis e procedência (revisão + impressão digital) de cada rodada.
- **Simulação/otimização** pelo EMS existente (GA/GWO/NGO + refino SLSQP), sem alterações científicas.
""")
    with c2:
        st.markdown("""
#### Não implementado (fora do alcance atual)
- **Operação em tempo real**, aquisição de medições ou comando de equipamentos (Centro de Operação: próximo piso).
- **Fluxo de potência**, tensões, proteções ou transitórios elétricos — a topologia é apenas declarativa.
- **Importação/exportação com a rede e tarifas**: declarar conexão à rede não as habilita no EMS.
- **Agregação de equipamentos heterogêneos** da mesma tecnologia no EMS (são identificados e excluídos, nunca omitidos).
- **Usina termelétrica de grande porte** no runtime integrado (somente na bancada Térmica).
- **Perfis calibrados do PEMFC ModelLab** (integração futura; não se inventam parâmetros dinâmicos/BoP).
- **Autenticação e perfis de acesso**: qualquer usuário da aplicação pode alterar a configuração.
- **Validação física experimental** dos modelos nesta instalação.
""")
    st.markdown("#### Dados e procedência")
    st.markdown("""
- Perfis *walk-forward* e COPEL B1 são **conjuntos de referência** incluídos no software, não medições da instalação.
- O clima **sintético** é explícito e serve para demonstração; para estudo, use CSV climático real.
- Presets de CVU térmico são **acadêmicos**; baterias são **células de referência** (não produtos comerciais validados);
  a PEMFC é um **perfil equivalente aproximado** sem validação no equipamento instalado.
""")
    st.caption(f"Armazenamento desta instalação: `{session.store().path}`")
