"""Memoria de lecciones: el "aprendizaje" entre ejecuciones sin reentrenar el modelo.

Cuando un intento corrige un fallo, el agente de Aprendizaje redacta una lección corta y generalizable
para el par origen→destino. Las lecciones relevantes se inyectan como contexto en futuras generaciones.
"""
from __future__ import annotations

import json
import re
import threading
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from copilot.contracts import Phase
from copilot.security import Sanitizer

from .llm import LLMClient, LLMError, complete_json
from .prompts import LESSON_SYSTEM

MAX_LESSON_CHARS = 400


class Lesson(BaseModel):
    pair: str                       # "cobol→java"
    text: str
    tags: list[str] = []
    uses: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LessonResponse(BaseModel):
    lesson: str
    tags: list[str] = []


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


class LessonStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> list[Lesson]:
        if not self.path.is_file():
            return []
        return [Lesson.model_validate(x) for x in json.loads(self.path.read_text(encoding="utf-8"))]

    def _save(self, lessons: list[Lesson]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([lesson.model_dump(mode="json") for lesson in lessons],
                                        indent=2, ensure_ascii=False), encoding="utf-8")

    def add(self, pair: str, text: str, tags: list[str]) -> bool:
        text = text.strip()[:MAX_LESSON_CHARS]
        if not text:
            return False
        clean, _ = Sanitizer().sanitize_text("lesson", text)
        with self._lock:
            lessons = self._load()
            if any(lesson.pair == pair and _norm(lesson.text) == _norm(clean) for lesson in lessons):
                return False
            lessons.append(Lesson(pair=pair, text=clean, tags=sorted({t.lower() for t in tags})))
            self._save(lessons)
        return True

    def relevant(self, pair: str, tags: list[str] | None = None, k: int = 5) -> list[str]:
        wanted = {t.lower() for t in tags or []}
        same = [lesson for lesson in self._load() if lesson.pair == pair]
        same.sort(key=lambda lesson: (len(wanted & set(lesson.tags)), lesson.created_at), reverse=True)
        return [lesson.text for lesson in same[:k]]

    def all(self) -> list[Lesson]:
        return self._load()


def learn(llm: LLMClient, store: LessonStore, pair: str, feedback: str, fix_summary: str) -> bool:
    prompt = (f"Par de lenguajes: {pair}\n\nFallo detectado por las pruebas:\n{feedback[:4000]}\n\n"
              f"Cambio que lo corrigió:\n{fix_summary[:4000]}")
    try:
        resp = complete_json(llm, LESSON_SYSTEM, prompt, LessonResponse, agent="lessons", phase=Phase.GENERACION)
    except LLMError:
        return False   # aprender es opcional: nunca bloquea la migración
    return store.add(pair, resp.lesson, resp.tags)
