#!/bin/bash
# Overnight queue for IT5440 5-KH: runs every step one after another, fastest first.
# It is independent of any Claude / Remote Control session. Start it once with:
#   cd "<project folder>" && nohup bash run_queue.sh > queue/queue.log 2>&1 &
# Progress: queue/STATUS (one line per step) and queue/stepN.log.
# Restart-safe: a step that finished leaves queue/stepN.done and is skipped next time.
# Stop everything: kill $(cat queue/queue.pid); pkill -f run_eval.py; pkill -f compare_pilot.py; pkill -f pilot.py

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1
mkdir -p queue
echo $$ > queue/queue.pid
caffeinate -i -w $$ &                      # keep the Mac awake while this script runs

export LLM_BASE_URL=http://localhost:11434/v1 LLM_API_KEY=ollama
M=qwen25c-24k                              # qwen2.5-coder:7b with a 24k context window (step 0)

step() {                                   # step <n> <name> <command...>
  local n=$1 name=$2; shift 2
  if [ -f "queue/step$n.done" ]; then echo "$(date '+%F %T') step $n $name: already done, skipped" >> queue/STATUS; return; fi
  echo "$(date '+%F %T') step $n $name: START" >> queue/STATUS
  ( "$@" ) > "queue/step$n.log" 2>&1
  local rc=$?
  if [ $rc -eq 0 ]; then touch "queue/step$n.done"; echo "$(date '+%F %T') step $n $name: DONE" >> queue/STATUS
  else echo "$(date '+%F %T') step $n $name: FAILED (exit $rc, see queue/step$n.log)" >> queue/STATUS; fi
}

# 0. model alias with a large context window (the OpenAI-compatible endpoint cannot set num_ctx per call)
step 0 make-model bash -c 'printf "FROM qwen2.5-coder:7b\nPARAMETER num_ctx 24576\nPARAMETER temperature 0\n" > queue/Modelfile && ollama create qwen25c-24k -f queue/Modelfile'

# 1. toolz, oracle only (~10 min)
step 1 toolz-oracle bash -c "cd toolz && python3 experiments/run_eval.py --data experiments/data/toolz_final_clean \
  --tasks semantic --k-groups 1,3 --filler-seed 0 --seed 7 --n 40 --lengths 0 --workers 1 \
  --model $M --out experiments/results/local_q25c_0.jsonl"

# 2. toolz, 4k (~1.5 h)
step 2 toolz-4k bash -c "cd toolz && python3 experiments/run_eval.py --data experiments/data/toolz_final_clean \
  --tasks semantic --k-groups 1,3 --filler-seed 0 --seed 7 --n 40 --lengths 4000 --workers 1 \
  --model $M --out experiments/results/local_q25c_4k.jsonl"

# 3. D1 SemTrace 2/4 digits, oracle + 4k (~1.5 h)
step 3 d1-oracle-4k bash -c "cd d1 && python3 experiments/compare_pilot.py --arms semtrace --lengths 0,4000 \
  --workers 1 --model $M --out experiments/results/d1_q25c_0_4k.jsonl"

# 4. D1 SemTrace 2/4 digits, 16k (~5 h)
step 4 d1-16k bash -c "cd d1 && python3 experiments/compare_pilot.py --arms semtrace --lengths 16000 \
  --workers 1 --model $M --out experiments/results/d1_q25c_16k.jsonl"

# 5. D2 (pilot.py v5, fixed filler), qwen3.5:9b, k=5, 16k, n=20 (~6-8 h)
step 5 d2-16k bash -c "cd pilot && python3 pilot.py --model qwen3.5:9b --k 5 --depth 2 --tokens 16000 \
  --n 20 --cot --max-out 2048 --seed 2"

echo "$(date '+%F %T') QUEUE FINISHED" >> queue/STATUS
ollama stop qwen25c-24k >/dev/null 2>&1; ollama stop qwen3.5:9b >/dev/null 2>&1
rm -f queue/queue.pid
