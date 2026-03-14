"""Model and HTTP client configuration for the web agent. Uses pi_ai for LLM inference."""

import os
from typing import Any

from dotenv import load_dotenv
import httpx

from pi_ai import get_model
from pi_ai.types import Model, ModelCost

load_dotenv()


#################################################################
# Inference Model (OpenAI API via pi_ai)
#################################################################
INFERENCE_BACKEND_ENV = "INFERENCE_BACKEND"
INFERENCE_BACKEND_OPENAI = "openai"
INFERENCE_BACKEND_TRANSFORMERS = "transformers"

# Local Hugging Face Transformers backend is not supported with pi-mono-python.
# Set INFERENCE_BACKEND=openai and use OPENAI_MODEL_ID with an API-based model.


def _is_transformers_backend() -> bool:
    raw = (os.getenv(INFERENCE_BACKEND_ENV) or INFERENCE_BACKEND_OPENAI).strip().lower()
    return raw == INFERENCE_BACKEND_TRANSFORMERS


def _normalized_base_url() -> str | None:
    raw = os.getenv("OPENAI_BASE_URL")
    return raw.strip().rstrip("/") if raw else None


OPENAI_BASE_URL = _normalized_base_url()

# Used when OPENAI_MODEL_ID is not set (e.g. .env fallback)
DEFAULT_MODEL_ID = (os.getenv("OPENAI_MODEL_ID") or "").strip() or None

# Default base URL for OpenAI when not overridden
_DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


def _build_pi_ai_model(model_id: str) -> Model:
    """Build a pi_ai Model for the given model_id. Uses registry if available, else constructs one."""
    model_id = model_id.strip()
    base_url = _normalized_base_url() or _DEFAULT_OPENAI_BASE_URL

    registered = get_model("openai", model_id)
    if registered is not None:
        if base_url and registered.base_url != base_url:
            return registered.model_copy(update={"base_url": base_url})
        return registered

    # Custom or unknown model ID: construct a Model for openai-completions API
    return Model(
        id=model_id,
        name=model_id,
        api="openai-completions",
        provider="openai",
        base_url=base_url,
        cost=ModelCost(),
    )


_model_cache: dict[tuple[str, str | None], Model] = {}


def get_openai_inference_model() -> Model:
    """Return the pi_ai Model for the current OPENAI_MODEL_ID (cached per model_id + base_url).

    When INFERENCE_BACKEND=transformers, raises ValueError; local transformers are not
    supported with pi-mono-python.
    """
    if _is_transformers_backend():
        raise ValueError(
            "INFERENCE_BACKEND=transformers is not supported with pi-mono-python. "
            "Use INFERENCE_BACKEND=openai and set OPENAI_MODEL_ID to an API model."
        )
    model_id = (os.getenv("OPENAI_MODEL_ID") or DEFAULT_MODEL_ID or "").strip()
    if not model_id:
        raise ValueError("OPENAI_MODEL_ID is not set; set it in .env or via Hydra model config.")
    cache_key = (model_id, _normalized_base_url())
    if cache_key not in _model_cache:
        _model_cache[cache_key] = _build_pi_ai_model(model_id)
    return _model_cache[cache_key]


# Lazy default: avoid building model at import time when OPENAI_MODEL_ID may not be set yet.
def _default_model_or_none() -> Model | None:
    if not DEFAULT_MODEL_ID or _is_transformers_backend():
        return None
    try:
        return get_openai_inference_model()
    except ValueError:
        return None


openai_inference_model: Model | None = _default_model_or_none()


#################################################################
# HTTP Client (for tools)
#################################################################
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36 "
    "WebAgent/1.0"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
}

http_client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20.0, http2=True)
