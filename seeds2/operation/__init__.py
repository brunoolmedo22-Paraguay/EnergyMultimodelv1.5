"""SEEDS2 Piso 2 — Centro de Operação (domínio, sem interface e sem ciência).

* ``scenarios``      — documento do cenário operativo, vínculo com a revisão do inventário, deriva e duplicação;
* ``initialization`` — estados iniciais dos equipamentos e regras de validação (erro / aviso / pendente);
* ``forecasts``      — Piso 2B: séries de previsão (variáveis, unidades, normalização, qualidade, forma canônica);
* ``forecast_sources`` — Piso 2B: fontes manual / CSV / sintética / referência V1.6 e reprodutibilidade;
* ``contracts``      — interfaces entre os Pisos 2B (Previsões, implementado), 2C (Execução) e 2D (Arquivo);
* ``service``        — operações completas sobre o ``MicrogridStore`` da microrrede ativa.

Nada aqui altera modelos científicos, o EMS ou a configuração física permanente da microrrede.
"""
