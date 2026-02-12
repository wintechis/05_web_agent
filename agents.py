from typing import Any

from dotenv import load_dotenv
from smolagents import (
    AgentToolCallError,
    AgentToolExecutionError,
    LogLevel,
    ToolCallingAgent,
    validate_tool_arguments,
)

from prompt import WEB_AGENT_PROMPT_TEMPLATES
from telemetry import init_tracing
from tools import GETTool
from clients import openai_inference_model

RATIONALE_KEY = "_rationale"
RATIONALE_INPUT_SPEC = {
    "type": "string",
    "description": "Describe your reasoning step-by-step in plain text BEFORE calling any tool.",
}

load_dotenv()

init_tracing()


# Vanilla Web Agent
# A Vanilla Web Agent is a basic Web Agent that can use
# only the HTTP Request Methods (GET, POST, PUT, DELETE)
# to interact with the web.


def _with_rationale_inputs(
    inputs: dict[str, dict[str, str | type | bool]],
) -> dict[str, dict[str, str | type | bool]]:
    if RATIONALE_KEY in inputs:
        return dict(inputs)
    # Ensure _rationale is the first element in the returned dict
    return {RATIONALE_KEY: dict(RATIONALE_INPUT_SPEC), **inputs}


class RationaleToolCallingAgent(ToolCallingAgent):
    """ToolCallingAgent that requires a rationale for every tool call."""

    def _setup_tools(self, tools, add_base_tools):
        super()._setup_tools(tools, add_base_tools)
        for tool in self.tools.values():
            tool.inputs = _with_rationale_inputs(tool.inputs)

    def _setup_managed_agents(self, managed_agents=None) -> None:
        super()._setup_managed_agents(managed_agents)
        for agent in self.managed_agents.values():
            agent.inputs = _with_rationale_inputs(agent.inputs)

    def execute_tool_call(self, tool_name: str, arguments: dict[str, str] | str) -> Any:
        available_tools = {**self.tools, **self.managed_agents}
        if tool_name not in available_tools:
            raise AgentToolExecutionError(
                f"Unknown tool {tool_name}, should be one of: {', '.join(available_tools)}.",
                self.logger,
            )

        tool = available_tools[tool_name]
        arguments = self._substitute_state_variables(arguments)
        is_managed_agent = tool_name in self.managed_agents

        try:
            validate_tool_arguments(tool, arguments)
        except (ValueError, TypeError) as exc:
            raise AgentToolCallError(str(exc), self.logger) from exc
        except Exception as exc:
            error_msg = (
                f"Error executing tool '{tool_name}' with arguments {str(arguments)}: "
                f"{type(exc).__name__}: {exc}"
            )
            raise AgentToolExecutionError(error_msg, self.logger) from exc

        rationale = None
        if isinstance(arguments, dict):
            arguments = dict(arguments)
            rationale = arguments.pop(RATIONALE_KEY, None)

        if rationale:
            self.logger.log(
                f"Rationale: {rationale}",
                level=LogLevel.INFO,
            )

        try:
            if isinstance(arguments, dict):
                return tool(**arguments) if is_managed_agent else tool(**arguments, sanitize_inputs_outputs=True)
            return tool(arguments) if is_managed_agent else tool(arguments, sanitize_inputs_outputs=True)
        except Exception as exc:
            if is_managed_agent:
                error_msg = (
                    f"Error executing request to team member '{tool_name}' with arguments {str(arguments)}: {exc}\n"
                    "Please try again or request to another team member"
                )
            else:
                error_msg = (
                    f"Error executing tool '{tool_name}' with arguments {str(arguments)}: "
                    f"{type(exc).__name__}: {exc}\nPlease try again or use another tool"
                )
            raise AgentToolExecutionError(error_msg, self.logger) from exc


vanilla_web_agent = RationaleToolCallingAgent(
    model=openai_inference_model,
    tools=[GETTool()],
    verbosity_level=2,
    prompt_templates=WEB_AGENT_PROMPT_TEMPLATES,
)
