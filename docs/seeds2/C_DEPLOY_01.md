# C-DEPLOY-01 — regularização da matriz CI

A PR #25 incluiu `-r requirements-ems_v2.txt` em `requirements.txt` para instalar Pyomo e HiGHS
no deploy do Streamlit Cloud. **Essa inclusão é necessária; não será revertida.**

O workflow antigo instalava todas as dependências em ambas as modalidades e exigia,
na modalidade sem solver, a ausência de Pyomo/HiGHS. A própria instalação contradizia
o teste. Além disso, duas guardas históricas proibiam qualquer modificação de
`requirements.txt` desde suas bases, apesar da inclusão autorizada em `f523035`.

## Alterações

- Na matriz `solver=false`, **somente no ambiente temporário do CI**, desinstalar
  `pyomo` e `highspy` antes de verificar sua ausência. O job `solver=true` permanece inalterado.
- `deploy_requirements_guard_policy.py`: autorizar exclusivamente o SHA-256 literal
  do `requirements.txt` de `f523035`, e exclusivamente a inserção declarada no workflow,
  validada em relação ao commit base `1f8b0f6`. Outros arquivos/status permanecem protegidos.
- Acrescentar testes positivos e negativos para a política de autorização.

## Intocados

`requirements.txt`, `requirements-ems_v2.txt`, motor MILP-MPC, runner, modelos físicos,
contratos, persistência, exportações e interfaces.

## Aceitação

Os dois jobs `scientific-regression (true/false)` devem terminar verdes.
Não usar `continue-on-error`, `xfail` nem desativar testes para esconder falhas.
