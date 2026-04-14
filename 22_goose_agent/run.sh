#!/bin/bash
# Goose Agent Runner
# Usage:
#   ./run.sh "タスクの説明"
#   ./run.sh --recipe planner "タスクの説明"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RECIPE="basic_task"
TASK=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --recipe)
            RECIPE="$2"
            shift 2
            ;;
        *)
            TASK="$1"
            shift
            ;;
    esac
done

if [ -z "$TASK" ]; then
    echo "Usage: $0 [--recipe basic_task|planner] \"task description\""
    echo ""
    echo "Recipes:"
    echo "  basic_task  - シンプルなタスク実行 (default)"
    echo "  planner     - Plan→Generate→Evaluate 3段階フロー"
    exit 1
fi

case $RECIPE in
    basic_task)
        goose run \
            --provider ollama \
            --model "qwen3.5:9b" \
            --recipe "$SCRIPT_DIR/recipes/basic_task.yaml" \
            --params "task=$TASK" \
            --no-session \
            --quiet \
            --no-profile \
            --with-builtin developer
        ;;
    planner)
        goose run \
            --provider ollama \
            --model "qwen3.5:9b" \
            --recipe "$SCRIPT_DIR/recipes/planner_flow.yaml" \
            --params "task=$TASK" \
            --params "workdir=$(pwd)" \
            --no-session \
            --quiet \
            --no-profile \
            --with-builtin developer \
            --max-turns 15
        ;;
    *)
        echo "Unknown recipe: $RECIPE"
        exit 1
        ;;
esac
