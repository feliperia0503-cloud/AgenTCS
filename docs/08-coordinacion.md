# 08 · Coordinación entre máquinas

| Máquina | Rama | Tarea actual | Estado | Bloqueado por |
|---|---|---|---|---|
| A | `maquina-a/oraculo-packs` | Oráculo nivel A, packs de origen y Dockerfile | En curso | — |
| B | `maquina-b/e2e-destinos` | Corrida real E2E, destinos, samples y API | En curso | — |
| C | `maquina-c/ux-docs` | UI y documentación: coordinación inicial completada; continúa la interfaz de resultados | En curso | — |

## Acuerdos de trabajo

- Cada máquina actualiza su propia fila al terminar una tarea.
- Las solicitudes que requieran cambios de API se registran aquí para la Máquina B; no se modifica el contrato de forma unilateral.
- No se registran datos reales, secretos ni llaves en la interfaz o la documentación.
