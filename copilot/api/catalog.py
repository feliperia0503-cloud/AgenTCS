"""Catálogo único de destinos (lenguaje → frameworks) y arquitecturas. Lo consumen la UI
(/api/catalog), la sugerencia con IA y el motor. Las claves de lenguaje son ids de packs de destino."""
from __future__ import annotations

from copilot.languages.registry import get_target

LANGUAGES: dict[str, dict] = {
    "java": {"label": "Java 21", "frameworks": {
        "spring": "Spring Boot 3", "quarkus": "Quarkus 3", "micronaut": "Micronaut 4", "none": "Sin framework (núcleo puro)"}},
    "csharp": {"label": "C# 12 (.NET 8)", "frameworks": {
        "aspnet": "ASP.NET Core", "worker": ".NET Worker Service", "none": "Sin framework (núcleo puro)"}},
    "typescript": {"label": "TypeScript 5 (Node.js)", "frameworks": {
        "nestjs": "NestJS", "fastify": "Fastify", "express": "Express", "none": "Sin framework (núcleo puro)"}},
    "python": {"label": "Python 3.12", "frameworks": {
        "fastapi": "FastAPI", "flask": "Flask", "none": "Sin framework (núcleo puro)"}},
}
ARCHITECTURES: dict[str, str] = {
    "hexagonal": "Arquitectura hexagonal", "clean": "Clean Architecture", "modular": "Monolito modular",
    "microservices": "Microservicios", "event-driven": "Orientada a eventos",
}


def is_valid(language: str, framework: str, architecture: str) -> str | None:
    """None si la combinación es válida; si no, el motivo."""
    if language not in LANGUAGES:
        return f"lenguaje debe ser uno de {list(LANGUAGES)}"
    if framework not in LANGUAGES[language]["frameworks"]:
        return f"framework para {language} debe ser uno de {list(LANGUAGES[language]['frameworks'])}"
    if architecture not in ARCHITECTURES:
        return f"arquitectura debe ser una de {list(ARCHITECTURES)}"
    return None


def catalog() -> dict:
    languages = []
    for lang_id, data in LANGUAGES.items():
        missing = get_target(lang_id).missing_tools()
        languages.append({"id": lang_id, "label": data["label"], "available": not missing, "missing_tools": missing,
                          "frameworks": [{"id": k, "label": v} for k, v in data["frameworks"].items()]})
    return {"languages": languages, "architectures": [{"id": k, "label": v} for k, v in ARCHITECTURES.items()]}


def compact() -> dict:
    """Versión para prompts: {lenguaje: [frameworks]} y arquitecturas."""
    return {"lenguajes": {k: list(v["frameworks"]) for k, v in LANGUAGES.items()},
            "arquitecturas": list(ARCHITECTURES)}
