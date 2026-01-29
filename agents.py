from dotenv import load_dotenv
from smolagents import ToolCallingAgent

from prompt import WEB_AGENT_PROMPT_TEMPLATES
from telemetry import init_tracing
from tools import GETTool
from clients import openai_inference_model

load_dotenv()

init_tracing()


# Vanilla Web Agent
# A Vanilla Web Agent is a basic Web Agent that can use 
# only the HTTP Request Methods (GET, POST, PUT, DELETE)
# to interact with the web.
vanilla_web_agent = ToolCallingAgent(
    model=openai_inference_model,
    tools=[GETTool()],
    prompt_templates=WEB_AGENT_PROMPT_TEMPLATES,
)
