import os
from typing import Any

from dotenv import load_dotenv
from smolagents import OpenAIModel
import httpx

from agent.context_compression import ContextCompressionModelWrapper, is_context_compression_enabled

load_dotenv()


#################################################################
# OpenAI Inference Model
#################################################################
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")

# Used when OPENAI_MODEL_ID is not set (e.g. .env fallback)
DEFAULT_MODEL_ID = os.getenv("OPENAI_MODEL_ID")


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


def _build_openai_model(model_id: str) -> Any:
    """Build OpenAIModel (with optional ContextCompression wrapper) for the given model_id."""
    base = OpenAIModel(
        model_id=model_id,
        api_key=OPENAI_API_KEY,
        api_base=OPENAI_BASE_URL,
        **_model_kwargs_from_env(),
    )
    return (
        ContextCompressionModelWrapper(base)
        if is_context_compression_enabled()
        else base
    )


_openai_model_cache: dict[str, Any] = {}


def get_openai_inference_model() -> Any:
    """Return the inference model for the current OPENAI_MODEL_ID (cached per model_id)."""
    model_id = os.getenv("OPENAI_MODEL_ID") or DEFAULT_MODEL_ID or ""
    if not model_id:
        raise ValueError("OPENAI_MODEL_ID is not set; set it in .env or via Hydra model config.")
    if model_id not in _openai_model_cache:
        _openai_model_cache[model_id] = _build_openai_model(model_id)
    return _openai_model_cache[model_id]


# Default at import time (from .env); use get_openai_inference_model() when OPENAI_MODEL_ID
# may be set later (e.g. by Hydra) so the correct model is used.
openai_inference_model = (
    _build_openai_model(DEFAULT_MODEL_ID) if DEFAULT_MODEL_ID else None
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
