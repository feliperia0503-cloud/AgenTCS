# ADR-002 · Entorno 100% contenerizado

- **Estado:** Propuesto
- **Fecha:** 2026-11-13

## Contexto
No sabemos en qué máquina será la demo. Instalar GnuCOBOL, JDK, Maven, Python y herramientas de
seguridad en el computador crea dependencia de esa máquina y riesgo el día de la presentación.
El reto exige ejecución reproducible con un solo comando en entorno contenerizado.

## Decisión
- Una sola imagen Docker con todo el stack (`Dockerfile`).
- Desarrollo dentro de esa misma imagen vía Dev Container (VS Code o GitHub Codespaces).
- Demo: `docker compose up`; para otra máquina, `docker save` → `docker load` (sin build ni internet).
- Dependencias Maven pre-descargadas en la imagen (`dependency:go-offline`).
- Modo replay del LLM (respuestas cacheadas) para operar sin internet ni API key.
- Herramientas pesadas (SonarQube) reemplazadas por plugins Maven (PMD, JaCoCo, ArchUnit).

## Alternativas
- Instalación local (WSL + paquetes): descartada por falta de portabilidad.
- Varios contenedores (uno por herramienta): más complejo sin beneficio para un prototipo.

## Consecuencias
- (+) Desarrollo = demo: "funciona en mi máquina" deja de ser un riesgo.
- (+) Cumple el entregable de "un solo comando".
- (−) Imagen grande (~1,5–2 GB); construirla y exportarla con anticipación.
