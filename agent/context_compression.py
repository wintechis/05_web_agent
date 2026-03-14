"""Context compression: pluggable strategies for trimming tool-response messages."""
import copy
import logging
import os
import re

logger = logging.getLogger(__name__)

ENV_CONTEXT_COMPRESSION = "CONTEXT_COMPRESSION"
ENV_MAX_TOKEN_FOR_MODEL = "MAX_TOKEN_FOR_MODEL"
ENV_COMPRESSION_STRATEGY = "COMPRESSION_STRATEGY"
ENV_KEEP_FULL_LAST_N = "COMPRESSION_KEEP_FULL_LAST_N"

DEFAULT_MAX_TOKEN_FOR_MODEL = 120000
DEFAULT_COMPRESSION_STRATEGY = "truncate"
DEFAULT_KEEP_FULL_LAST_N = 2
COMPRESSION_THRESHOLD_RATIO = 0.8
TOOL_CONTENT_MAX_CHARS = 500
TOOL_CONTENT_SUFFIX = " ..."

# Matches DBpedia resource and Wikipedia article URIs embedded in any content format.
_URI_RE = re.compile(
    r"https?://(?:dbpedia\.org/resource|en\.wikipedia\.org/wiki)/[^\s\)\]>,'\"<]+"
)

# Sentinel used by _TIERED_LIMITS to mean "keep full, no truncation".
_FULL = object()

# Tiered limits by rank (0 = most recent tool response):
#   rank < max_rank → apply chars (_FULL = keep full, int = truncate to N chars)
#   rank >= all max_ranks → URI-extract
_TIERED_LIMITS = [
    (1, _FULL),  # rank 0: most recent — keep full
    (2, 2000),   # rank 1: 2nd most recent — 2 000 chars
    (3, 500),    # rank 2: 3rd most recent — 500 chars (current default)
    # rank >= 3: URI extract
]


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def get_max_token_for_model() -> int:
    val = os.environ.get(ENV_MAX_TOKEN_FOR_MODEL, str(DEFAULT_MAX_TOKEN_FOR_MODEL)).strip()
    try:
        return max(1, int(val))
    except ValueError:
        return DEFAULT_MAX_TOKEN_FOR_MODEL


def is_context_compression_enabled() -> bool:
    val = os.environ.get(ENV_CONTEXT_COMPRESSION, "").strip()
    return val.lower() in ("true", "1", "yes") or val == "True"


def get_compression_strategy() -> str:
    return os.environ.get(ENV_COMPRESSION_STRATEGY, DEFAULT_COMPRESSION_STRATEGY).strip().lower()


def get_keep_full_last_n() -> int:
    raw = os.environ.get(ENV_KEEP_FULL_LAST_N, "").strip()
    try:
        return max(0, int(raw))
    except (ValueError, TypeError):
        return DEFAULT_KEEP_FULL_LAST_N


def estimate_tokens(messages) -> int:
    return len(str(messages).split()) * 3


# ---------------------------------------------------------------------------
# Low-level message helpers
# ---------------------------------------------------------------------------

def _role(m) -> str:
    return m.get("role", "") if isinstance(m, dict) else getattr(m, "role", "")


def _is_tool_response(m) -> bool:
    """True if message is a tool result (smolagents 'tool-response' or pi_ai 'toolResult')."""
    return _role(m) in ("tool-response", "toolResult")


def _content(m):
    return m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")


def _set_content(m, c) -> None:
    if isinstance(m, dict):
        m["content"] = c
    elif hasattr(m, "content"):
        m.content = c


def _content_as_text(content) -> str:
    """Flatten content (str or list of typed parts) to a single string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            p.get("text", "") for p in content
            if isinstance(p, dict) and p.get("type") == "text"
        )
    return str(content)


def _truncate_content(content, max_chars: int):
    """Truncate content to max_chars, preserving list structure."""
    if isinstance(content, str):
        return content[:max_chars] + TOOL_CONTENT_SUFFIX if len(content) > max_chars else content
    if isinstance(content, list):
        return [
            (
                {**p, "text": p["text"][:max_chars] + TOOL_CONTENT_SUFFIX}
                if isinstance(p, dict) and p.get("type") == "text" and len(p.get("text", "")) > max_chars
                else copy.deepcopy(p)
            )
            for p in content
        ]
    return content


def _uri_extract_content(content) -> str:
    """Replace content with a compact list of navigation URIs found in it.
    Falls back to truncation when no recognised URIs are present."""
    text = _content_as_text(content)
    uris = sorted(set(_URI_RE.findall(text)))
    if not uris:
        return _truncate_content(text, TOOL_CONTENT_MAX_CHARS)
    return "URIs: " + " | ".join(uris)


# ---------------------------------------------------------------------------
# Compression strategies
# ---------------------------------------------------------------------------

def _compress_truncate(messages: list) -> list:
    """Original strategy: truncate every tool response to TOOL_CONTENT_MAX_CHARS."""
    r = []
    for m in messages[:-1]:
        if _is_tool_response(m):
            lim = copy.deepcopy(m)
            _set_content(lim, _truncate_content(_content(lim), TOOL_CONTENT_MAX_CHARS))
            r.append(lim)
        else:
            r.append(copy.deepcopy(m))
    r.append(copy.deepcopy(messages[-1]))
    return r


def _compress_recency_uri(messages: list, keep_full_last_n: int) -> list:
    """Keep the last N tool responses verbatim; replace older ones with URI lists.

    Rationale: the agent needs full detail about the current page and recent
    hops; for older visited pages only the reachable URIs matter (avoid cycles,
    avoid re-fetching).
    """
    tool_indices = [
        i for i, m in enumerate(messages[:-1]) if _is_tool_response(m)
    ]
    keep_set = set(tool_indices[-keep_full_last_n:]) if keep_full_last_n > 0 else set()
    r = []
    for i, m in enumerate(messages[:-1]):
        if not _is_tool_response(m):
            r.append(copy.deepcopy(m))
        elif i in keep_set:
            r.append(copy.deepcopy(m))
        else:
            compressed = copy.deepcopy(m)
            _set_content(compressed, _uri_extract_content(_content(compressed)))
            r.append(compressed)
    r.append(copy.deepcopy(messages[-1]))
    return r


def _compress_tiered(messages: list) -> list:
    """Gradient compression based on recency: full → 2 000 → 500 → URI-extract.

    Ranks tool responses from 0 (most recent) upward, then applies the limit
    defined in _TIERED_LIMITS. Older responses that fall beyond all tiers get
    URI-extract.
    """
    tool_indices = [
        i for i, m in enumerate(messages[:-1]) if _is_tool_response(m)
    ]
    # rank 0 = most recent
    rank_of = {idx: len(tool_indices) - 1 - pos for pos, idx in enumerate(tool_indices)}
    r = []
    for i, m in enumerate(messages[:-1]):
        if not _is_tool_response(m):
            r.append(copy.deepcopy(m))
            continue
        rank = rank_of.get(i, 0)
        compressed = copy.deepcopy(m)
        limit = None  # sentinel: no matching tier → URI extract
        for max_rank, chars in _TIERED_LIMITS:
            if rank < max_rank:
                limit = chars
                break
        if limit is _FULL:
            r.append(compressed)
        elif limit is not None:
            _set_content(compressed, _truncate_content(_content(compressed), limit))
            r.append(compressed)
        else:
            _set_content(compressed, _uri_extract_content(_content(compressed)))
            r.append(compressed)
    r.append(copy.deepcopy(messages[-1]))
    return r


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compress_messages(messages: list) -> list:
    """Dispatch to the configured compression strategy."""
    if not messages:
        return []
    strategy = get_compression_strategy()
    if strategy == "recency_uri":
        return _compress_recency_uri(messages, get_keep_full_last_n())
    if strategy == "tiered":
        return _compress_tiered(messages)
    return _compress_truncate(messages)


def should_compress_messages(messages) -> bool:
    if not is_context_compression_enabled():
        return False
    return estimate_tokens(messages) > int(COMPRESSION_THRESHOLD_RATIO * get_max_token_for_model())


class ContextCompressionModelWrapper:
    def __init__(self, model):
        self._model = model

    def generate(self, messages, *a, **kw):
        if should_compress_messages(messages):
            strategy = get_compression_strategy()
            print(
                f"Compressing messages [{strategy}]. "
                f"Estimated tokens: {estimate_tokens(messages)}, "
                f"Max tokens: {get_max_token_for_model()}"
            )
            messages = compress_messages(messages)
            print(f"Messages compressed. Estimated tokens: {estimate_tokens(messages)}")
            logger.debug("Context compressed [%s]; tokens ~%s", strategy, estimate_tokens(messages))
        else:
            print(
                f"Not compressing messages. "
                f"Estimated tokens: {estimate_tokens(messages)}, "
                f"Max tokens: {get_max_token_for_model()}"
            )
        return self._model.generate(messages, *a, **kw)

    def __getattr__(self, name):
        return getattr(self._model, name)
