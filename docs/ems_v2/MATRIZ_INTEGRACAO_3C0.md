# Piso 3C-0 — Matriz de integración SEEDS2 → EMS V2 (entregable B)

Correspondencia entre los componentes **existentes** del SEEDS2 (verificados en el código de `main` `3c65d98`) y los
contratos de la puente. «Reutilizado» = la puente llama o replica la misma regla sin duplicar lógica científica.

## 1. Identidad, catálogo y persistencia

| Componente SEEDS2 | Ubicación | Contrato 3C-0 | Uso | Estado |
|---|---|---|---|---|
| Catálogo de microrredes (`uid`, incarnación, estado) | `seeds2/microgrid/registry.py` (`MicrogridRegistry.get/open`) | `IdentidadeMicrorrede.uid/incarnacao` | `ler_inventario` abre **por el catálogo** (`must_exist`, incarnación conferida) | Reutilizado (lectura) |
| Banco por microrred, revisiones, huella | `MicrogridStore.snapshot/current/get_revision` | `revisao_config`, `impressao_config` | Revisión actual + incarnación en un único instantáneo (H-03) o revisión fijada | Reutilizado (lectura) |
| Huella del inventario físico / por equipo | `seeds2/operation/scenarios.py` (`inventory_fingerprint`, `equipment_fingerprint`) | `impressao_inventario`, `DispositivoInventario.impressao_digital` | Misma regla del Piso 2A ⇒ comparación directa con `inventory_ref` | Reutilizado |
| Exclusión con lápida/incarnación (H-01/H-02) | `registry.delete`, `MicrogridStore._check_alive` | — | Microrred excluida ⇒ `MicrogridNotFound` en la lectura | Reutilizado |
| Persistencia de rodadas (`scenario_runs`) | `MicrogridStore.start_run/finish_run` | `RegistroExecucaoEMS` | **No usado**: registro EMS V2 en archivo JSON inmutable (D-3C0-07) | Brecha de integración |

## 2. Inventario y bancadas (modelos)

| Tipo SEEDS2 (`kind`) | Registro / unidad | Modelo científico existente | Dispositivo 3C-0 (`tipo`, `papel_ems`) | Recursos EMS (3A) | Observación |
|---|---|---|---|---|---|
| `pv` (usina) | `eq-…` con `arrays[]` | — (agrupador) | `pv_usina`, `agrupador` | ninguno | Disponibilidad del escenario declarada aquí |
| arreglo FV | `arr-…` | `models.pv_module` (`simulate_noct_efficiency_model`) | `pv_arranjo`, `renovavel` (`fv`) | 1 `PotencialRenovavel` | `A_pot` exige el modelo físico sobre el clima (brecha) |
| `wind` | `eq-…`, `count` | `models.wind_model` | `eolica`, `renovavel` | 1 por registro | Potencia nominal por turbina del catálogo |
| `battery` | `eq-…` (Ns/Np del modelo) | `models.battery_model` (Tremblay / 2RC) | `bateria`, `armazenamento` | 1 `EspecBateria` | Faltan η, P en la barra, autodescarga |
| `pemfc` | `eq-…`, `quantity` | `h2_pemfc` (perfil equivalente aproximado) | `pemfc`, `gerador` (`pemfc`) | `quantity` unidades `eq#k` | P_max del modelo de referencia; faltan P_min, curva q(P) |
| `thermal` | `eq-…` | `models.thermal_model` (pequeña unidad) | `termica`, `gerador` (`termica`) | 1 `EspecGerador` | Gran usina no representable |
| Retirados | `retired[]` | — | `InventarioMicrorrede.retirados` | ninguno | Condición para retirado ⇒ `erro` |
| Bancada MIX | `mix_app.py` | `simulation/mix_engine` | — | — | Inaccesible en la UI; no integrado |

Especificaciones de parámetros reutilizadas: `seeds2/microgrid/config.py` (`PARAM_SPECS`, `ARRAY_SPECS`: nombre y unidad
declarada), derivaciones `seeds2/microgrid/derived.py` (`battery_derived`, `pv_array_nominal`), catálogos
`seeds2/microgrid/references.py`. **No** se usa `seeds2/microgrid/adapter.py::build_plan` (agrega por tecnología).

## 3. Escenario, previsiones y ejecución

| Componente SEEDS2 | Ubicación | Contrato 3C-0 | Estado |
|---|---|---|---|
| Versión inmutable del escenario | `MicrogridStore.get_scenario(uid, version)` | `CenarioEMS(cenario_uid, versao_cenario, impressao_cenario)` | Reutilizado (lectura) |
| `inventory_ref` (revisión + huellas) | `seeds2/operation/scenarios.py` | `ReferenciaInventario` + `coerencia_cenario_inventario` | Reutilizado |
| Inicialización (`availability`, `soc0_pct`, `state`, `units_on`, `power_kW`) | `seeds2/operation/initialization.py` | `CondicaoInicialDispositivo` (SOC % → fracción exacta registrada) | Reutilizado |
| Huérfanos (`initialization.orphaned`) | idem | `CenarioEMS.orfaos` | Reutilizado |
| Previsiones (Piso 2B: demanda/clima, base temporal original) | `seeds2/operation/forecasts.py` | `ConjuntoPrevisao` (series por recurso, emitidas) | **Brecha**: semántica no declarada, clima ≠ potencial, sin emisión registrada, demanda sin UID/criticidad (`constatacoes_previsoes_seeds2`) |
| Misión (inicio, fuso, duración) | `seeds2/operation/strategy.py`, `mission.py` | `DefinicaoTemporal` (`MalhaTemporal`) | Contrato listo; conversión pendiente |
| Preflight V1.6 (fases A/B) | `seeds2/operation/preflight.py` | `preflight_ems_v2` | Independientes: el de V1.6 sigue gobernando el motor legado |
| Runner/rodadas V1.6 | `seeds2/operation/runner.py` | `executar` + `RegistroExecucaoEMS` | Sin conexión (3D) |
| Archivo Científico / dossier | `seeds2/archive`, `seeds2/report` | `RegistroExecucaoEMS` (JSON canónico, sellado) | Compatible por diseño (JSON + SHA-256); sin integración |

## 4. Núcleo científico EMS V2

| Componente | Ubicación | Uso en 3C-0 |
|---|---|---|
| `EntradaModeloEMS` + `validar_entrada` | `ems_v2/contracts.py` | Destino de `montar_entrada`, sin relajación |
| `MalhaTemporal`, `SerieTemporal`, `alinhar_a_malha` | `ems_v2/timegrid.py`, `series.py` | Definición temporal, previsiones y realizaciones |
| `Parametro`, `Procedencia`, `units` | `ems_v2/parameters.py`, `provenance.py`, `units.py` | Cadena bruto → canónico y procedencia por valor |
| `resolver` (3B-P) | `ems_v2/milp/solver.py` | Produce el `ResultadoResolucao` que `plano_de_resultado` consume |
| Auditor / integridad | `ems_v2/audit.py`, `milp/integridade.py` | Condición para que exista plan (`aceito`) |
| `Tolerancias` (provisionales, D07) | `ems_v2/audit.py` | Usadas por el ejecutor algébrico; no relajadas |
