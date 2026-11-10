"""Combined wind/3C-4 policy, retaining live scientific checks from reviewed main."""
import ast
import json
from pathlib import Path

import pytest

from wind_guard_policy import (INTEGRATION_BASE, assert_3c4_guards, assert_ems_unchanged,
                               assert_frozen_mission_ems, read_integration_evidence, _proved_ems_tree)
from test_wind_guard_policy import shallow_integration

ROOT=Path(__file__).resolve().parents[2]


def test_old_wind_evidence_and_new_integration_base_are_distinct():
    record=read_integration_evidence(ROOT)
    assert INTEGRATION_BASE=='19aa3ac328f337e31ec4c36baa837c056299a57a'
    assert _proved_ems_tree(record,INTEGRATION_BASE) != assert_frozen_mission_ems(ROOT)
    assert_3c4_guards(ROOT)


def test_c4_additions_and_energy_projection_exception_are_preserved():
    from test_ems_v2_ponte_isolamento import ADICOES_3C4
    from test_ems_v2_3c3_isolamento import MODIFICADOS_3C3
    assert ADICOES_3C4=={'ems_v2/milp/modelo_3c4.py','ems_v2/milp/solver_3c4.py',
                          'ems_v2/milp/resultado_3c4.py','ems_v2/milp/evidencia_3c4.py'}
    assert 'ems_v2/ponte/execucao.py' in MODIFICADOS_3C3


@pytest.mark.parametrize('name',[
    'test_hotfix_b3c4_01_restrito_a_projecao_numerica',
    'test_hotfix_b3c4_10_restrito_e_regra_c01_identica_a_base',
    'test_a03_auditoria_3c3_so_acrescenta_a_secao_de_normalizacoes',
    'test_a03_politica_b3c4_10_e_c01_inalteradas_desde_o_head_auditado',
    'test_a03_verificador_unico_reutilizado_pela_auditoria_3c4',
    'test_pisos_anteriores_v16_e_aplicacao_sem_alteracao_desde_o_merge_do_pr16',
])
def test_removing_or_weakening_a_live_c4_scientific_check_is_detected(tmp_path,name):
    record=read_integration_evidence(ROOT)
    evidence=tmp_path/'tests/fixtures/wind_3c4_integration_v1.json'
    evidence.parent.mkdir(parents=True)
    evidence.write_bytes((ROOT/'tests/fixtures/wind_3c4_integration_v1.json').read_bytes())
    module=ast.parse((ROOT/record['guard_path']).read_bytes())
    fn=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name==name)
    assertions=[n for n in ast.walk(fn) if isinstance(n,ast.Assert)]
    assert assertions
    assertions[0].test=ast.Constant(value=True)
    file=tmp_path/record['guard_path'];file.parent.mkdir(parents=True,exist_ok=True)
    file.write_text(ast.unparse(module))
    with pytest.raises(AssertionError,match='guarda científica'):
        assert_3c4_guards(tmp_path)


def test_changing_a_c4_exception_set_is_detected(tmp_path):
    record=read_integration_evidence(ROOT)
    evidence=tmp_path/'tests/fixtures/wind_3c4_integration_v1.json'
    evidence.parent.mkdir(parents=True)
    evidence.write_bytes((ROOT/'tests/fixtures/wind_3c4_integration_v1.json').read_bytes())
    file=tmp_path/record['guard_path'];file.parent.mkdir(parents=True)
    file.write_bytes((ROOT/record['guard_path']).read_bytes()+b'\nHOTFIX_B3C4_01 = set()\n')
    with pytest.raises(AssertionError,match='exceções científicas'):
        assert_3c4_guards(tmp_path)


def test_rewriting_the_new_main_evidence_is_detected(tmp_path):
    record=read_integration_evidence(ROOT);record['guard_source']+='\n# changed\n'
    evidence=tmp_path/'tests/fixtures/wind_3c4_integration_v1.json'
    evidence.parent.mkdir(parents=True)
    evidence.write_text(json.dumps(record))
    with pytest.raises(AssertionError,match='evidência da integração'):
        read_integration_evidence(tmp_path)


def test_combined_shallow_snapshot_uses_new_main_not_old_wind_base(shallow_integration):
    clone,_=shallow_integration
    # The actual integrated C4 tree resolves against the new reviewed main even
    # without that historical commit object; the old wind audit remains sealed.
    import subprocess
    reviewed_tree=_proved_ems_tree(read_integration_evidence(clone),INTEGRATION_BASE)
    snapshot_tree=subprocess.check_output(['git','rev-parse','HEAD:ems_v2'],cwd=clone,text=True).strip()
    # Verify reference resolution, not a perpetual freeze of future snapshots.
    # The current integration has the reviewed C4 tree; an independently evolved
    # future tree must instead be reported as a different explicit audit range.
    if snapshot_tree==reviewed_tree:
        assert_ems_unchanged(clone,INTEGRATION_BASE)
    else:
        with pytest.raises(AssertionError,match='EMS V2 alterado'):
            assert_ems_unchanged(clone,INTEGRATION_BASE)
    with pytest.raises(AssertionError,match='EMS V2 alterado'):
        assert_ems_unchanged(clone,'10365c5478b4dd137906b58819cd7f71d8de9cea')
