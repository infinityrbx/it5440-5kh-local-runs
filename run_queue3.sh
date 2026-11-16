#!/bin/bash
# Night 3 queue (15->16/11), last local batch for IT5440 5-KH. qwen3.5:9b only, thinking off via
# Ollama's native API (OLLAMA_NATIVE=1 in run_eval.py; pilot.py already uses it). Restart-safe.
#   cd "<project folder>" && mkdir -p queue3 && nohup bash run_queue3.sh > queue3/queue.log 2>&1 &
# Progress: queue3/STATUS. Stop: kill $(cat queue3/queue.pid); pkill -f run_eval.py; pkill -f compare_pilot.py; pkill -f pilot.py

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1
mkdir -p queue3
echo $$ > queue3/queue.pid
caffeinate -i -w $$ &

export OLLAMA_NATIVE=1 OLLAMA_NUM_CTX=24576 LLM_BASE_URL=http://localhost:11434/v1 LLM_API_KEY=ollama
M=qwen3.5:9b

step() {
  local n=$1 name=$2; shift 2
  if [ -f "queue3/step$n.done" ]; then echo "$(date '+%F %T') step $n $name: already done, skipped" >> queue3/STATUS; return 0; fi
  echo "$(date '+%F %T') step $n $name: START" >> queue3/STATUS
  ( "$@" ) > "queue3/step$n.log" 2>&1
  local rc=$?
  if [ $rc -eq 0 ]; then touch "queue3/step$n.done"; echo "$(date '+%F %T') step $n $name: DONE" >> queue3/STATUS
  else echo "$(date '+%F %T') step $n $name: FAILED (exit $rc, see queue3/step$n.log)" >> queue3/STATUS; fi
  return $rc
}

# 1. toolz, oracle (~10 min) + guard (thinking off, ANSWER: format)
step 1 toolz-q35-oracle bash -c "cd toolz && python3 experiments/run_eval.py --data experiments/data/toolz_final_clean \
  --tasks semantic --k-groups 1,3 --filler-seed 0 --seed 7 --n 40 --lengths 0 --workers 1 \
  --model $M --out experiments/results/local_q35n_0.jsonl"
step 2 toolz-q35-guard python3 queue2_check.py toolz/experiments/results/local_q35n_0.jsonl
if [ $? -eq 0 ]; then
  # 3. toolz, 4k (~1.5-2 h), same items/filler as qwen2.5-coder's local_q25c_4k
  step 3 toolz-q35-4k bash -c "cd toolz && python3 experiments/run_eval.py --data experiments/data/toolz_final_clean \
    --tasks semantic --k-groups 1,3 --filler-seed 0 --seed 7 --n 40 --lengths 4000 --workers 1 \
    --model $M --out experiments/results/local_q35n_4k.jsonl"
else
  echo "$(date '+%F %T') step 3 toolz-q35-4k: SKIPPED (guard failed, see queue3/step2.log)" >> queue3/STATUS
fi

# 4. D2 at 4k on the 30 seed-3 puzzles -> paired 4k vs 16k on all 50 (~3.5 h)
step 4 d2-q35-4k-seed3 bash -c "cd pilot && python3 pilot.py --model $M --k 5 --depth 2 --tokens 4000 \
  --n 30 --cot --max-out 2048 --seed 3"

# 5. D1 at 4k (~1.5 h), same items as d1_q35n_16k
step 5 d1-q35-4k bash -c "cd d1 && python3 experiments/compare_pilot.py --arms semtrace --lengths 4000 \
  --workers 1 --model $M --out experiments/results/d1_q35n_4k.jsonl"

echo "$(date '+%F %T') QUEUE FINISHED" >> queue3/STATUS
ollama stop qwen3.5:9b >/dev/null 2>&1
rm -f queue3/queue.pid
