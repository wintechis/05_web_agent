"""Web agent package: vanilla agent, clients, tools, prompt templates, telemetry."""

from agent.agents import RationaleToolCallingAgent, vanilla_web_agent
from agent.clients import http_client, openai_inference_model
from agent.telemetry import DEFAULT_TRACE_DIR, TRACE_DIR_ENV, init_tracing
from agent.tools import GETTool, POSTRdfTool, POSTTool, PUTTool
from agent.prompt import WEB_AGENT_PROMPT_TEMPLATES

__all__ = [
    "vanilla_web_agent",
    "RationaleToolCallingAgent",
    "http_client",
    "openai_inference_model",
    "init_tracing",
    "DEFAULT_TRACE_DIR",
    "TRACE_DIR_ENV",
    "GETTool",
    "POSTTool",
    "PUTTool",
    "POSTRdfTool",
    "WEB_AGENT_PROMPT_TEMPLATES",
]
