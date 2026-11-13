"""Cliente LLM del motor: Anthropic, caché/replay por hash y salidas JSON validadas con Pydantic.

Nada de fine-tuning: el modelo no se reentrena. El motor "aprende" con el bucle de
retroalimentación de pruebas (loop.py) y la memoria de lecciones (lessons.py). Ver ADR-005.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ValidationError

from copilot.contracts import LLMCall, Phase

DEFAULT_MODEL = "claude-sonnet-5-5"
T = TypeVar("T", bound=BaseModel)
CallRecorder = Callable[[LLMCall], None]


class LLMError(Exception):
    """Error del LLM con acción sugerida para el usuario (sin contenido sensible)."""

    def __init__(self, code: str, message: str, action: str):
        super().__init__(message)
        self.code, self.message, self.action = code, message, action


@runtime_checkable
class LLMClient(Protocol):
    model: str
    tokens_used: int
    recorder: CallRecorder | None

    def complete(self, system: str, prompt: str, *, agent: str, phase: Phase) -> str: ...


def prompt_hash(model: str, system: str, prompt: str) -> str:
    return hashlib.sha256(f"{model}\x00{system}\x00{prompt}".encode()).hexdigest()


class AnthropicLLM:
    """Claude vía SDK oficial. Lee primero la caché en disco; con replay=True SOLO usa la caché."""

    def __init__(self, model: str | None = None, *, cache_dir: Path | None = None,
                 replay: bool | None = None, max_tokens: int | None = None,
                 client: Any = None, recorder: CallRecorder | None = None):
        self.model = model or os.environ.get("AGENTCS_MODEL", DEFAULT_MODEL)
        self.cache_dir = cache_dir or Path(os.environ.get("AGENTCS_OUTPUT", "output")) / "llm_cache"
        self.replay = os.environ.get("AGENTCS_LLM_REPLAY") == "1" if replay is None else replay
        # Paquetes legacy grandes producen proyectos destino largos: 32k tokens de salida por defecto, con streaming.
        self.max_tokens = max_tokens or int(os.environ.get("AGENTCS_MAX_TOKENS", "32000"))
        self.recorder = recorder
        self.tokens_used = 0
        self._client = client

    def complete(self, system: str, prompt: str, *, agent: str, phase: Phase) -> str:
        key = prompt_hash(self.model, system, prompt)
        cached = self.cache_dir / f"{key}.json"
        if cached.is_file():
            data = json.loads(cached.read_text(encoding="utf-8"))
            self._record(phase, agent, key, 0, 0, 0.0, replayed=True)
            return data["text"]
        if self.replay:
            raise LLMError("REPLAY_MISS", "Modo replay activo y no hay respuesta en caché para esta solicitud.",
                           "Ejecuta una vez con conexión y ANTHROPIC_API_KEY para poblar output/llm_cache.")
        start = time.monotonic()
        try:
            response = self._request(system, prompt)
        except Exception as exc:
            error_name = type(exc).__name__
            if error_name == "APITimeoutError":
                raise LLMError("PROVIDER_TIMEOUT", "El proveedor no respondió dentro del tiempo límite.",
                               "Reintenta o activa el modo demo/replay para continuar sin depender de la red.") from exc
            if error_name == "APIConnectionError":
                raise LLMError("PROVIDER_CONNECTION", "No fue posible conectar con el proveedor del modelo.",
                               "Verifica red y certificados; para la demo usa el modo precomputado.") from exc
            if error_name == "AuthenticationError":
                raise LLMError("PROVIDER_AUTH", "El proveedor rechazó la autenticación.",
                               "Verifica ANTHROPIC_API_KEY sin copiarla en registros ni documentos.") from exc
            if error_name == "RateLimitError":
                raise LLMError("PROVIDER_RATE_LIMIT", "El proveedor limitó temporalmente las solicitudes.",
                               "Espera y reintenta, o usa el modo demo/replay.") from exc
            raise
        text = "".join(getattr(b, "text", "") for b in response.content)
        if getattr(response, "stop_reason", None) == "max_tokens":
            raise LLMError("OUTPUT_TRUNCATED", f"La respuesta superó el límite de {self.max_tokens} tokens y quedó cortada.",
                           "Pide archivos más compactos o sube AGENTCS_MAX_TOKENS.")
        usage = getattr(response, "usage", None)
        tin, tout = getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps({"model": self.model, "agent": agent, "text": text}, ensure_ascii=False),
                          encoding="utf-8")
        self._record(phase, agent, key, tin, tout, time.monotonic() - start, replayed=False)
        return text

    def _sdk(self) -> Any:
        if self._client is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise LLMError("NO_API_KEY", "No hay ANTHROPIC_API_KEY configurada.",
                               "Agrega la llave en .env o usa AGENTCS_LLM_REPLAY=1 con una caché existente.")
            import anthropic  # import diferido: las pruebas no lo necesitan
            timeout_s = max(10.0, float(os.environ.get("AGENTCS_LLM_TIMEOUT_S", "120")))
            max_retries = max(0, int(os.environ.get("AGENTCS_LLM_MAX_RETRIES", "1")))
            self._client = anthropic.Anthropic(timeout=timeout_s, max_retries=max_retries)
        return self._client

    def _request(self, system: str, prompt: str) -> Any:
        """Con streaming cuando el SDK lo ofrece: evita el corte por tiempo en respuestas largas."""
        messages = self._sdk().messages
        kwargs = {"model": self.model, "max_tokens": self.max_tokens, "system": system,
                  "messages": [{"role": "user", "content": prompt}]}
        if hasattr(messages, "stream"):
            with messages.stream(**kwargs) as stream:
                return stream.get_final_message()
        return messages.create(**kwargs)

    def _record(self, phase: Phase, agent: str, key: str, tin: int, tout: int, secs: float, *, replayed: bool) -> None:
        self.tokens_used += tin + tout
        if self.recorder:
            self.recorder(LLMCall(phase=phase, agent=agent, prompt_hash=key, model=self.model,
                                  input_tokens=tin, output_tokens=tout, duration_s=round(secs, 3), replayed=replayed))


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> str:
    """Toma el JSON de la respuesta aunque venga con texto o bloques ```json alrededor."""
    m = _FENCE.search(text)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("la respuesta no contiene un objeto JSON")
    return text[start:end + 1]


def complete_json(llm: LLMClient, system: str, prompt: str, model_cls: type[T], *,
                  agent: str, phase: Phase, retries: int = 2) -> T:
    """Pide JSON y lo valida; si falla, reintenta enviando el error de validación al modelo."""
    attempt_prompt, last_error = prompt, ""
    for _ in range(retries + 1):
        raw = llm.complete(system, attempt_prompt, agent=agent, phase=phase)
        try:
            return model_cls.model_validate_json(extract_json(raw))
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)[:2000]
            attempt_prompt = (f"{prompt}\n\n---\nTu respuesta anterior no cumplió el esquema. Error:\n{last_error}\n"
                              "Responde SOLO con el objeto JSON corregido.")
    raise LLMError("INVALID_LLM_OUTPUT", f"El modelo no produjo un JSON válido para '{agent}'.",
                   "Reintenta la fase; si persiste, revisa el prompt o reduce el tamaño del código enviado.")
