# ADR-006 · Ingesta universal y múltiples lenguajes destino sobre Docker

- **Estado:** Aceptado
- **Fecha:** 2026-11-13

## Contexto
El código que recibiremos puede venir en cualquier lenguaje (COBOL, PL/SQL, Delphi, RPG, VB6, C#, Java
antiguo…) y en cualquier forma (archivos sueltos, un comprimido o un repositorio que no siempre es GitHub).
El destino tampoco puede limitarse a uno: el cliente elige. Docker ya trae los runtimes de varios destinos.

## Decisión
### Ingesta (`copilot/api/sources.py`)
- Entradas: archivos sueltos, comprimidos **.zip / .tar / .tar.gz / .tgz** y repositorios **HTTPS** de
  cualquier proveedor (GitHub, Bitbucket, GitLab, Azure DevOps…) con clon superficial de solo lectura.
- Más de 40 extensiones reconocidas; el **lenguaje dominante** se calcula por líneas de lógica (se ignoran
  formularios, configuración y scripts). Un lenguaje sin pack de origen usa el segmentador genérico
  (Delphi, ABAP, RPG, PL/SQL, métodos tipo C, Python…) con confianza reducida y declarada.
- Seguridad: bloqueo de zip slip y rutas absolutas, límites (2 MB por archivo, 60 MB descomprimido,
  2.000 archivos), binarios y carpetas de dependencias descartados, URL sin credenciales, rama validada.
- Presupuesto de contexto (`AGENTCS_EXTRACTION_CHARS`, 120.000 caracteres por defecto): si el código lo
  supera, el extractor recibe los archivos con mayor densidad de lógica y la especificación lo declara.

### Destinos (`copilot/languages/<id>/`)
| Pack | Verificación (sin descargar dependencias) | Punto de entrada que genera el LLM |
|---|---|---|
| `java` | `javac` + `java`, arnés con lector JSON propio | `src/main/java/app/Entry.java` → `run(Map)` |
| `csharp` | `dotnet build` de un proyecto de consola de la plataforma | `App/Entry.cs` → `Run(IDictionary)` |
| `typescript` | `tsc` + `node`, decimal.js global | `src/app.ts` → `run(input)` |
| `python` | intérprete de la plataforma | `app.py` → `run(input)` |

- El framework elegido (Spring, Quarkus, ASP.NET, NestJS, FastAPI…) y la arquitectura se pasan al
  generador. El código propio del framework va en `infrastructure/`, que **no se compila en la
  verificación**: así se verifica el núcleo de negocio sin necesitar las dependencias del framework, y el
  paquete entregado incluye los adaptadores.
- Catálogo único en `copilot/api/catalog.py`, expuesto en `GET /api/catalog` con la disponibilidad real de
  herramientas en el equipo; la UI ya no tiene listas propias.
- Si faltan herramientas (p. ej. sin Docker), la API responde `TOOLCHAIN_MISSING` con la acción
  "ejecuta con Docker" en vez de fallar a mitad de la migración.

### Docker
La imagen trae JDK 21, .NET 8 SDK (precalentado), Node 22 + TypeScript 5 + decimal.js y Python 3.12: los
cuatro destinos funcionan sin red durante la demo.

## Consecuencias
- (+) Cualquier origen, cuatro destinos, una sola imagen, un solo comando.
- (+) Agregar un destino = un pack con arnés y comandos de build/ejecución; el motor no cambia.
- (−) La verificación cubre el núcleo; los adaptadores del framework se entregan pero no se compilan aquí
  (se compilan en el pipeline del cliente con sus dependencias).
- (−) El pack de C# no se probó fuera de Docker (en el entorno de desarrollo no había .NET).
