"""Local Hugging Face Transformers inference is not supported with pi-mono-python.

Previously this module provided smolagents TransformersModel for INFERENCE_BACKEND=transformers.
With the switch to pi-mono-python (pi_ai + pi_agent), only API-based inference is supported.
Use INFERENCE_BACKEND=openai and set OPENAI_MODEL_ID to your desired model.
"""


def get_transformers_inference_model():
    """Raise a clear error; local transformers backend is not supported."""
    raise ValueError(
        "Local Transformers inference (INFERENCE_BACKEND=transformers) is not supported "
        "with pi-mono-python. Use INFERENCE_BACKEND=openai and set OPENAI_MODEL_ID to an API model."
    )
