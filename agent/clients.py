import os

from dotenv import load_dotenv
from smolagents import OpenAIModel
import httpx

load_dotenv()


#################################################################
# OpenAI Inference Model
#################################################################
MODEL_ID = os.getenv("OPENAI_MODEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")

openai_inference_model = OpenAIModel(
    model_id=MODEL_ID,  # or any model name your API supports
    api_key=OPENAI_API_KEY,
    api_base=OPENAI_BASE_URL,  # Changed from base_url to api_base
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
