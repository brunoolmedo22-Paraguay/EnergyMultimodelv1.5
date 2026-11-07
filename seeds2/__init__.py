"""SEEDS2 — Piso 1 (Gestor de microrredes: configuração, instalação, persistência) + Pisos 2A/2B/2C (Centro de Operação:
cenários, estados iniciais, previsões, estratégia EMS e execução com rodadas persistentes; pacote ``seeds2.operation``).

Este pacote NÃO contém modelos científicos. Ele organiza a configuração física da
instalação, persiste-a localmente e a adapta ao contrato do orquestrador V1.6
(``orchestrator_runtime``), sem alterar equações, parâmetros ou algoritmos.
"""

APP_NAME = "SEEDS2"
APP_VERSION = "2.0.0-piso2c"
