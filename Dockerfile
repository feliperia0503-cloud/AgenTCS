# AgenTCS — imagen única: desarrollo, verificación y demo.
# Agnóstica de lenguaje: runtimes de ORIGEN para ejecutar el legacy (oráculo nivel A) y de DESTINO
# para compilar/probar el código generado. En el computador solo se necesita Docker.
#   Origen:  GnuCOBOL (COBOL) · Mono (C#/.NET Framework) · JDK (Java legacy) · PL/SQL -> servicio 'oracle' en compose
#   Destino: JDK 21 + Maven (Java) · Node + npm (TypeScript) · .NET 8 SDK (C#) · Python 3 (Python)
# Para agregar un lenguaje: sumar su runtime aquí (o como servicio con profile si es pesado).
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

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

ENV DOTNET_CLI_TELEMETRY_OPTOUT=1

# Código del proyecto
COPY . .

# Pre-descarga de dependencias de las plantillas de destino (si existen) para compilar el
# código generado SIN internet durante la demo.
RUN if [ -f copilot/languages/java/templates/pom.xml ]; then \
      mvn -q -f copilot/languages/java/templates/pom.xml dependency:go-offline; fi \
 && if [ -f copilot/languages/typescript/templates/package.json ]; then \
      cd copilot/languages/typescript/templates && npm ci; fi \
 && if ls copilot/languages/csharp/templates/*.sln >/dev/null 2>&1; then \
      dotnet restore copilot/languages/csharp/templates; fi

EXPOSE 8501
CMD ["streamlit", "run", "ui/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
