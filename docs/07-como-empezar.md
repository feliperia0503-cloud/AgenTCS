# 07 · Cómo empezamos a construir

## Paso 0 · Instalar lo mínimo (solo la máquina de desarrollo)
1. Clonar el repositorio en `C:\source\AgenTCS`.
2. PowerShell como administrador: `.\scripts\setup-windows.ps1` (Git, Docker Desktop, VS Code + Dev Containers) → reiniciar.
3. Abrir Docker Desktop y dejarlo corriendo.
4. Copiar `.env.example` a `.env` y poner la `ANTHROPIC_API_KEY`.

## Paso 1 · Abrir el proyecto en el contenedor
1. VS Code → abrir `C:\source\AgenTCS` → "Reopen in Container" (la primera vez construye la imagen; tarda unos minutos).
2. Ya dentro, en la terminal de VS Code: `cobc --version`, `java -version`, `mvn -v` → todo viene del contenedor.
3. `pytest -q` → deben pasar todas las pruebas del núcleo y de la API.
4. `claude` → comprobar con `/skills` que cargaron las 9 skills del proyecto.
5. Prueba de humo de la demo: desde PowerShell en `C:\source\AgenTCS`, `docker compose up --build` → abrir http://localhost:8000 (AgenTCS en modo demo).

## Paso 2 · Tres personas, una máquina
Varias terminales dentro del Dev Container, cada una con su worktree y su sesión de Claude Code:
```bash
git worktree add ../agentcs-verif -b feat/verification   # B
git worktree add ../agentcs-ui    -b feat/ui             # C
# A trabaja en la carpeta principal, rama feat/agents
```
Uno al teclado, los otros revisando, preparando datos y pitch; rotar.

## Paso 3 · Contratos del núcleo (los 3 juntos, corto) — lo más importante
En `copilot/contracts/` (Pydantic + Protocols), siguiendo la skill `language-adapters`:
`NeutralType`, `Spec` (reglas + modelo + contrato E/S + casos), `Rule`, `AnalysisResult`, `Case`,
`CaseOutput`, `VerificationReport`, `RunState`, y las interfaces `SourceAdapter`, `LegacyRunner`,
`TargetAdapter`. Commit a `main` primero: es lo que hace el sistema agnóstico y permite trabajar en paralelo.

## Paso 4 · Primeros prompts para Claude Code
**A · Núcleo y adaptadores**
> Implementa el núcleo agnóstico en `copilot/`: registro de packs que descubre `copilot/languages/*/pack.yaml`,
> un segmentador genérico de respaldo, y el pipeline (hoy: motor de autocorrección, ADR-005): ingesta (detectar lenguaje con los packs +
> sanitizar) → análisis (SourceAdapter) → Spec neutral (Claude, salida JSON validada con Pydantic) →
> interrupt de aprobación → generación (TargetAdapter) → verificación. Incluye modo replay (caché del LLM
> por hash del prompt). Luego crea los packs `cobol` (origen) y `java` (destino). El núcleo no debe mencionar
> ningún lenguaje concreto. Sigue language-adapters, business-rule-extraction y clean-architecture-targets.

**B · Verificación**
> Crea `samples/cobol/AMORTIZA.cbl` (amortización francesa, GnuCOBOL, formato fijo) con copybook, COMP-3,
> COMPUTE con y sin ROUNDED, tasa preferencial por monto, validaciones con códigos de error, PERFORM THRU y
> GO TO. Implementa en `copilot/verification/` el comparador neutral (cases.json / expected.json /
> actual.json, decimales como string, tolerancia cero) y el `LegacyRunner` de COBOL que traduce los casos
> JSON al formato del programa. Genera casos sintéticos normales, de frontera e inválidos.
> Sigue cobol-semantics y golden-master-testing.

**C · Experiencia**
> En `ui/` (AgenTCS), reemplaza los datos de maqueta por la API usando `src/api/client.js` y
> `src/api/adapters.js`, siguiendo la lista "Pendiente" de `ui/README.md`: crear ejecución y sondear su
> estado, reglas desde `run.spec.rules` con aprobar/ajustar/rechazar (comentario obligatorio si confianza
> < 0,7), aprobar la especificación, pruebas desde `run.verification` con nivel de oráculo y diferencias,
> carga de archivos, vista lado a lado legacy/regla/código nuevo, enmascaramiento visible y descarga del
> paquete. Respeta DESIGN.md. La API corre en modo demo, así que todo el flujo funciona desde ya.

## Paso 5 · Hitos
**Hito 1:** COBOL → Java de punta a punta con 100% de equivalencia (oráculo A).
**Hito 2 (prueba de agnosticismo):** solo agregando packs `plsql` (origen, runner Oracle Free) y
`typescript` (destino) — sin tocar el núcleo — PL/SQL → TypeScript pasa el 100%.
Si para el hito 2 hay que modificar el núcleo, es señal de que algo específico se coló: corregirlo.

## Paso 6 · Asegurar la demo en cualquier máquina
- `docker compose build` y `.\scripts\export-demo.ps1` → `agentcs-demo.tar` en una USB.
- Probar en un segundo computador: `docker load -i agentcs-demo.tar` + `docker compose up`.
- Alternativa sin instalar nada: subir el repo a GitHub y abrirlo en Codespaces.
- Respaldo final: video pregrabado + modo replay.
