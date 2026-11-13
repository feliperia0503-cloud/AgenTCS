---
name: dotnet-legacy-semantics
description: Cómo leer y migrar código .NET legacy (C# y VB.NET en .NET Framework 1.x–4.x, WebForms, WCF, ADO.NET, también VB6) y Java legacy (1.4–6, EJB 2), separando reglas de negocio de la infraestructura. Usar al analizar o migrar estos lenguajes orientados a objetos antiguos.
---

# Semántica .NET / Java legacy

## Señales de código legacy y su traducción
| Legacy | Problema | Moderno |
|---|---|---|
| `ArrayList`, `Hashtable`, `Vector` (sin genéricos) | casts implícitos, errores en runtime | colecciones genéricas / tipadas |
| Lógica en code-behind (`Page_Load`, `btn_Click` en WebForms) | negocio mezclado con UI | extraer a servicio de dominio |
| `DataSet`/`DataTable`/`SqlDataReader` en todas partes | dominio = tablas | entidades/records + repositorio |
| SQL concatenado (`"... WHERE id=" + id`) | inyección SQL | consultas parametrizadas en el adaptador (reportar como hallazgo) |
| Clases estáticas "Helper"/"Utils" de miles de líneas | God class | servicios de dominio cohesivos |
| `try { } catch { }` vacío / `catch (Exception)` genérico | errores silenciosos | excepciones de dominio explícitas |
| `On Error Resume Next` (VB6/VB.NET) | ignora errores | manejo explícito; marcar confianza baja |
| `Variant` (VB6), `Object` | tipos dinámicos | tipos fuertes inferidos del uso |
| Session/ViewState/`HttpContext.Current` | estado global | parámetros explícitos |
| EJB 2 (`SessionBean`, `ejbCreate`, JNDI lookups) | ceremonia de infraestructura | servicio simple + inyección de dependencias |
| `config` (`web.config`, `app.config`) con cadenas de conexión | **secretos** | enmascarar en ingesta; variables de entorno |

## Semántica numérica
- C# `decimal` = decimal exacto (28–29 dígitos). `Math.Round(x, n)` **por defecto es HALF_EVEN (banquero)**: trampa clásica al migrar a Java (`HALF_UP`). Usar `MidpointRounding` explícito.
- VB.NET `CDec`, `CInt` (CInt redondea HALF_EVEN), `Fix`/`Int` truncan distinto con negativos.
- VB6 `Currency` = escala fija de 4 decimales.
- Java legacy `double` para dinero → el comportamiento "correcto" a replicar puede incluir errores de punto flotante: documentar como supuesto y decidir en HITL.
- `DateTime` sin zona horaria; `DateTime.Now` → inyectar reloj.

## Negocio vs. infraestructura
Negocio: cálculos, validaciones, reglas en servicios/helpers, condicionales sobre conceptos del dominio.
Infraestructura: ADO.NET/JDBC, UI (WebForms, WinForms, JSP/Servlets), WCF/SOAP, configuración, logging, archivos.

## Ejecución (oráculo)
- C# .NET Framework sin dependencias de Windows: compilar con **Mono** (`mcs`) o con .NET 8 si es compatible → nivel A.
- Con dependencias de Windows (WebForms, COM, registro): extraer la clase de negocio a un harness de consola; si no compila, nivel C.
- Java legacy: suele compilar con JDK 21 (`-source 8` mínimo) tras pequeños ajustes → nivel A.
