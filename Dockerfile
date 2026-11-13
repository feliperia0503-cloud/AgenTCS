# AgenTCS — imagen única: desarrollo, verificación y demo.
# Etapa 1 compila la interfaz (AgenTCS, React + Vite). Etapa 2 contiene la API (FastAPI), el núcleo
# agnóstico y los runtimes de ORIGEN (ejecutar el legacy, oráculo nivel A) y de DESTINO
# (compilar/probar el código generado). En el computador solo se necesita Docker.
#   Origen:  GnuCOBOL (COBOL) · Mono (C#/.NET Framework) · JDK (Java legacy) · PL/SQL -> servicio 'oracle' en compose
#   Destino: JDK 21 (Java) · Node 22 + TypeScript + decimal.js · .NET 8 SDK (C#) · Python 3
#   La verificación de cada destino compila el núcleo generado sin descargar dependencias.

# ---------------------------------------------------------------- etapa 1: interfaz
FROM node:22-slim AS ui
WORKDIR /ui
COPY docker/certs/*.crt /usr/local/share/ca-certificates/
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY ui/package.json ui/package-lock.json ./
RUN NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt npm ci --no-audit --no-fund \
    && rm -f /usr/local/share/ca-certificates/AZRGAIDROOTCA-CA.crt \
             /usr/local/share/ca-certificates/AI-AZRGAIDSUBCA1-CA-1.crt \
             /usr/local/share/ca-certificates/aiproxy.tcs.in.crt \
    && update-ca-certificates --fresh
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

COPY docker/certs/*.crt /usr/local/share/ca-certificates/
RUN apt-get update && apt-get install -y --no-install-recommends \
        gnucobol mono-mcs \
        openjdk-21-jdk-headless maven \
        dotnet-sdk-8.0 \
        python3 python3-venv git curl ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22 (destino TypeScript) desde la imagen oficial: misma versión que compila la UI
COPY --from=ui /usr/local/bin/node /usr/local/bin/node
COPY --from=ui /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# uv para gestionar Python rápido
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# gitleaks (detección de secretos)
ARG GITLEAKS_VERSION=8.21.2
RUN curl -sSL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
    | tar -xz -C /usr/local/bin gitleaks

# Dependencias de Python (capa cacheada)
WORKDIR /app
COPY requirements.txt .
RUN uv venv /opt/venv && UV_SYSTEM_CERTS=true uv pip install --no-cache -r requirements.txt

<<<<<<< Updated upstream
# TypeScript global para los proyectos destino Node
RUN NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt npm install -g typescript
=======
# Destino TypeScript: compilador y decimal.js globales (la verificación no descarga dependencias)
RUN npm install -g typescript@5 decimal.js@10
ENV NODE_PATH=/usr/local/lib/node_modules

# Precalienta .NET (primer uso y paquetes de referencia) para verificar C# sin red durante la demo
RUN dotnet new console -o /tmp/warm --no-restore >/dev/null && dotnet build /tmp/warm -v q >/dev/null && rm -rf /tmp/warm
>>>>>>> Stashed changes

# Código del proyecto + interfaz compilada
COPY . .
COPY --from=ui /ui/dist /app/ui/dist

# Pre-descarga de dependencias de las plantillas de destino (si existen) para compilar el
# código generado SIN internet durante la demo.
RUN if [ -f copilot/languages/java/templates/pom.xml ]; then \
      mvn -q -f copilot/languages/java/templates/pom.xml dependency:go-offline; fi \
 && if [ -f copilot/languages/typescript/templates/package.json ]; then \
      cd copilot/languages/typescript/templates \
      && NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt npm ci; fi \
 && if ls copilot/languages/csharp/templates/*.sln >/dev/null 2>&1; then \
      dotnet restore copilot/languages/csharp/templates; fi \
 && rm -f /usr/local/share/ca-certificates/AZRGAIDROOTCA-CA.crt \
          /usr/local/share/ca-certificates/AI-AZRGAIDSUBCA1-CA-1.crt \
          /usr/local/share/ca-certificates/aiproxy.tcs.in.crt \
 && rm -rf /app/docker/certs \
 && update-ca-certificates --fresh

ENV SEMGREP_ENABLE_VERSION_CHECK=0

EXPOSE 8000
CMD ["uvicorn", "copilot.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
