"""Punto de entrada de la UI (placeholder). El rol C lo reemplaza por el wizard de 8 fases."""
import shutil
import subprocess

import streamlit as st

st.set_page_config(page_title="AgenTCS · Copiloto de Modernización", layout="wide")
st.title("AgenTCS · Copiloto de Modernización Legacy")
st.caption("Contenedor listo. Verificación de herramientas:")


def version(cmd: list[str]) -> str:
    if shutil.which(cmd[0]) is None:
        return "NO ENCONTRADO"
    out = subprocess.run(cmd, capture_output=True, text=True)
    return (out.stdout or out.stderr).strip().splitlines()[0]


st.subheader("Runtimes de origen (legacy)")
for name, cmd in {
    "GnuCOBOL (COBOL)": ["cobc", "--version"],
    "Mono (C# .NET Framework)": ["mcs", "--version"],
    "JDK (Java legacy)": ["java", "-version"],
}.items():
    st.write(f"**{name}:** {version(cmd)}")
st.caption("PL/SQL: servicio 'oracle' (docker compose --profile oracle up)")

st.subheader("Runtimes de destino y seguridad")
for name, cmd in {
    "Java 21 + Maven": ["mvn", "-v"],
    "Node (TypeScript)": ["node", "--version"],
    ".NET 8 (C#)": ["dotnet", "--version"],
    "Python": ["python", "--version"],
    "gitleaks": ["gitleaks", "version"],
    "Semgrep": ["semgrep", "--version"],
}.items():
    st.write(f"**{name}:** {version(cmd)}")
