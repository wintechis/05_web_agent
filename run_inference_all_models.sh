#!/usr/bin/env bash
# Run inference multirun (datasource sweep) for each model in config/model/.
# Usage: ./run_inference_all_models.sh [optional extra Hydra overrides]
# Example: ./run_inference_all_models.sh
# Example: ./run_inference_all_models.sh experiment=semantic_outgoing_turtle

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DATASOURCES="datasets_02,datasets_03,datasets_04,datasets_05"
EXPERIMENT="env_wikipedia_raw_html"
# Space-separated list of model names to skip. Override via env: BLACKLIST="model_a model_b" ./run_inference_all_models.sh
BLACKLIST="${BLACKLIST:-}"
# Example: BLACKLIST="mistral_large_3_675b glm_4_7"

EXTRA_OVERRIDES=("$@")

for yaml in config/model/*.yaml; do
  model="$(basename "$yaml" .yaml)"
  if [[ " ${BLACKLIST} " == *" ${model} "* ]]; then
    echo "========== Skipping blacklisted model=$model =========="
    continue
  fi
  echo "========== Running model=$model =========="
  python run_inference_hydra.py -m \
    "datasource=${DATASOURCES}" \
    "experiment=${EXPERIMENT}" \
    "model=${model}" \
    "${EXTRA_OVERRIDES[@]}"
done

echo "========== All models finished =========="
