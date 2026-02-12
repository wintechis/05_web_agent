## Web Agent

### HTTP server

Start the API server:

```bash
python -m agent.server
# or: uvicorn agent.server:app --host 0.0.0.0 --port 8000
```

- **POST /ask** – Submit a question. Returns `{"id": "..."}` immediately. The agent runs in the background.
- **GET /ask/{id}** – Poll for the result. Returns `{"status": "pending"}` until ready, then `{"status": "completed", "answer": "..."}` or `{"status": "failed", "error": "..."}`.

Example:

```bash
# Submit question
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question": "What is the capital of France?"}'
# -> {"id": "93c9bed7-1adc-47bd-b2b9-e1252db10e69"}

# Poll for result
curl http://localhost:8000/ask/93c9bed7-1adc-47bd-b2b9-e1252db10e69
# -> {"status": "pending"} or {"status": "completed", "answer": "Paris", "error": null}
```

### Run inference
- Run a single benchmark folder and write predictions:
  - `python3 run_inference.py benchmark/experiments/02 out/inference`
- Optional: set `MAX_AGENT_STEPS` to cap steps:
  - `MAX_AGENT_STEPS=10 python3 run_inference.py benchmark/experiments/02 out/inference`
- Optional: set trace output directory:
  - `OTEL_TRACE_DIR=web_agent_traces python3 run_inference.py benchmark/experiments/02 out/inference`

The output is written as YAML files in the output folder. Each entry includes the model id and a `predicted_answer`.

### Run evaluation
- Evaluate a folder of inference outputs against the benchmark gold data:
  - `python3 run_evaluation.py benchmark/experiments/02 out/inference out/evaluation`

The evaluation output contains CSR/TSR/PO metrics and per-question details.
