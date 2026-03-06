## Changelog

### 2026-02-21
- scripts/run_inference_challenges.py: run inference over challenges/dbpedia and challenges/wikipedia for every (experiment, model) pair. Output is now per-experiment (out/challenges_run/<experiment>/<dataset>/<model_slug>/) so multiple experiments do not overwrite each other; script reads experiment YAML for dataset and passes input_folder/output_folder overrides to Hydra. Uses run_inference_hydra.py with datasource=challenges. Experiments discovered from config/experiment/*.yaml (optional --experiment-blacklist or EXPERIMENT_BLACKLIST); models from config/model/*.yaml with optional --models whitelist (empty = all). Options: --dry-run, --extra for Hydra overrides. config/datasource/challenges.yaml added for input challenges/{dbpedia,wikipedia} and output out/challenges_run/{dbpedia,wikipedia}.
- scripts/split_challenges.py: add --per-dataset-dirs to write wikipedia splits to <output-dir>/wikipedia and dbpedia to <output-dir>/dbpedia. Split challenges/wikipedia_challenge_sampled.yaml and challenges/dbpedia_challenge_sampled.yaml into 50 sets in challenges/wikipedia/ and challenges/dbpedia/.
- scripts/evaluate_out_datasets.py: evaluate each benchmark result YAML in out/ for wikipedia and dbpedia. Discovers *-challenge.yaml under out/datasets_*/dbpedia and out/datasets_*/wikipedia, runs benchmark.cli.run_evaluation on each, writes <stem>-evaluation.yaml in the same folder. Options: --out-dir (default out), --dry-run, --datasource, --dataset. Continues on failure and exits non-zero if any evaluation failed.
### 2026-03-04
- **Transformers inference backend:** Add optional local inference via Hugging Face Transformers. New module `agent/clients_transformers.py` builds smolagents `TransformersModel` from env; `agent/clients.py` uses `INFERENCE_BACKEND` (`openai` | `transformers`) so `get_openai_inference_model()` returns either OpenAIModel or TransformersModel. Model id remains `OPENAI_MODEL_ID` (Hugging Face id when backend is transformers) so Hydra and run_inference_hydra work unchanged. Optional env: `HF_DEVICE`, `HF_MAX_NEW_TOKENS`, `TRUST_REMOTE_CODE`, `HF_TORCH_DTYPE`. Install with `uv sync --group transformers`.
- Add Hydra model config `qwen3_5_35b` for `Qwen/Qwen3.5-35B-A3B-FP8`. Use with `model=qwen3_5_35b`.
- Fix URI normalization in evaluation: `parse_predicted` and `parse_gold_path` now percent-decode URIs via `normalize_uri` (`urllib.parse.unquote`), so `K%C3%A4larne` and `Kälarne` compare equal. Fixes incorrect TSR, PO, and PPM when agent returns percent-encoded URLs but gold standard uses Unicode. Added tests for normalization in `test_path_parser.py` and PPM tests in `test_metrics.py`.

### 2026-02-17
- Experiment config via Hydra: optional `run_inference_hydra.py` entry point and `config/` tree. Use `experiment=<name>` to switch presets (e.g. `semantic_outgoing_turtle`, `compression_dbpedia_jsonld`) without editing `.env`. CLI overrides and multirun (`-m experiment=exp1,exp2`) supported. See `docs/experiment-config-options.md`. Added `hydra-core>=1.3.0` dependency.
- Hydra config: input/output folders are chosen from `dataset_paths` (dbpedia vs wikipedia) based on each experiment's `dataset`; each experiment YAML has `dataset: dbpedia` or `dataset: wikipedia`. Override with `input_folder=...` / `output_folder=...` on CLI when needed.
- Hydra: add `_self_` to defaults list in config.yaml (fixes UserWarning and ensures dataset_paths are in the composed config). Read experiment keys from `cfg.experiment` when present (Hydra nests config group content under the group name).
- Fix trace file location: remove module-level `init_tracing()` from `agent/agents.py` so tracing is initialized only in `RunInferenceUseCase.run()` after `OTEL_TRACE_DIR` is set. Trace .jsonl files are now written to the benchmark output trace_dir (e.g. `out/dbpedia/traces/`) instead of the default `web_agent_traces/`.
- Inference: when an unhandled exception occurs during agent run, store the error message as the predicted answer (prefix "Error: ", truncated to 2000 chars) and set task_state to "failed" so benchmark YAML records what went wrong instead of an empty predicted_answer.
- Inference: include task_state in predicted_answer when the agent returns a dict with urls and task_state, so the stored string is the complete response (e.g. "task_state: partial" followed by the URL list) instead of only the URLs.
- Hydra model experiments: add config group **model** with one YAML per LLM (qwen3_coder_30b, devstral_2_123b, qwen3_vl_30b, glm_4_7, mistral_large_3_675b, meta_llama_3_1_8b, llama_3_3_70b). Run with `model=<name>`; OPENAI_MODEL_ID is set from config and output goes to a per-model subfolder (e.g. out/dbpedia/llama-3.3-70b-instruct/). Lazy model resolution in agent/clients.py (get_openai_inference_model) and agent/agents.py (get_vanilla_web_agent) so the model chosen by Hydra is used at run time.
- scripts/split_challenges.py: split wikipedia_challenge.yaml and dbpedia_challenge.yaml into n equal-sized YAMLs (same structure; aligned by index so part k of both datasets contain the same challenges).
- generate_challenge: handle Six Degrees API timeouts and transport errors (ReadTimeout, ConnectTimeout, WriteTimeout, HTTPError) in find_wiki_path; log warning and return [] so generation continues with the next attempt. Increase request timeout to 60s (SIX_DEGREES_REQUEST_TIMEOUT) for path finding.
- Hydra datasource config: add config group **datasource** to select dataset path sets. Options: experiment_10 (evaluation/experiments/10_dbpedia and 10_wikipedia), datasets_02, datasets_03, datasets_04, datasets_05 (from datasets/). Default is experiment_10. Run with e.g. `datasource=datasets_04`; path resolution uses cfg.datasource.dataset_paths.

### 2026-02-16
- turtle_terser_version (resource_transform): include URI in output only on first occurrence per URI; later occurrences show only the label [label].
- generate_challenge: handle Six Degrees API errors (e.g. 502) and non-JSON responses in find_wiki_path; return [] instead of crashing so the generator can continue with the next attempt.
- When max steps is reached, agent now requests a structured final_answer tool call (urls + task_state) instead of free text; override `_handle_max_steps_reached` in RationaleToolCallingAgent so StructuredFinalAnswerTool is used in both normal and max-steps paths.
- Structured final answer: custom `StructuredFinalAnswerTool` (agent/tools.py) with `urls` and `task_state` (completed, partial, failed, unclear). Replaces default final_answer; agent returns `{"urls": [...], "task_state": "..."}`. Inference stores `task_state` in benchmark YAML when present; `_normalize_answer` and `_extract_answer_and_task_state` support both structured and legacy answers.
- Determinism: support OPENAI_TEMPERATURE, OPENAI_TOP_P, OPENAI_SEED in .env; values are passed to OpenAIModel for more reproducible runs (e.g. temperature=0, top_p=1, seed=42 in .env.example). Inference config overview prints these three env vars.
- GET tool: retry up to 3 times on transient transport errors (e.g. RemoteProtocolError, ConnectError, ReadTimeout) with 1s delay; return an error message Response after all retries fail instead of raising.
- Benchmark runs: print a configuration overview at the start of each run (run_inference: paths, model, MAX_AGENT_STEPS, MODIFY_CONTEXT, REPRESENTATION_FORMAT, CONTEXT, RDF_REPRESENTATION, PRUNING_METHOD, CONTEXT_COMPRESSION, MAX_TOKEN_FOR_MODEL; run_evaluation: results_file, output; generate_challenge: all CLI args).
- run_inference: accept both top-level `benchmark` and `questions` in input YAML (via iter_entries). Fixes empty runs when using evaluation/experiments challenge files (which use `benchmark:`). Log a warning when no entries are found.
- README: document benchmark CLI (run_inference, run_evaluation, generate_challenge) with input/output parameters and examples.
- Add `agent/resource_transform.py`: transformation variants for GET (URI rewriting, RDF pruning, serialization). Driven by MODIFY_CONTEXT, REPRESENTATION_FORMAT, CONTEXT, RDF_REPRESENTATION, PRUNING_METHOD.
- GET tool: when MODIFY_CONTEXT is true, rewrites URL via modify_uri, sets Accept header, and runs get_representation on response. Fixed content-type branching (use elif so text is always set).
- Add `agent/context_compression.py`: when CONTEXT_COMPRESSION is enabled and estimated tokens exceed 0.8 * MAX_TOKEN_FOR_MODEL, tool message content is truncated to 500 chars before each model call. Model wrapper wired in `agent/clients.py`.
- Dependencies: add rdflib and pyld to pyproject.toml.

### 2026-02-13
- run_inference: default trace log directory is now output_folder/traces (override with --trace-dir or OTEL_TRACE_DIR)

### 2026-01-29
- add OpenTelemetry tracing with JSONL file span exporter in `telemetry.py`
- split trace logs into per-trace JSONL files. They are stored now in DEFAULT_TRACE_DIR (if not configured it is /web_agent_traces)
- initialize tracing for each agent run
- add OpenTelemetry dependencies in `pyproject.toml`
- Reorganized code based.
