# ADR-007 · Oráculo nivel A genérico: ejecutar el legacy de cualquier lenguaje

- **Estado:** Aceptado
- **Fecha:** 2026-11-13
- **Complementa:** ADR-003 (agnóstico de lenguaje), ADR-005 (motor) y ADR-006 (ingesta universal)

## Contexto
La equivalencia funcional pesa 25% y topa los criterios 3–7. Hasta ahora el oráculo siempre era nivel C
(una referencia que el LLM escribe desde la especificación): si una regla se extraía mal, el error se
repetía en el esperado y en el migrado, y la prueba pasaba igual. Necesitamos ejecutar el legacy REAL, en
cualquier lenguaje, sin escribir un runner a mano por cada uno.

## Decisión
### Un lenguaje de origen = `pack.yaml` + `knowledge.md` (sin Python)
`copilot/languages/<id>/pack.yaml` con `role: source` declara extensiones, alias de la ingesta y, si el
lenguaje se puede ejecutar en el contenedor, una sección `runner` (herramientas, comando de compilación,
comando de ejecución, flags permitidos e indicaciones para el arnés). `knowledge.md` lleva la semántica y
las trampas del lenguaje y se inyecta en el extractor. `source_pack.py` los carga; `registry._sources()`
los registra.

| Pack | Runner | Nivel máximo |
|---|---|---|
| cobol | GnuCOBOL (`cobc -x`) | A |
| php | `php` CLI | A |
| delphi (alias pascal) | Free Pascal en modo Delphi | A (lógica sin VCL) |
| csharp-legacy | Mono (`mcs` + `mono`) | A |
| java-legacy | JDK (`javac` + `java`) | A |
| plsql (alias sql) | Oracle Free (`docker compose --profile oracle`) | A con Oracle; si no, C declarado |
| rpg, vb6 (alias vbnet) | — | B / C |

### El LLM escribe solo el arnés; la plataforma hace todo lo determinista (`source_runner.py`)
1. El agente `legacy_harness` propone un plan JSON: modo `driver` (un programa mínimo en el MISMO lenguaje
   que lee entradas, invoca el legacy y escribe salidas) o `direct` (el legacy ya lee de stdin; se
   declaran regex de salida).
2. Validación determinista del plan: no puede sobrescribir archivos legacy, debe compilar o referenciar el
   legacy, tamaño acotado, flags en lista blanca del pack, campos del contrato aprobado.
3. Compilación y ejecución en el sandbox, **un proceso por caso**: las entradas viajan por stdin (una
   línea por campo, `plain` o `implied` con ceros a la izquierda) y la salida usa el protocolo
   `@@campo=valor`, `@@ROW`, `@@ERROR=código|mensaje`.
4. Normalización determinista al tipo neutral (signo al final, punto implícito, relleno de escala). Nunca
   redondea: si el legacy imprime más decimales, la diferencia queda visible. El mensaje de error se toma
   del contrato, no del LLM.
5. Si compila mal o algún caso no produce salida válida, el error vuelve al LLM (hasta
   `AGENTCS_HARNESS_ATTEMPTS`, 3 por defecto).
6. Si aun así no se logra (falta el compilador, dependencias de VCL/CICS/EJB...), el oráculo baja a nivel B
   o C y el reporte lo declara: *"Nivel A no disponible (motivo). …"*.

El plan del arnés se guarda en `OracleResult.reference_code` para auditoría.

## Consecuencias
- (+) La equivalencia se mide contra el comportamiento real: los tests de `tests/test_source_runner.py`
  ejecutan COBOL, PHP, Delphi, C# legacy y Java legacy reales y capturan el truncamiento verdadero.
- (+) Agregar un lenguaje ejecutable = un YAML y un Markdown; el motor no cambia.
- (+) Nunca se queda sin oráculo: cae a B/C y lo declara.
- (−) El arnés lo escribe un LLM. La validación impide sobrescribir o ignorar el legacy, pero no puede
  probar que el arnés no contenga lógica propia; por eso es mínimo, se guarda y se muestra para revisión.
- (−) Programas que leen archivos, bases de datos o pantallas (CICS, VCL) necesitan más trabajo: hoy caen a C.
- La imagen Docker agrega `php-cli`, `fp-compiler` y `mono-runtime`.

## PL/SQL con tablas (`oracle_runner.py`)
El caso real de la demo es un script PL/SQL completo: DDL de tablas, paquetes, funciones y lógica que lee y
modifica datos. Sin tocar los contratos congelados:
- El extractor declara cada tabla que la rutina lee o modifica como `Entity(kind="tabla")` con las columnas
  usadas. Los parámetros de la rutina son `io.inputs`; los efectos relevantes sobre tablas son salidas
  escalares (p. ej. `estado_final`).
- Cada caso trae el estado inicial de la base en `input["_tablas"]` = `{"TABLA": [filas]}`. El generador de
  casos también busca fronteras en columnas de tabla (en PL/SQL las condiciones suelen estar sobre datos).
- Nivel A: esquema temporal por intento, script tal cual (división estilo SQL*Plus; solo se quita el prefijo
  de esquema, y se declara), verificación de `USER_ERRORS`, FK deshabilitadas para cargar filas de prueba
  (los triggers siguen activos), por caso `DELETE` + `INSERT` deterministas, bloque anónimo del LLM con
  binds `:entrada` que solo puede invocar el legacy y leer (prohibido DML/DDL/SQL dinámico), salida por
  `DBMS_OUTPUT` con el protocolo `@@`, `ROLLBACK`, y al final `DROP USER CASCADE`.
- Errores no capturados (`RAISE_APPLICATION_ERROR`) se convierten en el código del contrato, sin importar si
  el contrato lo escribe `ORA-20001`, `-20001` o `20001`.
- Destinos: si el caso trae `_tablas`, el código migrado usa un repositorio en memoria detrás de un puerto del
  dominio; el adaptador real de base de datos va en `infrastructure/`.
- Credenciales de Oracle solo en variables de entorno; el sandbox del código generado no las hereda.

## Corrección asociada
`loop.py` marcaba una REGRESIÓN solo si el intento no mejoraba la similitud. Ahora cualquier caso que pasó
en un intento anterior y vuelve a fallar se marca como REGRESIÓN, aunque la similitud global suba.
