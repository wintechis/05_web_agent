"""URI handling for CRN: expand prefixed URIs, resolve relative, equality, local name (spec Section 9)."""

import re
from urllib.parse import urljoin, quote

# Regex: optional angle brackets around absolute URI.
_ANGLE_URI_RE = re.compile(r"^<([^>]+)>$")
# Prefix ref: prefix:local (local may contain alphanumeric, -, _, ., ~, (, ) per spec 9.2).
_PREFIX_REF_RE = re.compile(r"^([a-zA-Z0-9]+):(.+)$")


def expand_uri(uri_ref: str, prefixes: dict[str, str]) -> str:
    """Expand uri_ref to absolute URI using prefixes.

    - If uri_ref is <http://...>, return the inner URI.
    - If uri_ref is prefix:local, return prefixes[prefix] + local (percent-encode if needed).
    - Otherwise return uri_ref as-is (caller must ensure it is absolute).
    """
    uri_ref = uri_ref.strip()
    angle = _ANGLE_URI_RE.match(uri_ref)
    if angle:
        return angle.group(1)
    pre = _PREFIX_REF_RE.match(uri_ref)
    if pre:
        prefix_name, local = pre.group(1), pre.group(2)
        base = prefixes.get(prefix_name)
        if base is None:
            return uri_ref
        base = base.rstrip("/")
        # Spec 9.2: local may contain alphanumeric, -, _, ., ~, (, ). Others percent-encode.
        local_encoded = quote(local, safe="-_.~()")
        if base.endswith("#"):
            return f"{base}{local_encoded}"
        return f"{base}/{local_encoded}"
    return uri_ref


def resolve_relative(relative_uri: str, base_uri: str) -> str:
    """Resolve relative_uri against base_uri (spec 9.1). Returns absolute URI."""
    return urljoin(base_uri, relative_uri)


def uri_equals(uri_ref_a: str, uri_ref_b: str, prefixes: dict[str, str]) -> bool:
    """True iff expanded forms of uri_ref_a and uri_ref_b are identical (spec 9.4)."""
    return expand_uri(uri_ref_a, prefixes) == expand_uri(uri_ref_b, prefixes)


def local_name_from_uri(uri: str) -> str:
    """Derive a local name for label: fragment or last path segment, underscores to spaces."""
    uri = uri.strip()
    if "#" in uri:
        local = uri.split("#")[-1]
    else:
        local = uri.rstrip("/").split("/")[-1]
    return local.replace("_", " ")


def is_prefixed_ref(uri_ref: str) -> bool:
    """True if uri_ref looks like prefix:local (and not <...>)."""
    uri_ref = uri_ref.strip()
    if _ANGLE_URI_RE.match(uri_ref):
        return False
    return _PREFIX_REF_RE.match(uri_ref) is not None


def is_full_uri(uri_ref: str) -> bool:
    """True if uri_ref is <http://...>."""
    return _ANGLE_URI_RE.match(uri_ref.strip()) is not None
