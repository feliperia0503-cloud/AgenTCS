# 09 · Probar con el paquete PL/SQL de la evaluación

> Los archivos de la evaluación (src/ y pruebas/) **no se suben a este repositorio**: es público.
> Guárdalos fuera del repo, p. ej. `C:\Users\<usuario>\Documents\Hackathon`.

## Qué hace el copiloto con ese paquete
| Archivo | Papel detectado | Qué se hace con él |
|---|---|---|
| `src/01_ddl_tablas.sql` | Código | Se instala primero (tablas, índices, secuencias) |
| `src/02_parametros.sql` | Configuración del sistema | Se instala; sus filas son parte del estado base |
| `src/03_…_spec.sql`, `src/04_…_body.sql` | Código | Se instalan; de aquí salen las reglas |
| `pruebas/datos_prueba.sql` | Datos de prueba | NO se extraen reglas; se convierten en `_tablas` (estado inicial) |
| `pruebas/ejecutar_lote.sql` | Script de ejecución | Define el **caso oficial** (lote al 2026-03-31) |

- Reglas: solo del código. Código muerto (p. ej. `fn_calcular_deducible_v1`) se reporta aparte y no se migra.
- Caso oficial: `pr_procesar_lote(DATE '2026-03-31')` sobre los datos del cliente → una fila por siniestro.
- Variantes: casos de borde que heredan las tablas base y cambian solo lo necesario.
- Oráculo: nivel **A** con Oracle (el PL/SQL real se ejecuta); sin Oracle, nivel **C** y el reporte dice por qué.

## Prueba 1 · Sin Oracle (siempre debe funcionar)
```bash
docker compose up --build            # http://localhost:8000, con ANTHROPIC_API_KEY en .env
```
1. Migración → sube los 6 archivos (o un .zip con src/ y pruebas/) → destino Java → iniciar.
2. Reglas: abre "Hallazgos que no son reglas": deben verse los 4 papeles de archivo y el código muerto.
3. Prueba "+ Agregar regla" (tipo "Documenta el legacy", cita líneas reales del body).
4. Aprueba todas las reglas → Validación: debe decir **"Nivel A no disponible (Oracle no configurado…)"**
   y mostrar la tabla **"Ejecución oficial del cliente"** con 17 siniestros (el 1016 no entra: denuncia posterior).

## Prueba 2 · Con Oracle (nivel A)
```bash
docker compose --profile oracle up --build    # la primera vez Oracle tarda 1–2 min en quedar "healthy"
docker compose exec copilot pytest -q tests/test_oracle_runner.py
```
- `test_real_oracle_level_a_with_tables` debe **pasar** (no "skipped").
- Repite la Prueba 1: la Validación debe decir **Oráculo nivel A** y la tabla oficial muestra lo que calculó Oracle.

## Prueba 3 · Pruebas automáticas con los archivos reales
```bash
docker compose exec -e AGENTCS_JURY_DIR=/datos copilot pytest -q tests/test_jurado_e2e.py
```
(monta la carpeta con `-v C:\ruta\Hackathon:/datos` o copia los archivos al contenedor).

## Si algo falla, envía
- La pantalla con el error (incluye la acción sugerida).
- `output/runs/<id>/state.json` (no contiene secretos) y, si existe, `output/runs/<id>/oracle/`.
