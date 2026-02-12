## Web Agent

### Installation

**With uv:**

```bash
uv sync
```

This creates a virtual environment and installs all dependencies. Run commands with `uv run python ...` or activate the venv first.

**With Python (pip):**

```bash
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -e .
```

**Environment configuration:**

Copy `.env.example` to `.env` and fill in your API credentials:

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL_ID
```

### Interacting with the Agent

#### **Via main.py (CLI, single task):**

Edit the `task` variable in `main.py` and run:

```bash
uv run python main.py
# or, with activated venv: python main.py
```

The agent runs once, blocks until the task completes, and prints the result.

#### **Via server (HTTP API):**

Start the server:

```bash
uv run python -m agent.server
# or: uvicorn agent.server:app --host 0.0.0.0 --port 8000
```

##### Longpolling
- **GET /** – Run the agent synchronously via query params. Accepts `task` (required) and `id` (optional). Blocks until completion and returns the result string directly, or the error message on failure. (This is for the current version of taskmaster.)

##### Polling
- **POST /ask** – Submit a question. Returns `{"id": "..."}` immediately. The agent runs in the background.
- **GET /ask/{id}** – Poll for the result. Returns `{"status": "pending"}` until ready, then `{"status": "completed", "answer": "..."}` or `{"status": "failed", "error": "..."}`.


Example:

```bash
# Sync request (GET /, blocks until done)
curl "http://localhost:8000/?task=What%20is%20the%20capital%20of%20France%3F"
# -> "Paris"

# Submit question
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question": "What is the capital of France?"}'
# -> {"id": "93c9bed7-1adc-47bd-b2b9-e1252db10e69"}

# Poll for result
curl http://localhost:8000/ask/93c9bed7-1adc-47bd-b2b9-e1252db10e69
# -> {"status": "pending"} or {"status": "completed", "answer": "Paris", "error": null}
```
