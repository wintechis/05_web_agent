"""Utilities for working with URIs."""

from __future__ import annotations

import html
import os
import re
import urllib.parse
from loguru import logger

from clients import http_client

def _generate_uri_variations(candidate_uri: str) -> list[str]:
    """Generate different variations of a URI for robust matching.

    Creates multiple representations to handle different encoding scenarios:
    - Original URI
    - Apostrophe percent-encoded (%27)
    - HTML entity encodings (&apos; and &#39;)
    - URL-encoded version using urllib.parse
    - Variants without query parameters and/or fragments

    Args:
        candidate_uri: The URI to generate variations for

    Returns:
        List of URI variations for matching
    """
    variations = [candidate_uri]

    if "'" in candidate_uri:
        variations.extend([
            candidate_uri.replace("'", "%27"),
            candidate_uri.replace("'", "&#39;"),
            candidate_uri.replace("'", "&apos;"),
        ])

    try:
        parsed = urllib.parse.urlsplit(candidate_uri)

        # URL-encoded version with all components
        path_enc = urllib.parse.quote(parsed.path, safe="/@:%")
        query_enc = urllib.parse.quote(parsed.query, safe="=&:%+?@,;/")
        frag_enc = urllib.parse.quote(parsed.fragment, safe="=&:%+?@,;/")

        uri_enc = urllib.parse.urlunsplit((
            parsed.scheme,
            parsed.netloc,
            path_enc,
            query_enc,
            frag_enc 
        ))

        if uri_enc and uri_enc not in variations:
            variations.append(uri_enc)

        # Variant without fragment (but keep query if present)
        if parsed.fragment:
            uri_no_frag = urllib.parse.urlunsplit((
                parsed.scheme,
                parsed.netloc,
                path_enc,
                query_enc,
                "",  # No fragment
            ))
            if uri_no_frag and uri_no_frag not in variations:
                variations.append(uri_no_frag)

        # Variant without query and fragment (base path only)
        if parsed.query or parsed.fragment:
            uri_base = urllib.parse.urlunsplit((
                parsed.scheme,
                parsed.netloc,
                path_enc,
                "",  # No query
                "",  # No fragment
            ))
            if uri_base and uri_base not in variations:
                variations.append(uri_base)

    except Exception:
        pass

    return [v for v in variations if v]


def _check_raw_bytes(content: bytes, needles: list[bytes]) -> bool:
    """Check for URI matches using raw byte sequence search.

    Args:
        content: Raw response content as bytes
        needles: List of encoded URI variations to search for

    Returns:
        True if any needle is found in the content
    """
    return any(content.find(needle) != -1 for needle in needles)


def _extract_and_resolve_urls(html_content: str, container_uri: str, candidate_uri: str, variations: list[str]) -> bool:
    """Extract URLs from HTML and check for matches after resolving relative URLs.

    Args:
        html_content: Decoded HTML content
        container_uri: Base URI for resolving relative URLs
        candidate_uri: Target URI to match
        variations: List of URI variations to check against

    Returns:
        True if a match is found
    """
    try:
        # Find all href and src attributes
        url_pattern = r'(?:href|src)=["\']([^"\']+)["\']'
        urls = re.findall(url_pattern, html_content, re.IGNORECASE)

        for url in urls:
            # Skip empty, anchor-only, or protocol-relative URLs
            if not url or url.startswith('#') or url.startswith('//'):
                continue

            # Resolve relative URL to absolute URL
            absolute_url = urllib.parse.urljoin(container_uri, url)

            # Check against candidate URI and all variations
            if absolute_url in (candidate_uri, *variations):
                return True

    except Exception as e:
        logger.info(f"Exception parsing URLs: {container_uri} -> {candidate_uri} -> {e}")

    return False


def _check_html_text(content: bytes, candidate_uri: str) -> bool:
    """Check for URI matches in HTML-unescaped text content.

    Args:
        content: Raw response content as bytes
        candidate_uri: URI to search for

    Returns:
        True if candidate URI is found in unescaped content
    """
    try:
        text = content.decode("utf-8", errors="ignore")
        return candidate_uri in html.unescape(text)
    except Exception:
        return False


def _save_debug_content(content: bytes, container_uri: str) -> None:
    """Save response content to file for debugging purposes.

    Args:
        content: Raw response content as bytes
        container_uri: Source URI for generating filename
    """
    os.makedirs("./content", exist_ok=True)

    # Create a safe filename from the URI
    parsed = urllib.parse.urlparse(container_uri)
    safe_filename = f"{parsed.netloc}{parsed.path}".replace("/", "_").replace(":", "_")
    if parsed.query:
        safe_filename += f"_{parsed.query.replace('&', '_').replace('=', '_')}"
    if parsed.fragment:
        safe_filename += f"_{parsed.fragment.replace('#', '').replace('=', '_')}"

    # Ensure filename isn't too long and add .html extension
    safe_filename = safe_filename[:200] + ".html"

    filepath = f"./content/{safe_filename}"
    print(f"Writing content to {filepath}")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content.decode("utf-8", errors="ignore"))


def _fetch_content(container_uri: str, timeout: int) -> bytes | None:
    """Fetch content from URI with proper error handling.

    Args:
        container_uri: URI to fetch content from
        timeout: Request timeout in seconds

    Returns:
        Response content as bytes, or None if fetch fails
    """
    try:
        response = http_client.get(container_uri, timeout=timeout)
        if response.status_code != 200:
            return None
        return response.content
    except Exception as e:
        logger.info(f"Error fetching {container_uri}: {e}")
        return None


def uri_contains(
    container_uri: str,
    candidate_uri: str,
    timeout: int = 30,
    chunk_size: int = 65536,
) -> bool:
    """Check whether the resource at ``container_uri`` contains ``candidate_uri``.

    Uses multiple search strategies for robust URI detection:
    1. Raw byte sequence matching for exact URI matches
    2. HTML parsing to extract and resolve relative URLs to absolute URLs
    3. Text-level search in HTML-unescaped content

    Args:
        container_uri: URI to fetch and search within
        candidate_uri: URI to look for inside the fetched content
        timeout: Network timeout in seconds
        chunk_size: Size of streaming chunks in bytes (unused in current implementation)

    Returns:
        True if the fetched content contains the candidate URI, else False
    """
    logger.info(f"Checking if {container_uri} contains {candidate_uri}")
    if not container_uri or not candidate_uri:
        return False

    # Generate URI variations for robust matching
    variations = _generate_uri_variations(candidate_uri)
    if not variations:
        logger.info(f"No variations found for {candidate_uri}")
        return False

    # Fetch content from the container URI
    content = _fetch_content(container_uri, timeout)
    if content is None:
        logger.info(f"No content found for {container_uri}")
        return False

    # Strategy 1: Raw byte sequence matching
    needles = [v.encode("utf-8") for v in variations]
    if _check_raw_bytes(content, needles):
        logger.info(f"Raw byte sequence matching found for {candidate_uri}")
        return True

    # Strategy 2: HTML URL resolution
    html_content = content.decode("utf-8", errors="ignore")
    if _extract_and_resolve_urls(html_content, container_uri, candidate_uri, variations):
        logger.info(f"HTML URL resolution found for {candidate_uri}")
        return True

    # Strategy 3: HTML text fallback search
    if _check_html_text(content, candidate_uri):
        logger.info(f"HTML text fallback search found for {candidate_uri}")
        return True

    # Save content for debugging if no match found
    #_save_debug_content(content, container_uri)
    logger.info(f"No match found for {candidate_uri}")

    return False


__all__ = ["uri_contains"]