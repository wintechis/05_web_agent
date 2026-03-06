import os
from typing import Any

from dotenv import load_dotenv
from smolagents import OpenAIModel
import httpx

from agent.context_compression import ContextCompressionModelWrapper, is_context_compression_enabled

load_dotenv()


#################################################################
# Inference Model (OpenAI API or local Transformers)
#################################################################
INFERENCE_BACKEND_ENV = "INFERENCE_BACKEND"
INFERENCE_BACKEND_OPENAI = "openai"
INFERENCE_BACKEND_TRANSFORMERS = "transformers"


def _is_transformers_backend() -> bool:
    raw = (os.getenv(INFERENCE_BACKEND_ENV) or INFERENCE_BACKEND_OPENAI).strip().lower()
    return raw == INFERENCE_BACKEND_TRANSFORMERS


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
def _normalized_base_url() -> str | None:
    raw = os.getenv("OPENAI_BASE_URL")
    return raw.strip().rstrip("/") if raw else None


OPENAI_BASE_URL = _normalized_base_url()

# Used when OPENAI_MODEL_ID is not set (e.g. .env fallback)
DEFAULT_MODEL_ID = (os.getenv("OPENAI_MODEL_ID") or "").strip() or None


def _model_kwargs_from_env() -> dict:
    """Build kwargs for OpenAIModel from env (temperature, top_p, seed for determinism)."""
    kwargs: dict = {}
    if (t := os.getenv("OPENAI_TEMPERATURE")) is not None and t != "":
        try:
            kwargs["temperature"] = float(t)
        except ValueError:
            pass
    if (p := os.getenv("OPENAI_TOP_P")) is not None and p != "":
        try:
            kwargs["top_p"] = float(p)
        except ValueError:
            pass
    if (s := os.getenv("OPENAI_SEED")) is not None and s != "":
        try:
            kwargs["seed"] = int(s)
        except ValueError:
            pass
    return kwargs


_LLM_TIMEOUT_ENV = "OPENAI_TIMEOUT"
_LLM_TIMEOUT_DEFAULT = 120.0  # seconds; prevents indefinite hangs on slow API responses



def _llm_timeout() -> float:
    raw = os.getenv(_LLM_TIMEOUT_ENV, "").strip()
    try:
        return float(raw) if raw else _LLM_TIMEOUT_DEFAULT
    except ValueError:
        return _LLM_TIMEOUT_DEFAULT


def _build_openai_model(model_id: str) -> Any:
    """Build OpenAIModel (with optional ContextCompression wrapper) for the given model_id."""
    base = OpenAIModel(
        model_id = model_id.strip(),
        api_key=OPENAI_API_KEY,
        api_base=OPENAI_BASE_URL,
        client_kwargs={"timeout": _llm_timeout()},
        **_model_kwargs_from_env(),
    )
    return (
        ContextCompressionModelWrapper(base)
        if is_context_compression_enabled()
        else base
    )


_openai_model_cache: dict[str, Any] = {}


def get_openai_inference_model() -> Any:
    """Return the inference model for the current backend and OPENAI_MODEL_ID (cached per model_id).

    When INFERENCE_BACKEND=transformers, delegates to get_transformers_inference_model() so
    the same entry point works for API and local inference. Otherwise builds OpenAIModel.
    """
    if _is_transformers_backend():
        from agent.clients_transformers import get_transformers_inference_model
        return get_transformers_inference_model()
    model_id = (os.getenv("OPENAI_MODEL_ID") or DEFAULT_MODEL_ID or "").strip()
    if not model_id:
        raise ValueError("OPENAI_MODEL_ID is not set; set it in .env or via Hydra model config.")
    if model_id not in _openai_model_cache:
        _openai_model_cache[model_id] = _build_openai_model(model_id)
    return _openai_model_cache[model_id]


# Default at import time (from .env); use get_openai_inference_model() when OPENAI_MODEL_ID
# or INFERENCE_BACKEND may be set later (e.g. by Hydra) so the correct model is used.
# When backend is transformers we do not build at import time to avoid loading torch.
openai_inference_model = (
    _build_openai_model(DEFAULT_MODEL_ID) if (DEFAULT_MODEL_ID and not _is_transformers_backend()) else None
)


#################################################################
# HTTP Client
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
