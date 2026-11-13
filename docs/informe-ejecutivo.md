# AgenTCS · Modernización verificable de software bancario

## Decisión ejecutiva

AgenTCS reduce el riesgo de modernizar aplicaciones críticas al convertir el código legacy en una especificación de negocio trazable, generar una implementación moderna y comparar ambos sistemas con los mismos casos. La recomendación es validarlo en un piloto acotado, con datos sintéticos, criterios de salida acordados y revisión humana antes de generar el paquete final.

## El problema

Procesos bancarios esenciales siguen dependiendo de COBOL, PL/SQL, RPG, Java antiguo y otras tecnologías con documentación incompleta. La lógica real está dispersa entre código, supuestos y conocimiento de especialistas. Una traducción manual o basada solo en IA puede cambiar cálculos, redondeos y caminos de error sin hacerlo visible, elevando el costo de pruebas y regresión.

## La solución

AgenTCS guía un flujo auditable: ingiere y sanitiza el código; analiza dependencias y riesgos; extrae reglas con archivo y líneas de origen; exige aprobación humana; propone arquitectura; genera el destino; ejecuta pruebas diferenciales; autocorrige; y entrega código, pruebas y reportes. La interfaz muestra cada fase, la evidencia del oráculo, las diferencias por intento y el código legacy frente al generado.

## Diferenciador

El núcleo usa una especificación neutral y adaptadores, por lo que no depende de un único par origen–destino. Su valor principal no es “traducir código”, sino **demostrar equivalencia funcional ejecutando el legacy** cuando existe un runner de nivel A. Los niveles B y C quedan declarados cuando la evidencia disponible es menor; nunca se presentan como equivalentes a una ejecución real.

## Evidencia y métricas del piloto

| Indicador | Resultado |
|---|---|
| Par origen → destino ejecutado | [PENDIENTE: dato de la corrida real de la Máquina B] |
| Nivel de oráculo alcanzado | [PENDIENTE: dato de la corrida real de la Máquina B] |
| Casos equivalentes / total | [PENDIENTE: dato de la corrida real de la Máquina B] |
| Diferencias en cálculos y redondeos | [PENDIENTE: dato de la corrida real de la Máquina B] |
| Cobertura de líneas / ramas | [PENDIENTE: dato de la corrida real de la Máquina B] |
| Hallazgos críticos | [PENDIENTE: dato de la corrida real de la Máquina B] |
| Duración punta a punta | [PENDIENTE: dato de la corrida real de la Máquina B] |

## Ahorro estimado y control del riesgo

El ahorro debe calcularse con datos del banco y de la corrida, no con supuestos comerciales: **ahorro por rutina = costo del esfuerzo manual de análisis, migración y regresión − costo del esfuerzo asistido y su revisión**. Para el piloto: esfuerzo manual base, tarifa combinada, esfuerzo de revisión y ahorro monetario son [PENDIENTE: dato de la corrida real de la Máquina B].

El piloto no usa datos reales ni secretos. Todo hallazgo conserva trazabilidad; una persona aprueba las reglas; y el paquete solo se considera apto cuando los gates acordados están en verde. El siguiente paso es seleccionar una rutina representativa y una de borde, fijar la línea base manual con el banco y validar conjuntamente la evidencia generada.
