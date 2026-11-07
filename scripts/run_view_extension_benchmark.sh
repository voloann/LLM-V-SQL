#!/bin/sh
# Runs V-SQL on all 500 questions with the given view sets. Direct traces are reused from
# luna_500_described because Direct's prompt does not depend on the views, so only V-SQL calls cost money.
# usage: scripts/run_view_extension_benchmark.sh [budget_per_run_usd] [view_sets]
set -u
cd "$(dirname "$0")/.."
BUDGET="${1:-0.8}"
MODES="${2:-fk gold paper}"
PORT=8766
for MODE in $MODES; do
  OUT="outputs/luna_500_$MODE"
  mkdir -p "$OUT/direct" "$OUT/vsql"
  cp -n outputs/luna_500_described/questions.json "$OUT/questions.json"
  cp -n outputs/luna_500_described/direct/trace.jsonl "$OUT/direct/trace.jsonl"
  # A run stopped by a network error resumes from its trace, so retry a few times.
  for ATTEMPT in 1 2 3 4; do
    .venv/bin/python -u scripts/run_benchmark.py "$OUT" gpt-6-luna --view-mode "$MODE" --schema-mode described \
      --budget "$BUDGET" --port "$PORT" --label "gpt-6-luna, view $MODE" && break
    echo "attempt $ATTEMPT for $MODE failed"
    sleep 60
  done
  PORT=$((PORT + 1))
done
