"""HTTP server exposing the web agent at POST /ask."""

import asyncio
import uuid
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from agent import vanilla_web_agent

app = FastAPI(title="Web Agent API", description="Ask questions to the web agent.")

# In-memory task store: id -> {status, result?, error?}
_TASKS: dict[str, dict] = {}


def _run_agent_sync(task_id: str, question: str) -> None:
    """Run agent synchronously and update task state. Called from thread pool."""
    try:
        result = vanilla_web_agent.run(question)
        _TASKS[task_id]["status"] = "completed"
        _TASKS[task_id]["result"] = str(result)
    except Exception as exc:
        _TASKS[task_id]["status"] = "failed"
        _TASKS[task_id]["error"] = str(exc)


async def _run_agent_async(task_id: str, question: str) -> None:
    """Run agent in thread pool to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _run_agent_sync, task_id, question)


class AskRequest(BaseModel):
    """Request body for the POST /ask endpoint."""

    question: str


class AskCreatedResponse(BaseModel):
    """Response for POST /ask: returns the task ID immediately."""

    id: str


class AskStatusResponse(BaseModel):
    """Response for GET /ask/{id}: status and optional result."""

    status: Literal["pending", "completed", "failed"]
    answer: str | None = None
    error: str | None = None


@app.post("/ask", response_model=AskCreatedResponse)
def create_ask(request: AskRequest, background_tasks: BackgroundTasks) -> AskCreatedResponse:
    """Create a question task and return its ID immediately. Agent runs in background."""
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question must not be empty")

    task_id = str(uuid.uuid4())
    _TASKS[task_id] = {"status": "pending", "result": None, "error": None}

    background_tasks.add_task(_run_agent_async, task_id, question)

    return AskCreatedResponse(id=task_id)


@app.get("/ask/{task_id}", response_model=AskStatusResponse)
def get_ask_status(task_id: str) -> AskStatusResponse:
    """Check if the task result is available. Returns pending, completed, or failed."""
    if task_id not in _TASKS:
        raise HTTPException(status_code=404, detail="task not found")

    task = _TASKS[task_id]
    status = task["status"]

    if status == "pending":
        return AskStatusResponse(status="pending")
    if status == "completed":
        return AskStatusResponse(status="completed", answer=task["result"])
    return AskStatusResponse(status="failed", error=task["error"])


def main() -> None:
    """Run the server. Usage: python -m agent.server"""
    import uvicorn

    uvicorn.run("agent.server:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
