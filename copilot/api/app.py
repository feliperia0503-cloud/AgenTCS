"""API HTTP del copiloto. Arranque: uvicorn copilot.api.app:app --port 8000

Sirve también la interfaz compilada (ui/dist) en el mismo origen cuando existe.
"""
from __future__ import annotations

from pathlib import Path

try:   # carga ANTHROPIC_API_KEY y demás variables desde .env al correr con uvicorn local
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from copilot.contracts import RunState

from .service import CopilotService, ServiceError

UI_DIST = Path(__file__).resolve().parents[2] / "ui" / "dist"

app = FastAPI(title="AgenTCS · Copiloto de Modernización", version="0.2.0")
service = CopilotService()


@app.exception_handler(ServiceError)
async def _service_error(_: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"detail": exc.as_dict()})


@app.exception_handler(Exception)
async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
    # Nunca exponer trazas ni contenido del usuario en la respuesta.
    return JSONResponse(status_code=500, content={"detail": {
        "code": "INTERNAL_ERROR", "message": "Ocurrió un error inesperado en el copiloto.",
        "action": "Reintenta. Si persiste, revisa los registros de la API."}})


class RuleDecision(BaseModel):
    action: str
    by: str
    comment: str | None = None
    changes: dict | None = None


class Approval(BaseModel):
    by: str


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "mode": service.mode.value}


@app.get("/api/languages")
def languages() -> dict:
    return service.languages()


@app.get("/api/catalog")
def catalog() -> dict:
    return service.catalog()


@app.post("/api/runs", response_model=RunState)
async def create_run(
    target_language: str = Form(...),
    target_framework: str | None = Form(None),
    target_architecture: str | None = Form(None),
    source_language: str | None = Form(None),
    domain: str | None = Form(None),
    repo_url: str | None = Form(None),
    branch: str | None = Form(None),
    demo: bool | None = Form(None),
    files: list[UploadFile] = File(default=[]),
) -> RunState:
    payload = [(f.filename or "archivo", await f.read()) for f in files]
    return service.create_run(payload, target_language, source_language, domain, demo, repo_url=repo_url,
                              branch=branch, framework=target_framework, architecture=target_architecture)


@app.post("/api/suggest")
async def suggest_target(
    repo_url: str | None = Form(None),
    branch: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
) -> dict:
    payload = [(f.filename or "archivo", await f.read()) for f in files]
    return service.suggest_target(payload, repo_url, branch)


@app.get("/api/runs/{run_id}", response_model=RunState)
def get_run(run_id: str) -> RunState:
    return service.get_run(run_id)


@app.post("/api/runs/{run_id}/rules/{rule_id}/decision", response_model=RunState)
def decide_rule(run_id: str, rule_id: str, body: RuleDecision) -> RunState:
    return service.decide_rule(run_id, rule_id, body.action, body.by, body.comment, body.changes)


@app.post("/api/runs/{run_id}/approve", response_model=RunState)
def approve(run_id: str, body: Approval) -> RunState:
    return service.approve_spec(run_id, body.by)


@app.get("/api/runs/{run_id}/verification")
def verification(run_id: str) -> dict:
    return service.verification(run_id)


@app.get("/api/runs/{run_id}/package")
def package(run_id: str) -> Response:
    data = service.package(run_id)
    return Response(content=data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="agentcs-{run_id}.zip"'})


# ---------------------------------------------------------------- interfaz (SPA)
if UI_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=UI_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        candidate = (UI_DIST / path).resolve()
        if path and candidate.is_file() and UI_DIST in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(UI_DIST / "index.html")
