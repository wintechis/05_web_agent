"""Context compression."""
import copy
import logging
import os

logger = logging.getLogger(__name__)
ENV_CONTEXT_COMPRESSION = "CONTEXT_COMPRESSION"
ENV_MAX_TOKEN_FOR_MODEL = "MAX_TOKEN_FOR_MODEL"
DEFAULT_MAX_TOKEN_FOR_MODEL = 120000
COMPRESSION_THRESHOLD_RATIO = 0.8
TOOL_CONTENT_MAX_CHARS = 500
TOOL_CONTENT_SUFFIX = " ..."

def get_max_token_for_model():
    val = os.environ.get(ENV_MAX_TOKEN_FOR_MODEL, str(DEFAULT_MAX_TOKEN_FOR_MODEL)).strip()
    try:
        return max(1, int(val))
    except ValueError:
        return DEFAULT_MAX_TOKEN_FOR_MODEL

def is_context_compression_enabled():
    val = os.environ.get(ENV_CONTEXT_COMPRESSION, "").strip()
    return val.lower() in ("true", "1", "yes") or val == "True"

def estimate_tokens(messages):
    return len(str(messages).split()) * 3

def _truncate(c):
    if isinstance(c, str):
        return c[:TOOL_CONTENT_MAX_CHARS] + TOOL_CONTENT_SUFFIX if len(c) > TOOL_CONTENT_MAX_CHARS else c
    if isinstance(c, list):
        return [({**p, "text": p["text"][:TOOL_CONTENT_MAX_CHARS] + TOOL_CONTENT_SUFFIX} if isinstance(p, dict) and p.get("type") == "text" and len(p.get("text", "")) > TOOL_CONTENT_MAX_CHARS else copy.deepcopy(p)) for p in c]
    return c

def _role(m): return m.get("role", "") if isinstance(m, dict) else getattr(m, "role", "")
def _content(m): return m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
def _set_content(m, c):
    if isinstance(m, dict): m["content"] = c
    elif hasattr(m, "content"): m.content = c
def compress_messages(messages):
    if not messages: return []
    r = []
    for m in messages[:-1]:
        if _role(m) == "tool-response":
            lim = copy.deepcopy(m)
            _set_content(lim, _truncate(_content(lim)))
            r.append(lim)
        else: r.append(copy.deepcopy(m))
    r.append(copy.deepcopy(messages[-1]))
    return r

def should_compress_messages(messages):
    if not is_context_compression_enabled():
        return False
    if estimate_tokens(messages) <= int(COMPRESSION_THRESHOLD_RATIO * get_max_token_for_model()):
        return False
    return True


class ContextCompressionModelWrapper:
    def __init__(self, model): 
        self._model = model
    def generate(self, messages, *a, **kw):
        if should_compress_messages(messages):
            print(f"Compressing messages. Estimated tokens: {estimate_tokens(messages)}, Max tokens: {get_max_token_for_model()}")
            messages = compress_messages(messages)
            print(f"Messages compressed. Estimated tokens: {estimate_tokens(messages)}")
            logger.debug("Context compressed; tokens ~%s", estimate_tokens(messages))
        else:
            print(f"Not compressing messages. Estimated tokens: {estimate_tokens(messages)}, Max tokens: {get_max_token_for_model()}")
        return self._model.generate(messages, *a, **kw)
    def __getattr__(self, name): return getattr(self._model, name)
