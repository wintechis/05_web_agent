"""Web agent runner using pi_agent's agent_loop. Exposes sync run(question, max_steps=None)."""

import asyncio
import os
import time
from typing import Any

from dotenv import load_dotenv
from pi_ai.types import UserMessage
from pi_agent.agent_loop import agent_loop
from pi_agent.types import AgentContext, AgentLoopConfig, AgentMessage

from agent.clients import get_openai_inference_model
from agent.context_compression import (
    compress_messages,
    is_context_compression_enabled,
    should_compress_messages,
)
from agent.prompt import get_web_agent_prompt_templates
from agent.tools import GETTool, StructuredFinalAnswerTool

load_dotenv()

# Tracing is initialized by RunInferenceUseCase.run() (after setting OTEL_TRACE_DIR).
# For standalone agent use, set OTEL_TRACE_DIR and call init_tracing() before running.


def _default_convert_to_llm(messages: list[AgentMessage]) -> list[AgentMessage]:
    """Keep only LLM-compatible messages (user, assistant, toolResult)."""
    return [
        m
        for m in messages
        if hasattr(m, "role") and getattr(m, "role", "") in ("user", "assistant", "toolResult")
    ]


async def _transform_context_compression(
    messages: list[AgentMessage], cancel_event: asyncio.Event | None
) -> list[AgentMessage]:
    """Apply context compression before sending to LLM. toolResult role is treated as tool response."""
    if not should_compress_messages(messages):
        return messages
    return compress_messages(messages)


class VanillaWebAgentRunner:
    """Sync runner for the web agent. Holds model, tools, prompt; exposes run(question, max_steps=None)."""

    def __init__(self) -> None:
        self._model = get_openai_inference_model()
        self._tools = [GETTool, StructuredFinalAnswerTool]
        self._templates = get_web_agent_prompt_templates()

    def run(self, question: str, max_steps: int | None = None) -> Any:
        """Run the agent on a question. Returns final answer (dict with urls/task_state, or string)."""
        try:
            return asyncio.run(_arun(question, self._model, self._tools, self._templates, max_steps))
        except Exception as e:
            raise RuntimeError(f"Agent run failed: {e}") from e


async def _arun(
    question: str,
    model: Any,
    tools: list[Any],
    templates: Any,
    max_steps: int | None,
) -> Any:
    """Async run: build context/config, run agent_loop, collect final_answer from events."""
    system_prompt = templates.system_prompt
    context = AgentContext(system_prompt=system_prompt, messages=[], tools=tools)

    user_msg = UserMessage(
        role="user",
        content=question,
        timestamp=int(time.time() * 1000),
    )
    prompts = [user_msg]

    def get_api_key(provider: str) -> str | None:
        if provider == "openai":
            return os.environ.get("OPENAI_API_KEY")
        return None

    transform_context = _transform_context_compression if is_context_compression_enabled() else None

    config = AgentLoopConfig(
        model=model,
        convert_to_llm=_default_convert_to_llm,
        transform_context=transform_context,
        get_api_key=get_api_key,
    )

    cancel_event: asyncio.Event | None = asyncio.Event()
    stream = agent_loop(prompts, context, config, cancel_event=cancel_event)

    last_final_answer: Any = None
    step_count = 0
    max_steps_val = max_steps if max_steps is not None else 0

    try:
        async for event in stream:
            if event.type == "tool_execution_end":
                if getattr(event, "tool_name", None) == "final_answer":
                    result = getattr(event, "result", None)
                    if result is not None and getattr(result, "details", None) is not None:
                        last_final_answer = result.details
            if event.type == "turn_end":
                step_count += 1
                if max_steps_val > 0 and step_count >= max_steps_val:
                    if cancel_event:
                        cancel_event.set()
                    break
            if event.type == "agent_end":
                break
    except asyncio.CancelledError:
        pass
    except Exception:
        if last_final_answer is None:
            raise

    if last_final_answer is not None:
        return last_final_answer
    # No final_answer tool was called; return a default so _extract_answer_and_task_state still works
    return {"urls": [], "task_state": "partial"}


def get_vanilla_web_agent() -> VanillaWebAgentRunner:
    """Return the web agent runner (uses current OPENAI_MODEL_ID and env)."""
    return VanillaWebAgentRunner()


# Default agent at import time; use get_vanilla_web_agent() when model may be set later (e.g. Hydra).
vanilla_web_agent = get_vanilla_web_agent()
