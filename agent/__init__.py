"""Web agent package: vanilla agent runner, clients, tools, prompt templates, telemetry."""

from agent.agents import VanillaWebAgentRunner, get_vanilla_web_agent, vanilla_web_agent
from agent.clients import http_client, openai_inference_model

from agent.telemetry import DEFAULT_TRACE_DIR, TRACE_DIR_ENV, init_tracing
from agent.tools import GETTool, POSTRdfTool, POSTTool, PUTTool, StructuredFinalAnswerTool
from agent.prompt import WEB_AGENT_PROMPT_TEMPLATES

__all__ = [
    "vanilla_web_agent",
    "get_vanilla_web_agent",
    "VanillaWebAgentRunner",
    "http_client",
    "openai_inference_model",
    "init_tracing",
    "DEFAULT_TRACE_DIR",
    "TRACE_DIR_ENV",
    "GETTool",
    "POSTTool",
    "PUTTool",
    "POSTRdfTool",
    "StructuredFinalAnswerTool",
    "WEB_AGENT_PROMPT_TEMPLATES",
]
