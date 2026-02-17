# Easily Modifying Experiment Environment

You currently drive experiments via env vars in `.env` (e.g. `MODIFY_CONTEXT`, `REPRESENTATION_FORMAT`, `RDF_REPRESENTATION`, `PRUNING_METHOD`, `CONTEXT_COMPRESSION`). Below are three ways to make switching experiments easier.

## Option 1: Hydra (recommended)

**Why Hydra fits:**

- **Named experiment configs** — One YAML per variant (e.g. `semantic_outgoing_turtle`, `compression_json_ld`) instead of commenting blocks in `.env`.
- **CLI overrides** — Run with a preset and override any key:  
  `python run_inference_hydra.py experiment=semantic_outgoing_turtle RDF_REPRESENTATION=turtle input_folder=... output_folder=...`
- **Multirun** — Sweep over experiments:  
  `python run_inference_hydra.py -m experiment=env_wikipedia_raw_html,env_dbpedia_raw_turtle input_folder=... output_folder=...`
- **Versionable** — Configs live in YAML under version control; `.env` can stay for secrets only (e.g. `OPENAI_API_KEY`).

**Minimal integration:** Hydra composes the chosen config; at startup you push the experiment slice into `os.environ`. Existing code in `agent/resource_transform.py`, `agent/context_compression.py`, and `benchmark/application/inference.py` keeps reading from `os.environ`, so no refactor of those modules is required.

Input/output folders are chosen from `config/config.yaml` **dataset_paths** based on each experiment's **dataset** (`dbpedia` | `wikipedia`), so you can run without passing paths. Override with `input_folder=...` and `output_folder=...` on the CLI if needed.

**Model selection:** Use the config group **model** to run the same experiment with different LLMs (e.g. `model=llama_3_3_70b`, `model=devstral_2_123b`). Output is written to a subfolder by model (e.g. `out/dbpedia/llama-3.3-70b-instruct/`) so results do not overwrite. See `config/model/` for available models.

**Data source selection:** Use the config group **datasource** to switch which dataset paths are used (e.g. `datasource=experiment_10`, `datasource=datasets_04`). Each datasource defines `dataset_paths` (dbpedia and wikipedia input/output folders). Available: `experiment_10` (evaluation/experiments/10_*), `datasets_02`, `datasets_03`, `datasets_04`, `datasets_05` (from the `datasets/` folder). See `config/datasource/`.

See `config/experiment/`, `config/model/`, `config/datasource/`, and `run_inference_hydra.py` for the concrete setup.

---

## Option 2: CLI flags only

Extend `benchmark/cli/run_inference.py` with optional arguments (e.g. `--representation-format`, `--rdf-representation`, `--pruning-method`, `--modify-context`, `--context-compression`). Before creating the use case, set `os.environ` from these args when provided.

**Pros:** No new dependency; quick to add.  
**Cons:** Long CLI; no first-class “experiment presets” unless you add a small preset loader (e.g. YAML/JSON with named presets).

---

## Option 3: Dotenv preset files

Keep using `python-dotenv`. Add multiple files (e.g. `.env.semantic-outgoing-turtle`, `.env.compression-jsonld`) and run with:

```bash
env $(grep -v '^#' .env.semantic-outgoing-turtle | xargs) python -m benchmark.cli.run_inference ...
```

Or a small wrapper script that loads a chosen `.env.*` and then runs inference.

**Pros:** No code change; only new env files.  
**Cons:** No override from CLI; multirun/sweeps are manual.

---

## Recommendation

Use **Hydra** if you want structured, named experiments plus CLI overrides and multirun. Use **CLI flags** for a minimal improvement without new deps. Use **dotenv presets** if you want the absolute minimum change (only new env files and a shell wrapper).
