# 09 · Prueba con usuario externo (criterio 9)

## Objetivo y criterio de éxito

Comprobar si una persona que no participó en el desarrollo puede completar el flujo principal sin instrucciones del equipo: cargar código legacy sintético, configurar una migración, revisar y aprobar reglas, interpretar la equivalencia y descargar el paquete. La prueba es exitosa solo si completa la tarea **sin ayuda**; las dudas, errores y abandonos también son evidencia y no deben ocultarse.

## Preparación (antes de invitar al participante)

- Usar una instalación local con el último build verde y la API disponible; preparar replay por si no hay conexión.
- Dejar `samples/cobol/INTMORA.cbl` accesible, pero no abrirlo ni iniciar una corrida.
- Limpiar ejecuciones anteriores, notificaciones, historial visible y cualquier dato personal.
- Usar únicamente archivos sintéticos. No pedir correo, documentos, credenciales ni datos bancarios reales.
- Preparar cronómetro, grabación de pantalla opcional con consentimiento y esta plantilla. El observador no toca teclado ni mouse.

## Texto que se entrega al participante

> Eres responsable de modernizar una rutina bancaria legacy. En AgenTCS, carga `samples/cobol/INTMORA.cbl`, elige una tecnología destino disponible, inicia la migración, revisa todas las reglas de negocio y aprueba la especificación. Luego confirma cuántos casos son equivalentes, identifica el nivel de oráculo, abre la comparación entre legacy y código generado y descarga el paquete. Detente cuando consideres terminada la tarea. Piensa en voz alta; no hay respuestas incorrectas y estamos evaluando el producto, no a ti.

## Protocolo del observador

1. Leer el texto literalmente, iniciar el cronómetro y no explicar controles ni conceptos.
2. Si pregunta “¿qué hago?”, responder solo: “Haz lo que te parezca más natural”. Registrar la pregunta como fricción.
3. Permitir que se recupere de los errores mediante la acción sugerida por la UI. No corregir rutas, elecciones o comentarios.
4. Detener el tiempo cuando descargue el paquete y declare que terminó, o cuando abandone.
5. Hacer tres preguntas finales: “¿Qué resultado te dio confianza?”, “¿Qué fue confuso?” y “¿Qué esperarías hacer después?”.

## Plantilla de registro

**Prueba:** `UX-EXT-____`  
**Fecha:** ____ / ____ / ______  
**Quién la hizo:** alias o iniciales `________` · rol general `________________`  
**Observador:** alias o iniciales `________`  
**Experiencia previa con migraciones:** ninguna / básica / frecuente  
**Inicio:** `____:____` · **fin:** `____:____` · **duración total:** `________`  
**¿Completó sin ayuda?:** sí / no · **¿Descargó el paquete?:** sí / no

| Hito observable | Completado | Tiempo acumulado | Fricción o error observado |
|---|---|---|---|
| Cargó el archivo y configuró el destino | ☐ | | |
| Inició la migración | ☐ | | |
| Revisó y aprobó todas las reglas | ☐ | | |
| Encontró casos equivalentes y nivel de oráculo | ☐ | | |
| Abrió legacy vs. generado | ☐ | | |
| Descargó el paquete | ☐ | | |

**Ayuda solicitada o recibida (si hubo):**  
____________________________________________________________________

**Qué generó confianza:**  
____________________________________________________________________

**Qué resultó confuso y mejora prioritaria:**  
____________________________________________________________________

**Evidencia guardada:** nombre de captura/video `________________` (sin datos personales).  
**Resultado del criterio 9:** aprobado / repetir después de corregir.

No marcar el checklist de evaluación hasta completar esta plantilla con una sesión real.
