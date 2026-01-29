import markdownify
from pydantic import BaseModel
from smolagents import Tool
from clients import http_client

class GETResponse(BaseModel):
    text: str
    url: str



def markdownify_text(text: str) -> str:
    return markdownify.markdownify(text)


def _get(url: str) -> GETResponse:
    """Internal synchronous function to fetch and process URL."""
    response = http_client.get(url)

    if response.status_code != 200:
        return GETResponse(
            text=f"Failed to GET {url}: {response.status_code}, {response.text}",
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