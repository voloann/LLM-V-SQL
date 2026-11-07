#!/bin/sh
# Runs Direct and V-SQL on all 500 questions with the main configuration (paper views, described schema) on the
# local models, one model at a time and fastest first. Luna has its own run: scripts/run_view_extension_benchmark.sh.
# A stopped run resumes from its trace, so running this again only does the missing questions.
# usage: scripts/run_main_config_benchmark.sh
set -u
cd "$(dirname "$0")/.."
PORT=8770
for ENTRY in qwen3_4b_500_paper:qwen3-4b-2507-16k qwen7b_500_paper:qwen2.5-coder-16k qwen32b_500_paper:qwen2.5-coder-32b-16k; do
  NAME="${ENTRY%%:*}"
  MODEL="${ENTRY#*:}"
  OUT="outputs/$NAME"
  mkdir -p "$OUT"
  cp -n outputs/luna_500_described/questions.json "$OUT/questions.json"
  for ATTEMPT in 1 2 3 4; do
    .venv/bin/python -u scripts/run_benchmark.py "$OUT" "$MODEL" --view-mode paper --schema-mode described \
      --budget 0 --port "$PORT" --label "$MODEL, view paper" && break
    echo "attempt $ATTEMPT for $MODEL failed"
    sleep 60
  done
  # Free the model's memory before the next one loads.
  ollama stop "$MODEL" || true
  PORT=$((PORT + 1))
done
