from typing import Any

from dotenv import load_dotenv
from smolagents import (
    AgentToolCallError,
    AgentToolExecutionError,
    ChatMessage,
    LogLevel,
    MessageRole,
    ToolCallingAgent,
    validate_tool_arguments,
)
from smolagents.agents import populate_template
from smolagents.models import parse_json_if_needed

from agent.prompt import get_web_agent_prompt_templates
from agent.tools import GETTool, POSTRdfTool, PUTTool, StructuredFinalAnswerTool
from agent.clients import get_openai_inference_model

load_dotenv()

# Tracing is initialized by RunInferenceUseCase.run() (after setting OTEL_TRACE_DIR) so
# trace files are written to the benchmark output folder. For standalone agent use, set
# OTEL_TRACE_DIR and call init_tracing() before running.


# Vanilla Web Agent
# A Vanilla Web Agent is a basic Web Agent that can use
# only the HTTP Request Methods (GET, POST, PUT, DELETE)
# to interact with the web.


class RationaleToolCallingAgent(ToolCallingAgent):
    """ToolCallingAgent with custom error handling and forced final-answer on max-steps."""

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

    def _handle_max_steps_reached(self, task: str) -> Any:
        """When max steps is reached, ask the model for a structured final_answer tool call so we still get urls + task_state."""
        final_tool = self.tools.get("final_answer")
        if final_tool is None:
            return super()._handle_max_steps_reached(task)

        messages = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=[{"type": "text", "text": self.prompt_templates["final_answer"]["pre_messages"]}],
            )
        ]
        messages += self.write_memory_to_messages()[1:]
        messages.append(
            ChatMessage(
                role=MessageRole.USER,
                content=[
                    {
                        "type": "text",
                        "text": populate_template(
                            self.prompt_templates["final_answer"]["post_messages"], variables={"task": task}
                        ),
                    }
                ],
            )
        )
        try:
            chat_message: ChatMessage = self.model.generate(messages, tools_to_call_from=[final_tool])
        except Exception:
            return super()._handle_max_steps_reached(task)

        if not chat_message.tool_calls:
            return super()._handle_max_steps_reached(task)
        final_call = next(
            (tc for tc in chat_message.tool_calls if getattr(tc.function, "name", None) == "final_answer"),
            None,
        )
        if final_call is None:
            return super()._handle_max_steps_reached(task)

        arguments = parse_json_if_needed(getattr(final_call.function, "arguments", {}) or {})
        if not isinstance(arguments, dict):
            arguments = {}
        try:
            return self.execute_tool_call("final_answer", arguments)
        except Exception:
            return super()._handle_max_steps_reached(task)


def get_vanilla_web_agent() -> RationaleToolCallingAgent:
    """Return the web agent using the current OPENAI_MODEL_ID and SCRATCHPAD_MODE (for Hydra/model switching)."""
    return RationaleToolCallingAgent(
        model=get_openai_inference_model(),
        tools=[GETTool(), POSTRdfTool(), PUTTool(), StructuredFinalAnswerTool()],
        verbosity_level=LogLevel.INFO,
        prompt_templates=get_web_agent_prompt_templates(),
    )


# Default agent at import time; use get_vanilla_web_agent() when model may be set later (e.g. Hydra).
vanilla_web_agent = get_vanilla_web_agent()
