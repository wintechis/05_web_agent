"""Hydra-based entry point for inference: switch experiments via config/CLI without editing .env.

Input/output folders are chosen from dataset_paths based on the experiment's dataset (dbpedia | wikipedia).

Usage:
  # Use dataset defaults (dbpedia for semantic_outgoing_turtle)
  python run_inference_hydra.py

  # Switch experiment → dataset and paths follow from config
  python run_inference_hydra.py experiment=env_wikipedia_raw_html

  # Override dataset paths from CLI
  python run_inference_hydra.py experiment=semantic_outgoing_turtle input_folder=other/questions output_folder=other/out

  # Multirun: sweep over experiments (each uses its dataset's paths)
  python run_inference_hydra.py -m experiment=env_wikipedia_raw_html,env_dbpedia_raw_turtle

  # Different LLM model (config group "model"); output goes to e.g. out/dbpedia/llama-3.3-70b-instruct
  python run_inference_hydra.py model=llama_3_3_70b
  python run_inference_hydra.py experiment=env_wikipedia_raw_html model=devstral_2_123b

  # Multirun over models
  python run_inference_hydra.py -m model=qwen3_coder_30b,llama_3_3_70b,glm_4_7

  # Different data source (config group "datasource"): experiment_10, datasets_02, datasets_03, datasets_04, datasets_05
  python run_inference_hydra.py datasource=datasets_04
  # Sweep over multiple datasources (or experiments/models): add -m before the comma-separated key
  python run_inference_hydra.py -m datasource=datasets_02,datasets_03,datasets_04 experiment=env_wikipedia_raw_html model=llama_3_3_70b
  python run_inference_hydra.py experiment=env_wikipedia_raw_html datasource=datasets_03 model=llama_3_3_70b

Load .env for secrets (OPENAI_API_KEY, etc.) before running; this script sets experiment and model env from Hydra config.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from omegaconf import DictConfig, OmegaConf

# Load .env first so OPENAI_API_KEY etc. are set; we overlay experiment config below
load_dotenv()

# Hydra must be imported after dotenv so that the decorator runs with env ready
import hydra  # noqa: E402
from benchmark.application.inference import RunInferenceUseCase  # noqa: E402
from agent.telemetry import TRACE_DIR_ENV  # noqa: E402


# Keys in experiment YAML -> env var name; value is set as string (bool -> "true"/"false")
_EXPERIMENT_ENV_MAP = {
    "modify_context": ("MODIFY_CONTEXT", lambda v: "true" if v else "false"),
    "context": ("CONTEXT", str),
    "representation_format": ("REPRESENTATION_FORMAT", str),
    "rdf_representation": ("RDF_REPRESENTATION", str),
    "pruning_method": ("PRUNING_METHOD", str),
    "context_compression": ("CONTEXT_COMPRESSION", lambda v: "true" if v else "false"),
    "max_token_for_model": ("MAX_TOKEN_FOR_MODEL", str),
}


def _get_experiment_config(cfg: DictConfig) -> DictConfig:
    """Return the config slice that holds experiment keys (Hydra nests them under cfg.experiment)."""
    exp = OmegaConf.select(cfg, "experiment")
    if exp is not None and OmegaConf.is_config(exp) and "dataset" in exp:
        return exp
    return cfg


def _apply_experiment_to_env(experiment_cfg: DictConfig) -> None:
    """Set os.environ from experiment-related config keys so existing code keeps working."""
    for key, (env_key, coerce) in _EXPERIMENT_ENV_MAP.items():
        if key not in experiment_cfg or OmegaConf.is_missing(experiment_cfg, key):
            continue
        val = OmegaConf.select(experiment_cfg, key)
        if val is None:
            continue
        os.environ[env_key] = coerce(val)


def _model_slug(model_id: str) -> str:
    """Filesystem-safe slug from model id (e.g. for output subfolder)."""
    return str(model_id).replace("/", "_").strip() or "unknown"


def _get_model_config(cfg: DictConfig) -> DictConfig | None:
    """Return the config slice for model (Hydra nests it under cfg.model)."""
    model_cfg = OmegaConf.select(cfg, "model")
    if model_cfg is not None and OmegaConf.is_config(model_cfg) and "openai_model_id" in model_cfg:
        return model_cfg
    return None


def _apply_model_to_env(cfg: DictConfig) -> None:
    """Set OPENAI_MODEL_ID from config so get_openai_inference_model() uses the chosen model."""
    model_cfg = _get_model_config(cfg)
    if model_cfg is not None:
        model_id = OmegaConf.select(model_cfg, "openai_model_id")
        if model_id is not None and not OmegaConf.is_missing(model_cfg, "openai_model_id"):
            os.environ["OPENAI_MODEL_ID"] = str(model_id)


def _get_dataset_paths(cfg: DictConfig):
    """Return dataset_paths from selected datasource or top-level (Hydra nests under cfg.datasource)."""
    datasource = OmegaConf.select(cfg, "datasource")
    if datasource is not None and OmegaConf.is_config(datasource):
        p = OmegaConf.select(datasource, "dataset_paths")
        if p is not None:
            return p
    return OmegaConf.select(cfg, "dataset_paths")


def _resolve_paths(cfg: DictConfig) -> tuple[Path, Path]:
    """Resolve input_dir and output_dir from config; use dataset_paths when not overridden."""
    experiment_cfg = _get_experiment_config(cfg)
    dataset = OmegaConf.select(experiment_cfg, "dataset") or OmegaConf.select(cfg, "dataset")
    paths = _get_dataset_paths(cfg)
    input_raw = OmegaConf.select(cfg, "input_folder")
    output_raw = OmegaConf.select(cfg, "output_folder")
    use_dataset_defaults = (
        input_raw is None
        or OmegaConf.is_missing(cfg, "input_folder")
        or output_raw is None
        or OmegaConf.is_missing(cfg, "output_folder")
    )
    if use_dataset_defaults and paths is None:
        raise ValueError(
            "dataset_paths not found; select a datasource, e.g. datasource=experiment_10 or datasource=datasets_04"
        )
    if use_dataset_defaults and dataset is not None and paths is not None:
        if dataset not in paths:
            raise ValueError(
                f"dataset={dataset!r} not in dataset_paths; allowed: {list(paths.keys())}"
            )
        input_dir = Path(paths[dataset].input_folder).resolve()
        output_dir = Path(paths[dataset].output_folder).resolve()
    else:
        if input_raw is None or OmegaConf.is_missing(cfg, "input_folder"):
            raise ValueError("Set input_folder in config or pass input_folder=... on CLI")
        if output_raw is None or OmegaConf.is_missing(cfg, "output_folder"):
            raise ValueError("Set output_folder in config or pass output_folder=... on CLI")
        input_dir = Path(str(input_raw)).resolve()
        output_dir = Path(str(output_raw)).resolve()
    # Subfolder by model so different models do not overwrite
    model_cfg = _get_model_config(cfg)
    if model_cfg is not None:
        model_id = OmegaConf.select(model_cfg, "openai_model_id")
        if model_id is not None and not OmegaConf.is_missing(model_cfg, "openai_model_id"):
            output_dir = output_dir / _model_slug(str(model_id))
    return input_dir, output_dir


@hydra.main(version_base=None, config_path="config", config_name="config")
def main(cfg: DictConfig) -> None:
    experiment_cfg = _get_experiment_config(cfg)
    _apply_experiment_to_env(experiment_cfg)
    _apply_model_to_env(cfg)

    input_dir, output_dir = _resolve_paths(cfg)
    trace_dir_raw = OmegaConf.select(cfg, "trace_dir")
    if trace_dir_raw is None or OmegaConf.is_missing(cfg, "trace_dir"):
        trace_dir = output_dir / "traces"
    else:
        trace_dir = Path(str(trace_dir_raw)).resolve()

    trace_dir_str = os.getenv(TRACE_DIR_ENV, str(trace_dir))
    use_case = RunInferenceUseCase()
    use_case.run(
        input_dir=str(input_dir),
        output_dir=str(output_dir),
        trace_dir=trace_dir_str,
    )


if __name__ == "__main__":
    main()
