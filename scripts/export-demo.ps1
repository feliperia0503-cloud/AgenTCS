# Empaqueta la imagen para llevar la demo a OTRA máquina sin internet ni build.
# En la máquina de desarrollo:
#   docker compose build
#   .\scripts\export-demo.ps1        -> crea agentcs-demo.tar (copiar a USB junto con la carpeta del proyecto)
# En la máquina de demo (solo necesita Docker Desktop):
#   docker load -i agentcs-demo.tar
#   docker compose up            (sin --build)
#   abrir http://localhost:8000

docker save -o agentcs-demo.tar agentcs/copilot:latest
Write-Host "Imagen exportada a agentcs-demo.tar" -ForegroundColor Green
