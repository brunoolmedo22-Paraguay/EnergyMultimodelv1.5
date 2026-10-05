# Energy MultiModel V1.3.1 — hotfix NumPy 2.5+

## Correção

- Corrigida a integração numérica dos módulos **Bateria** e **H₂ / PEMFC** no Streamlit Cloud.
- O código anterior usava `getattr(np, "trapezoid", np.trapz)`. O terceiro argumento de `getattr` é avaliado imediatamente, portanto a simples ausência de `np.trapz` no NumPy 2.5+ causava `AttributeError` mesmo quando `np.trapezoid` existia.
- Implementado fallback preguiçoso: primeiro `np.trapezoid`, depois `np.trapz` para NumPy antigo e, por último, uma implementação trapezoidal vetorizada independente.
- Adicionado teste de regressão que remove temporariamente `np.trapz` e valida os KPIs de energia.
- Novo inicializador: `INICIAR_ENERGY_MULTIMODEL_V1.3.1.bat`.

Nenhuma equação física dos modelos de bateria ou PEMFC foi alterada; o hotfix afeta somente a rotina de integração dos KPIs.
