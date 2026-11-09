# C-EOL-01 — alcance de la política eólica y evolución del EMS

PR #18: https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/18 . Corrección de tests y evidencia; sin cambios de producción, curvas, parámetros o reglas físicas. No se hace merge.

## Problema reproducido

`assert_context()` invocaba `assert_ems_unchanged(root, 10365c5)` en cada ejecución de las guardias. Eso convertía una evidencia de alcance de la misión en una prohibición perpetua de cambios EMS. Además, las tres guardias consultaban bases Git antiguas y saltaban la comprobación en clones superficiales.

No bastaba con quitar una llamada: sus propios `git diff` contra el árbol móvil también rechazaban la evolución de otras entregas. C-EOL-01 separa dos responsabilidades.

## Comprobaciones permanentes de regresión

1. Los nueve archivos eólicos existentes y los doce artefactos de curvas/tests ya publicados mantienen EXACTAMENTE sus SHA-256 anteriores. El manifiesto `wind_guard_policy_v1.json` no cambió; tampoco sus hashes originales, las curvas ni `wind_historical_v1.json`.
2. Se comparan los seis registros históricos completos, incluida la familia de densidades Nordex, y se mantienen las 12 comparaciones numéricas independientes. La carpeta `config/wind_curves` debe contener exactamente los archivos admitidos: una curva no autorizada también falla aunque no modifique otra existente.
3. Las tres guardias ejecutan sus aserciones de alcance sobre la entrega histórica auditada, no sobre todo el desarrollo futuro. Los deltas se conservaron desde objetos Git de las bases originales al commit publicado `96215438e0d4d57bcf600f62b5ae3f2d3c25da9d`, cuando las tres guardias ya pasaban. No se inventaron listas para aprobar una ejecución actual.
4. Solo se protege por AST la función de auditoría eólica de cada guardia, conservando sus aserciones. No se inmoviliza el resto del módulo de tests: otros pisos pueden añadir sus propias comprobaciones. Las verificaciones arquitectónicas existentes siguen ejecutándose sobre el código real.

Por tanto, una integración independiente puede añadir o modificar archivos EMS sin modificar la evidencia de lo que hizo esta misión. Esto no declara aprobado cualquier cambio del EMS: su autorización y validación corresponden al PR que lo introduce y a sus tests numéricos/arquitectónicos.

## Auditoría explícita del diff de la misión

`assert_ems_unchanged(root, base, head, include_worktree=True)` sigue disponible, pero ya NO se llama desde el contexto permanente. Exige la base/head de la misión que se quiere auditar. Compara el identificador de la subárbol EMS entre esas revisiones y verifica también cambios locales preparados/no preparados y archivos nuevos.

Para la entrega actual del PR #18, desde la raíz:

```bash
PYTHONDONTWRITEBYTECODE=1 python tests/ems_v2/wind_guard_policy.py \
  --audit-mission-base 10365c5478b4dd137906b58819cd7f71d8de9cea
```

Resultado verificado: `EMS inalterado; catálogo e referências históricas íntegros`. Un commit EMS dentro del rango auditado sigue fallando. Para otro PR se debe indicar SU base; no reutilizar indefinidamente la base histórica de la misión eólica. La herramienta no cambia ni deduce automáticamente el alcance para convertir un fallo en éxito.

## Clones superficiales: dependencia resuelta, sin omisiones

Evidencia retenida: `tests/fixtures/wind_guard_evidence_v1.json`, SHA-256 **b3e81f4c658f07c97d242a1fa0ab2cd01b362bd22cea4f0363931d367f54c316**, fijado literalmente en el soporte de tests. Contiene:

- Los bytes originales de los nueve archivos y las tres guardias, contrastados contra los MISMOS hashes originales anteriores.
- Los tres deltas de entregas históricas, sus commits completos y objetivos explícitos.
- Objetos Git originales de commit y árbol raíz de `10365c5` y `9621543`. Se verifican sus identidades Git recalculando el hash de objeto con tipo/longitud, la referencia commit→árbol y la entrada de directorio `ems_v2`.

Ambos commits referencian el mismo subárbol EMS: **7661032cfcb6d1cb54f1136fc2b13a0cb94144c7**. Esta prueba de identidad no necesita descargar el árbol EMS histórico completo. La auditoría explícita puede resolver la base de PR #18 con esa evidencia si el objeto antiguo no está en el clon; el HEAD real se resuelve localmente.

Las guardias no hacen fetch, no sustituyen una referencia por el tip remoto y no hacen `pytest.skip` por falta de historia. La evidencia y el manifiesto tienen hashes fijos; no hay código que los regenere durante el test.

## Pruebas adversariales ejecutadas

- **135 passed** en el lote focalizado, incluida la cuarta guardia de aislamiento intacta.
- Clon real `git clone --depth 1 file://...` de un snapshot temporal del código actual, sin NINGUNO de los objetos históricos requeridos antes. Las tres guardias y los tres tests de aislamiento 3A ejecutan **14 passed, 0 skipped** en ese clon; también pasa la auditoría CLI explícita.
- En ese clon se crea y se integra una rama sintética independiente 3C-4: archivos nuevos y cambio de un módulo EMS existente. El mismo lote vuelve a ejecutar **14 passed, 0 skipped**. Son centinelas de integración, NO una implementación ni una validación física del planificador.
- Después de esa integración, cambiar un nodo SWIFT o añadir una curva no autorizada sigue provocando fallo. Auditar deliberadamente el cambio EMS de otro PR como si perteneciera al rango eólico original también falla: no se oculta un cambio de misión.
- Se conservan los adversariales anteriores de parámetros y curvas históricas, hashes del manifiesto, identidades, archivos permitidos, borrados/renombrados, symlinks y cambios EMS dentro de un rango explícitamente auditado. Se añade corrupción de la nueva evidencia y evolución legítima del módulo de tests.
- Históricos por separado: **12 passed, 98 deselected**; la suite completa posterior ejecuta también los no seleccionados.

Resultado de la suite completa: **1765 passed, 0 failed, 0 skipped, 7 warnings**, 411,59 s. Ver `RESULTADOS_REGRESION.md`.

## Estado de la integración real

Durante esta corrección se observó `main` en `19aa3ac328f337e31ec4c36baa837c056299a57a` (PR #17, 3C-4). La rama del PR #18 sigue conservando su base original; no se reescribió su historia ni se incorporó código de producción de otra rama. La prueba adversarial descrita simula la integración posterior; no equivale a afirmar que se ejecutó la suite combinada del PR #17. Las guardias propias que otras entregas mantengan contra árboles móviles deberán distinguir igualmente su entrega histórica del diff de futuros PR.
