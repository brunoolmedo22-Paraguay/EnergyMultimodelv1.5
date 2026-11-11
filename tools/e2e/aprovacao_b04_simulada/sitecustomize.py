"""APROVAÇÃO B04 SIMULADA para o E2E do fluxo completo do Piso 3D-A2-H — NUNCA usar em produção.

Ativado só quando este diretório está no ``PYTHONPATH`` do servidor de TESTE e ``SEEDS2_E2E_APROVACAO_B04_SIMULADA=1``.
A política B04 do repositório continua PENDENTE: aqui, só no processo do servidor E2E, entra-se (sem sair) no MESMO
gerenciador dos testes, ``tests/piso3da2h_util.politica_aprovada_no_teste``, que troca a situação da política CONGELADA
no registro do núcleo (pela identidade do conteúdo). Cada ativação é registrada em ``$SEEDS2_E2E_APROVACAO_LOG``.

Com ``SEEDS2_E2E_ENGINE_LOG`` definido, aplica também a sabotagem de ``tools/e2e/sabotage_v2`` (motor, solver e modelos
renováveis) e sabota os modelos da PEMFC (curva, análise transitória, verificação dinâmica e a resposta estática do
``h2_pemfc``): reabrir uma rodada com PEMFC tem de só LER e VERIFICAR o que foi gravado.
"""
import os
import runpy
import sys

if os.environ.get("SEEDS2_E2E_APROVACAO_B04_SIMULADA") == "1":
    root = os.environ.get("SEEDS2_E2E_ROOT") or os.getcwd()
    if root not in sys.path:
        sys.path.insert(0, root)
    if os.path.join(root, "tests") not in sys.path:
        sys.path.insert(0, os.path.join(root, "tests"))
    import piso3da2h_util as _H  # noqa: E402
    from integracao_v2 import curva_h2 as _CH  # noqa: E402

    _APROVACAO = _H.politica_aprovada_no_teste()
    _APROVACAO.__enter__()                                     # aprovação SIMULADA durante todo o processo de teste
    _h = _CH.hash_politica_nucleo()
    if os.environ.get("SEEDS2_E2E_APROVACAO_LOG"):
        with open(os.environ["SEEDS2_E2E_APROVACAO_LOG"], "a", encoding="utf-8") as fh:
            fh.write(f"APROVAÇÃO B04 SIMULADA (E2E) — política {_CH.POLITICA_B04['versao']} {_h[:12]}… pid {os.getpid()}\n")

    if os.environ.get("SEEDS2_E2E_ENGINE_LOG"):
        runpy.run_path(os.path.join(root, "tools", "e2e", "sabotage_v2", "sitecustomize.py"), run_name="sabotage_v2")
        _LOG = os.environ["SEEDS2_E2E_ENGINE_LOG"]

        def _boom(nome):
            def f(*a, **k):
                with open(_LOG, "a", encoding="utf-8") as fh:
                    fh.write(nome + "\n")
                raise RuntimeError(f"E2E: {nome} chamado com os modelos PEMFC sabotados")
            return f
        import h2_pemfc.models.equivalent_65kw_power_request as _PRM  # noqa: E402
        from integracao_v2 import pemfc_dinamica as _DY  # noqa: E402

        _CH.obter_curva = _boom("v2.curva_h2.obter_curva")
        _CH._gerar = _boom("v2.curva_h2._gerar")
        _DY.verificar_despacho = _boom("v2.pemfc_dinamica.verificar_despacho")
        _DY.analise_transitoria = _boom("v2.pemfc_dinamica.analise_transitoria")
        _DY.massas_eventos = _boom("v2.pemfc_dinamica.massas_eventos")
        _PRM.Equivalent65kWHorizonPowerRequestModel.solve_requested_power = _boom("h2_pemfc.solve_requested_power")
