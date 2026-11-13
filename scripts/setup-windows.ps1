# AgenTCS - lo ÚNICO que se instala en el computador de desarrollo.
# PowerShell como administrador:
#   Set-ExecutionPolicy -Scope Process Bypass; .\scripts\setup-windows.ps1
# Todo lo demás (GnuCOBOL, Java, Maven, Python, Semgrep, gitleaks, Claude Code) vive en el contenedor.

winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
winget install --id Docker.DockerDesktop -e --accept-source-agreements --accept-package-agreements
winget install --id Microsoft.VisualStudioCode -e --accept-source-agreements --accept-package-agreements
code --install-extension ms-vscode-remote.remote-containers

Write-Host "Listo. Reinicia, abre Docker Desktop y luego abre C:\AgenTCS en VS Code -> 'Reopen in Container'." -ForegroundColor Green
