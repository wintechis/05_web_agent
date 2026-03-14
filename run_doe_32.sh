#!/usr/bin/env bash
# Run all 32 full-factorial DOE experiments for a given model.
#
# Usage:
#   ./run_doe_32.sh                                    # defaults: model=qwen3_coder_30b, datasource=experiment_10
#   ./run_doe_32.sh --model llama_3_3_70b              # different model
#   ./run_doe_32.sh --datasource datasets_04           # different datasource
#   ./run_doe_32.sh --model llama_3_3_70b --datasource datasets_04
#   ./run_doe_32.sh --dry-run                          # print commands without executing
#
# Each experiment runs sequentially. Output goes to out/{dataset}/{model_slug}/{experiment_name}/
# Logs are written to logs/doe_{experiment_name}.log

set -euo pipefail

MODEL="qwen3_coder_30b"
DATASOURCE="experiment_10"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model)      MODEL="$2"; shift 2 ;;
        --datasource) DATASOURCE="$2"; shift 2 ;;
        --dry-run)    DRY_RUN=true; shift ;;
        -h|--help)
            echo "Usage: $0 [--model MODEL] [--datasource DATASOURCE] [--dry-run]"
            echo ""
            echo "Runs all 32 full-factorial DOE experiments."
            echo ""
            echo "Options:"
            echo "  --model MODEL          Hydra model config name (default: qwen3_coder_30b)"
            echo "  --datasource DATASOURCE Hydra datasource config name (default: experiment_10)"
            echo "  --dry-run              Print commands without executing"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Full factorial: 4 environment×format cells × 2^3 agent-side interventions = 32
EXPERIMENTS=(
    # Wikipedia × HTML (8)
    doe_01_wiki_html
    doe_02_wiki_html_clean
    doe_03_wiki_html_filter
    doe_04_wiki_html_compress
    doe_05_wiki_html_clean_filter
    doe_06_wiki_html_clean_compress
    doe_07_wiki_html_filter_compress
    doe_08_wiki_html_clean_filter_compress
    # DBpedia × HTML (8)
    doe_09_db_html
    doe_10_db_html_clean
    doe_11_db_html_filter
    doe_12_db_html_compress
    doe_13_db_html_clean_filter
    doe_14_db_html_clean_compress
    doe_15_db_html_filter_compress
    doe_16_db_html_clean_filter_compress
    # DBpedia × Turtle (8)
    doe_17_db_turtle
    doe_18_db_turtle_clean
    doe_19_db_turtle_filter
    doe_20_db_turtle_compress
    doe_21_db_turtle_clean_filter
    doe_22_db_turtle_clean_compress
    doe_23_db_turtle_filter_compress
    doe_24_db_turtle_clean_filter_compress
    # DBpedia × JSON-LD (8)
    doe_25_db_jsonld
    doe_26_db_jsonld_clean
    doe_27_db_jsonld_filter
    doe_28_db_jsonld_compress
    doe_29_db_jsonld_clean_filter
    doe_30_db_jsonld_clean_compress
    doe_31_db_jsonld_filter_compress
    doe_32_db_jsonld_clean_filter_compress
)

LOGDIR="logs"
mkdir -p "$LOGDIR"

TOTAL=${#EXPERIMENTS[@]}
echo "=== Full Factorial DOE: $TOTAL experiments ==="
echo "Model:      $MODEL"
echo "Datasource: $DATASOURCE"
echo ""

PASSED=0
FAILED=0
FAILED_LIST=()

for i in "${!EXPERIMENTS[@]}"; do
    EXP="${EXPERIMENTS[$i]}"
    NUM=$((i + 1))
    LOGFILE="$LOGDIR/doe_${EXP}.log"

    echo "[$NUM/$TOTAL] Running experiment=$EXP ..."

    CMD="python run_inference_hydra.py experiment=$EXP model=$MODEL datasource=$DATASOURCE"

    if $DRY_RUN; then
        echo "  [dry-run] $CMD"
        continue
    fi

    if $CMD > "$LOGFILE" 2>&1; then
        echo "  DONE (log: $LOGFILE)"
        PASSED=$((PASSED + 1))
    else
        echo "  FAILED (log: $LOGFILE)"
        FAILED=$((FAILED + 1))
        FAILED_LIST+=("$EXP")
    fi
done

if $DRY_RUN; then
    echo ""
    echo "Dry run complete. No experiments were executed."
    exit 0
fi

echo ""
echo "=== Summary ==="
echo "Passed: $PASSED / $TOTAL"
echo "Failed: $FAILED / $TOTAL"
if [[ $FAILED -gt 0 ]]; then
    echo "Failed experiments:"
    for exp in "${FAILED_LIST[@]}"; do
        echo "  - $exp"
    done
    exit 1
fi
