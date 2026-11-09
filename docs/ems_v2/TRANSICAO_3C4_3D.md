# Transición 3C-4 → siguiente etapa (integración)

3D **no está autorizado**; nada de lo siguiente se implementó en 3C-4.

| Piso | Responsabilidad | No es responsabilidad |
|---|---|---|
| **3C-4 (este)** | Planificador de largo plazo, costo de continuación verificable, MPC jerárquico causal, auditoría, comparadores científicos | Integración con catálogo/UI/runtime; datos reales |
| **Siguiente** | Conectar el EMS V2 (3C-3/3C-4) a microrredes reales del catálogo, persistencia en `MicrogridStore`, UI | Reformular el EMS V1.6 |

## 1. Lo que la integración encontrará disponible

| Necesidad | Disponible | Dónde |
|---|---|---|
| Controlador hierárquico por puntos de extensión | `ControladorMPCHierarquico` | `hierarquia/mpc.py` |
| Configuración declarativa del planificador (sin defectos) | `ConfiguracaoPlanejador3C4` + validación | `hierarquia/contrato.py` |
| Evidencia sellada por ventana y por misión | `RegistroCoordenacao3C4`, `VinculoHierarquico3C4`, `RegistroMissaoHierarquica3C4` | `hierarquia/mpc.py` |
| Retomada y auditoría integral | `retomar_controlador_hierarquico`, `auditar_missao_hierarquica` | `hierarquia/auditoria.py` |
| Degradación declarada (≡ MPC 3C-3) | `DEGRADACOES` | `hierarquia/contrato.py` |
| Comparación científica | `comparadores.comparar` | `hierarquia/comparadores.py` |

## 2. Pendientes que bloquean una microrred real

1. B3C4-01 (deriva numérica heredada) — decisión del responsable sobre la proyección/tolerancia de energía.
2. B3C3-01/02 (PCC y tarifas reales), B3C2-02 (estimador de estado), D07 (tolerancias).
3. Calibración de Φ_L y de los parámetros del planificador (H_L, puntos, tolerancias) con procedencia.
4. Presupuesto computacional del planificador (B3C4-05) antes de cualquier uso fuera de simulación.

## 3. Riesgos heredados

- Valor futuro determinista (sin incertidumbre); tarifas y equipos sintéticos; misma malla temporal en ambos niveles.
- SHA-256 no es firma (B3C4-08).
