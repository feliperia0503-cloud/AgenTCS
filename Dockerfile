# AgenTCS — imagen única: desarrollo, verificación y demo.
# Etapa 1 compila la interfaz (AgenTCS, React + Vite). Etapa 2 contiene la API (FastAPI), el núcleo
# agnóstico y los runtimes de ORIGEN (ejecutar el legacy, oráculo nivel A) y de DESTINO
# (compilar/probar el código generado). En el computador solo se necesita Docker.
#   Origen:  GnuCOBOL (COBOL) · Mono (C#/.NET Framework) · JDK (Java legacy) · PL/SQL -> servicio 'oracle' en compose
#   Destino: JDK 21 + Maven (Java) · Node + npm (TypeScript) · .NET 8 SDK (C#) · Python 3 (Python)

# ---------------------------------------------------------------- etapa 1: interfaz
FROM node:22-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

# ---------------------------------------------------------------- etapa 2: API + runtimes
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    AGENTCS_OUTPUT=/app/output

RUN apt-get update && apt-get install -y --no-install-recommends \
        gnucobol mono-mcs \
        openjdk-21-jdk-headless maven \
        nodejs npm \
        dotnet-sdk-8.0 \
        python3 python3-venv git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# uv para gestionar Python rápido
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# gitleaks (detección de secretos)
ARG GITLEAKS_VERSION=8.21.2
RUN curl -sSL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
    | tar -xz -C /usr/local/bin gitleaks

# Dependencias de Python (capa cacheada)
WORKDIR /app
COPY requirements.txt .
RUN uv venv /opt/venv && uv pip install --no-cache -r requirements.txt

# TypeScript global para los proyectos destino Node
RUN npm install -g typescript

# Código del proyecto + interfaz compilada
COPY . .
COPY --from=ui /ui/dist /app/ui/dist

# Pre-descarga de dependencias de las plantillas de destino (si existen) para compilar el
# código generado SIN internet durante la demo.
RUN if [ -f copilot/languages/java/templates/pom.xml ]; then \
      mvn -q -f copilot/languages/java/templates/pom.xml dependency:go-offline; fi \
 && if [ -f copilot/languages/typescript/templates/package.json ]; then \
      cd copilot/languages/typescript/templates && npm ci; fi \
 && if ls copilot/languages/csharp/templates/*.sln >/dev/null 2>&1; then \
      dotnet restore copilot/languages/csharp/templates; fi

EXPOSE 8000
CMD ["uvicorn", "copilot.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
