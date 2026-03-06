"""Transformers-based inference: local models via smolagents TransformersModel and env config."""
import os
from typing import Any

from dotenv import load_dotenv

from agent.context_compression import ContextCompressionModelWrapper, is_context_compression_enabled

load_dotenv()

# Lazy import so we do not load torch/transformers when backend is OpenAI.
TransformersModel: type[Any] | None = None

_TRANSFORMERS_IMPORT_ERROR: str = (
    "TransformersModel requires the optional dependency group 'transformers'. "
    "Install with: uv sync --group transformers"
)


def _get_transformers_model_class() -> type[Any]:
    """Lazy-import TransformersModel; raise a clear error if not installed."""
    global TransformersModel
    if TransformersModel is not None:
        return TransformersModel
    try:
        from smolagents import TransformersModel as _TM

        TransformersModel = _TM
        return TransformersModel
    except ImportError as e:
        raise ImportError(f"{_TRANSFORMERS_IMPORT_ERROR}\nOriginal error: {e}") from e


# Env keys for transformers backend (model id reused from OPENAI_MODEL_ID for Hydra compatibility)
ENV_HF_DEVICE = "HF_DEVICE"
ENV_HF_MAX_NEW_TOKENS = "HF_MAX_NEW_TOKENS"
ENV_TRUST_REMOTE_CODE = "TRUST_REMOTE_CODE"
ENV_HF_TORCH_DTYPE = "HF_TORCH_DTYPE"
DEFAULT_HF_MAX_NEW_TOKENS = 4096


def _transformers_model_kwargs_from_env() -> dict[str, Any]:
    """Build kwargs for TransformersModel from env (device, max_new_tokens, sampling, etc.)."""
    kwargs: dict[str, Any] = {}
    if (d := os.getenv(ENV_HF_DEVICE)) is not None and d.strip():
        kwargs["device"] = d.strip()
    if (n := os.getenv(ENV_HF_MAX_NEW_TOKENS)) is not None and n.strip():
        try:
            kwargs["max_new_tokens"] = max(1, int(n.strip()))
        except ValueError:
            kwargs["max_new_tokens"] = DEFAULT_HF_MAX_NEW_TOKENS
    else:
        kwargs["max_new_tokens"] = DEFAULT_HF_MAX_NEW_TOKENS
    if (r := os.getenv(ENV_TRUST_REMOTE_CODE)) is not None and r.strip().lower() in ("true", "1", "yes"):
        kwargs["trust_remote_code"] = True
    if (dt := os.getenv(ENV_HF_TORCH_DTYPE)) is not None and dt.strip():
        kwargs["torch_dtype"] = dt.strip()
    # Sampling (same env as OpenAI path for consistency)
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


_transformers_model_cache: dict[str, Any] = {}


def get_transformers_inference_model() -> Any:
    """Return the inference model for the current model id (cached per model_id).

    Model id is read from OPENAI_MODEL_ID (Hugging Face model id when backend is transformers)
    so Hydra and run_inference_hydra work without change.

    Raises:
        ValueError: If OPENAI_MODEL_ID is not set.
        ImportError: If smolagents[transformers] is not installed.
    """
    model_id = (os.getenv("OPENAI_MODEL_ID") or "").strip()
    if not model_id:
        raise ValueError(
            "OPENAI_MODEL_ID is not set; set it in .env or via Hydra model config (use a Hugging Face model id for transformers backend)."
        )
    if model_id not in _transformers_model_cache:
        _transformers_model_cache[model_id] = _build_transformers_model(model_id)
    return _transformers_model_cache[model_id]


def _build_transformers_model(model_id: str) -> Any:
    """Build TransformersModel (with optional ContextCompression wrapper) for the given model_id."""
    cls = _get_transformers_model_class()
    base = cls(model_id=model_id.strip(), **_transformers_model_kwargs_from_env())
    return (
        ContextCompressionModelWrapper(base)
        if is_context_compression_enabled()
        else base
    )
