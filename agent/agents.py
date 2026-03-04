import os
from typing import Any

from dotenv import load_dotenv
from smolagents import (
    AgentGenerationError,
    AgentParsingError,
    AgentToolCallError,
    AgentToolExecutionError,
    ChatMessage,
    LogLevel,
    MessageRole,
    ToolCallingAgent,
    validate_tool_arguments,
)
from smolagents.agents import ActionOutput, ToolOutput, populate_template
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


THINKING_MODE_ENV = "THINKING_MODE"
PLAN_MODE_ENV = "PLAN_MODE"

PLAN_INPUT_SPEC = {
    "type": "string",
    "description": (
        "Your navigation plan for this step: "
        "(1) where you currently are, "
        "(2) which URIs you have already fetched and ruled out, "
        "(3) the specific URI you will fetch next and why it is likely to lead toward the target."
    ),
    "nullable": True,
}


def _extract_text(msg: ChatMessage) -> str:
    if isinstance(msg.content, str):
        return msg.content
    if isinstance(msg.content, list):
        return " ".join(b.get("text", "") for b in msg.content if isinstance(b, dict) and b.get("type") == "text")
    return ""


class RationaleToolCallingAgent(ToolCallingAgent):
    """ToolCallingAgent with custom error handling and forced final-answer on max-steps."""

    def _plan_enabled(self) -> bool:
        return os.getenv(PLAN_MODE_ENV, "").strip().lower() in ("true", "1", "yes")

    def _thinking_enabled(self) -> bool:
        return os.getenv(THINKING_MODE_ENV, "").strip().lower() in ("true", "1", "yes")

    def _with_plan_inputs(self, tool):
        tool.inputs = {"_plan": PLAN_INPUT_SPEC, **tool.inputs}
        return tool

    def _setup_tools(self, tools, add_base_tools=False):
        super()._setup_tools(tools, add_base_tools)
        if self._plan_enabled():
            self.tools = {k: self._with_plan_inputs(v) for k, v in self.tools.items()}

    def _setup_managed_agents(self, managed_agents):
        super()._setup_managed_agents(managed_agents)
        if self._plan_enabled():
            self.managed_agents = {k: self._with_plan_inputs(v) for k, v in self.managed_agents.items()}

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

        if isinstance(arguments, dict):
            arguments.pop("_plan", None)

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

    def _step_stream(self, memory_step):
        if not self._thinking_enabled() or self.stream_outputs:
            yield from super()._step_stream(memory_step)
            return

        memory_messages = self.write_memory_to_messages()
        input_messages = memory_messages.copy()
        memory_step.model_input_messages = input_messages

        # Call 1: reasoning only (no tools_to_call_from → forces text-only output)
        try:
            thinking_msg = self.model.generate(input_messages)
        except Exception as e:
            raise AgentGenerationError(f"Error during thinking call:\n{e}", self.logger) from e

        reasoning_text = _extract_text(thinking_msg)
        if reasoning_text.strip():
            input_messages = input_messages + [
                ChatMessage(role=MessageRole.ASSISTANT,
                            content=[{"type": "text", "text": reasoning_text}]),
                ChatMessage(role=MessageRole.USER,
                            content=[{"type": "text", "text": "Based on your reasoning above, call the appropriate tool now."}]),
            ]

        # Call 2: tool decision
        try:
            chat_message = self.model.generate(
                input_messages,
                stop_sequences=["Observation:", "Calling tools:"],
                tools_to_call_from=self.tools_and_managed_agents,
            )
        except Exception as e:
            raise AgentGenerationError(f"Error while generating output:\n{e}", self.logger) from e

        memory_step.model_output_message = chat_message
        memory_step.model_output = chat_message.content
        memory_step.token_usage = chat_message.token_usage

        if chat_message.tool_calls is None or len(chat_message.tool_calls) == 0:
            try:
                chat_message = self.model.parse_tool_calls(chat_message)
            except Exception as e:
                raise AgentParsingError(f"Error parsing tool calls: {e}", self.logger) from e
        else:
            for tc in chat_message.tool_calls:
                tc.function.arguments = parse_json_if_needed(tc.function.arguments)

        final_answer, got_final_answer = None, False
        for output in self.process_tool_calls(chat_message, memory_step):
            yield output
            if isinstance(output, ToolOutput) and output.is_final_answer:
                final_answer = output.output
                got_final_answer = True
                if isinstance(final_answer, str) and final_answer in self.state:
                    final_answer = self.state[final_answer]

        yield ActionOutput(output=final_answer, is_final_answer=got_final_answer)

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
        tools=[GETTool(), StructuredFinalAnswerTool()], #  POSTRdfTool(), PUTTool(),
        verbosity_level=LogLevel.INFO,
        prompt_templates=get_web_agent_prompt_templates(),
    )


# Default agent at import time; use get_vanilla_web_agent() when model may be set later (e.g. Hydra).
vanilla_web_agent = get_vanilla_web_agent()
