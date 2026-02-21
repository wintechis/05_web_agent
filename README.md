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

### Benchmark CLI (`benchmark/cli`)

Three entry points: **run_inference**, **run_evaluation**, and **generate_challenge**. Run from the project root, e.g. `python -m benchmark.cli.run_inference ...` or `python benchmark/cli/run_inference.py ...`.

#### Run inference

Runs the agent on every question in the benchmark YAML files and writes predictions.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `input_folder` | yes | Directory containing benchmark YAML files (e.g. `benchmark/experiments/02`). All `.yaml`/`.yml` files are processed. |
| `output_folder` | yes | Directory where result YAML files are written. One output file per input file (same basename). |
| `--trace-dir` | no | Directory for per-trace JSONL files. Default: `output_folder/traces`. Override with env `OTEL_TRACE_DIR` if `--trace-dir` is not set. |

**Environment**

- `MAX_AGENT_STEPS` – If set and > 0, caps the number of agent steps per question.

**Output**

- One YAML file per input file in `output_folder`, each with a list of entries with `id`, question, gold data, `model`, `predicted_answer`, and `trace_file`.

**Example**

```bash
python -m benchmark.cli.run_inference benchmark/experiments/02 out/inference
MAX_AGENT_STEPS=10 python -m benchmark.cli.run_inference evaluation/experiments/02/questions evaluation/experiments/02 --trace-dir out/traces
```

#### Run evaluation

Evaluates a **single** results YAML file (e.g. one produced by run_inference) and prints or writes metrics.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `results_file` | yes | Path to a results YAML file (e.g. `out/inference/wikipedia.yaml` from run_inference). |
| `--output` | no | If set, path to write evaluation metrics and per-task details as YAML. |

**Output**

- **stdout**: Claimed Success Rate (CSR), True Success Rate (TSR), Path Optimality (PO), and prefix-match metric (PPM).
- **File** (if `--output` is set): YAML with the same metrics plus per-task fields (e.g. `predicted_length`, `valid`, `success`, `start_uri`, `target_uri`).

**Example**

```bash
python -m benchmark.cli.run_evaluation out/inference/wikipedia.yaml
python -m benchmark.cli.run_evaluation out/inference/wikipedia.yaml --output out/evaluation.yaml
```

To evaluate all result YAMLs in `out/` (wikipedia and dbpedia) and write evaluation files into each dataset folder: `python scripts/evaluate_out_datasets.py` (optional: `--out-dir out`, `--dry-run`, `--datasource datasets_05`, `--dataset dbpedia`).

**Running inference on challenges**

To run inference on all challenge YAMLs in `challenges/dbpedia` and `challenges/wikipedia` for every non-blacklisted experiment and (optionally) a subset of models: `python scripts/run_inference_challenges.py`. Options: `--models qwen3_coder_30b,llama_3_3_70b` (whitelist; default = all models), `--experiment-blacklist exp1,exp2` or env `EXPERIMENT_BLACKLIST`, `--dry-run`, `--extra` for Hydra overrides. Output goes to `out/challenges_run/dbpedia/<model>/` and `out/challenges_run/wikipedia/<model>/`.

#### Generate challenge

Generates Wikipedia/DBpedia path-finding challenge YAML files (random start/end pages connected by a path of a given distance).

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--distance` | no | 3 | Path length (number of steps). |
| `--number-of-challenges` | no | 10 | Number of challenges to generate. |
| `--default-limit` | no | 2 | Limit used in SPARQL/API calls. |
| `--enforce-exact-distance` | no | true | If true, only keep paths with exactly `distance + 1` nodes. |
| `--log-level` | no | INFO | Logging level. |
| `--wikipedia-output` | no | wikipedia_challenge.yaml | Output path for Wikipedia-URL challenge file. |
| `--dbpedia-output` | no | dbpedia_challenge.yaml | Output path for DBpedia-URL challenge file. |

**Output**

- Two YAML files: one with Wikipedia URLs and one with DBpedia URLs, each containing the list of path challenges.

**Example**

```bash
python -m benchmark.cli.generate_challenge
python -m benchmark.cli.generate_challenge --distance 2 --number-of-challenges 5 --wikipedia-output my_wiki.yaml --dbpedia-output my_dbp.yaml
```
