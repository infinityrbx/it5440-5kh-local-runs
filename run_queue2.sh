#!/bin/bash
# Night 2 queue (14->15/11) for IT5440 5-KH. Same mechanics as run_queue.sh: one step after another,
# fastest first, independent of any Claude session, restart-safe (queue2/stepN.done).
#   cd "<project folder>" && mkdir -p queue2 && nohup bash run_queue2.sh > queue2/queue.log 2>&1 &
# Progress: queue2/STATUS. Stop: kill $(cat queue2/queue.pid); pkill -f compare_pilot.py; pkill -f pilot.py

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1
mkdir -p queue2
echo $$ > queue2/queue.pid
caffeinate -i -w $$ &

export LLM_BASE_URL=http://localhost:11434/v1 LLM_API_KEY=ollama
export LLM_EXTRA_BODY='{"think": false}'     # read by d1/experiments/run_eval.py (local addition)
M=qwen35-24k                                # qwen3.5:9b with a 24k context window (step 0)

step() {
  local n=$1 name=$2; shift 2
  if [ -f "queue2/step$n.done" ]; then echo "$(date '+%F %T') step $n $name: already done, skipped" >> queue2/STATUS; return 0; fi
  echo "$(date '+%F %T') step $n $name: START" >> queue2/STATUS
  ( "$@" ) > "queue2/step$n.log" 2>&1
  local rc=$?
  if [ $rc -eq 0 ]; then touch "queue2/step$n.done"; echo "$(date '+%F %T') step $n $name: DONE" >> queue2/STATUS
  else echo "$(date '+%F %T') step $n $name: FAILED (exit $rc, see queue2/step$n.log)" >> queue2/STATUS; fi
  return $rc
}

# 0. model alias with a 24k context window
step 0 make-model bash -c 'printf "FROM qwen3.5:9b\nPARAMETER num_ctx 24576\nPARAMETER temperature 0\n" > queue2/Modelfile && ollama create qwen35-24k -f queue2/Modelfile'

# 1. D1 oracle on qwen3.5:9b (~5 min) + guard: thinking must be off and answers in ANSWER: format
step 1 d1-q35-oracle bash -c "cd d1 && python3 experiments/compare_pilot.py --arms semtrace --lengths 0 \
  --workers 1 --model $M --out experiments/results/d1_q35_0.jsonl"
step 2 d1-q35-guard python3 queue2_check.py d1/experiments/results/d1_q35_0.jsonl
D1_OK=$?

# 3. D2 (pilot.py v5) at 4k on the SAME puzzles as last night's 16k run (seed 2) -> clean 4k vs 16k (~1.2 h)
step 3 d2-q35-4k bash -c "cd pilot && python3 pilot.py --model qwen3.5:9b --k 5 --depth 2 --tokens 4000 \
  --n 20 --cot --max-out 2048 --seed 2"

# 4. D1 at 16k on qwen3.5:9b (~4-5 h), only if the guard passed
if [ $D1_OK -eq 0 ]; then
  step 4 d1-q35-16k bash -c "cd d1 && python3 experiments/compare_pilot.py --arms semtrace --lengths 16000 \
    --workers 1 --model $M --out experiments/results/d1_q35_16k.jsonl"
else
  echo "$(date '+%F %T') step 4 d1-q35-16k: SKIPPED (guard failed, see queue2/step2.log)" >> queue2/STATUS
fi

# 5. D2 at 16k, 30 NEW puzzles (seed 3) -> pooled with last night's 20 gives n=50 (~6.5 h)
step 5 d2-q35-16k-more bash -c "cd pilot && python3 pilot.py --model qwen3.5:9b --k 5 --depth 2 --tokens 16000 \
  --n 30 --cot --max-out 2048 --seed 3"

echo "$(date '+%F %T') QUEUE FINISHED" >> queue2/STATUS
ollama stop qwen35-24k >/dev/null 2>&1; ollama stop qwen3.5:9b >/dev/null 2>&1
rm -f queue2/queue.pid
