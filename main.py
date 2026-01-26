from smolagents import ToolCallingAgent, OpenAIModel
from dotenv import load_dotenv
import os
from prompt import WEB_AGENT_PROMPT_TEMPLATES
from tools import GETTool

load_dotenv()

MODEL_ID = os.getenv("OPENAI_MODEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")

model = OpenAIModel(
    model_id=MODEL_ID,  # or any model name your API supports
    api_key=OPENAI_API_KEY,
    api_base=OPENAI_BASE_URL,  # Changed from base_url to api_base
)

agent = ToolCallingAgent(
    model=model,
    tools=[GETTool()],
    prompt_templates=WEB_AGENT_PROMPT_TEMPLATES,
)


result = agent.run(
    "Find the path from the start URL: https://en.wikipedia.org/wiki/Pavhari_Baba to the end URL: https://en.wikipedia.org/wiki/Hindu.",
)
