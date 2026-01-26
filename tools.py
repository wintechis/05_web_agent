from smolagents import Tool
import httpx
from typing import Any
from pydantic import BaseModel
from loguru import logger
import markdownify

class GETResponse(BaseModel):
    text: str
    url: str

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
}

httpx_client = httpx.Client()


def markdownify_text(text: str) -> str:
    return markdownify.markdownify(text)


def _get(url: str) -> GETResponse:
    """Internal synchronous function to fetch and process URL."""
    response = httpx_client.get(url, headers=HEADERS)

    if response.status_code != 200:
        return GETResponse(
            text=f"Failed to GET {url}: {response.status_code}",
            url=url,
        )

    text = markdownify_text(response.text)

    return GETResponse(
        text=text,
        url=url,
    )


class GETTool(Tool):
    """Tool to fetch and convert web pages to markdown."""
    
    name = "get"
    description = "Fetches a URL and returns the page content. Takes a URL as input and returns the the URL with the page content."
    inputs = {
        "url": {
            "type": "string",
            "description": "The URL to fetch and the page content.",
        }
    }
    output_type = "string"

    def forward(self, url: str) -> str:
        """Synchronous function to fetch URL and return markdown content."""
        result = _get(url)
        return f"URL: {result.url}\n\nContent:\n{result.text}"