# Energy MultiModel V1.3 — Bateria + H₂ / PEMFC

## Alterações principais

- Tela inicial ampliada de 3 para 5 recursos: Solar, Eólica, Térmica, Bateria e H₂ / PEMFC.
- Novo `battery_app.py` com navegação própria, simulação, comparação e exportação.
- Port do Modelo 01 Tremblay–Dessaint / Shepherd para Python, com as quatro químicas do protótipo MATLAB.
- Port do Modelo 03 de circuito equivalente Li-Ion de 2 RC, incluindo OCV(SOC), R0/R1/C1/R2/C2 dependentes de SOC.
- Integração interna com passo de até 1 s para preservar a estabilidade numérica dos modelos de bateria mesmo quando o CSV possui intervalos maiores.
- Escalonamento de banco por `Ns × Np` sem alterar as equações de célula.
- Novo `h2_app.py` com Visão geral, Simulação EMS, Caracterização e Exportação.
- Núcleo `FC-PEM-66-KW` incorporado em `h2_pemfc/` com imports namespaced, evitando conflito com os modelos Solar/Térmico/Eólico existentes.
- Preservados stack, balance of plant, solver potência→corrente, máquina de estados, rampas, consumo de H₂, eficiência e flags de limitação.
- Arquivos MATLAB originais de bateria preservados em `reference_models/battery_matlab/`.
- Documentação científica do modelo Horizon preservada em `h2_pemfc/docs/`.
- Novos exemplos CSV em `Dados_exemplo/`.
- Novos testes físicos para bateria e PEMFC/H₂.
- Novo inicializador `INICIAR_ENERGY_MULTIMODEL_V1.3.bat`.

## Compatibilidade

Os módulos Solar, Eólica e Térmica existentes não foram reestruturados; a V1.3 acrescenta os novos módulos por roteamento no `app.py` e mantém as APIs anteriores.
