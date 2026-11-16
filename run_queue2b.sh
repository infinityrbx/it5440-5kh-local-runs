#!/bin/bash
# Follow-up to run_queue2.sh: D1 on qwen3.5:9b through Ollama's NATIVE API (think:false works there;
# the /v1 endpoint ignored it, so the first D1 attempt only produced thinking and empty answers).
# Waits for run_queue2.sh to finish, then runs. Restart-safe (queue2b/stepN.done).
#   cd "<project folder>" && mkdir -p queue2b && nohup bash run_queue2b.sh > queue2b/queue.log 2>&1 &
# Progress: queue2b/STATUS. Stop: kill $(cat queue2b/queue.pid); pkill -f compare_pilot.py

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1
mkdir -p queue2b
echo $$ > queue2b/queue.pid
caffeinate -i -w $$ &

# wait for the first queue (it removes queue2/queue.pid when it finishes)
while [ -f queue2/queue.pid ] && kill -0 "$(cat queue2/queue.pid)" 2>/dev/null; do sleep 60; done
echo "$(date '+%F %T') queue2 finished, starting" >> queue2b/STATUS

export OLLAMA_NATIVE=1 OLLAMA_NUM_CTX=24576 LLM_BASE_URL=http://localhost:11434/v1 LLM_API_KEY=ollama
M=qwen3.5:9b

step() {
  local n=$1 name=$2; shift 2
  if [ -f "queue2b/step$n.done" ]; then echo "$(date '+%F %T') step $n $name: already done, skipped" >> queue2b/STATUS; return 0; fi
  echo "$(date '+%F %T') step $n $name: START" >> queue2b/STATUS
  ( "$@" ) > "queue2b/step$n.log" 2>&1
  local rc=$?
  if [ $rc -eq 0 ]; then touch "queue2b/step$n.done"; echo "$(date '+%F %T') step $n $name: DONE" >> queue2b/STATUS
  else echo "$(date '+%F %T') step $n $name: FAILED (exit $rc, see queue2b/step$n.log)" >> queue2b/STATUS; fi
  return $rc
}

# 1. D1 oracle via native API (~5 min) + guard
step 1 d1-q35-oracle bash -c "cd d1 && python3 experiments/compare_pilot.py --arms semtrace --lengths 0 \
  --workers 1 --model $M --out experiments/results/d1_q35n_0.jsonl"
step 2 d1-q35-guard python3 queue2_check.py d1/experiments/results/d1_q35n_0.jsonl
if [ $? -eq 0 ]; then
  # 3. D1 at 16k (~4-5 h)
  step 3 d1-q35-16k bash -c "cd d1 && python3 experiments/compare_pilot.py --arms semtrace --lengths 16000 \
    --workers 1 --model $M --out experiments/results/d1_q35n_16k.jsonl"
else
  echo "$(date '+%F %T') step 3 d1-q35-16k: SKIPPED (guard failed, see queue2b/step2.log)" >> queue2b/STATUS
fi

echo "$(date '+%F %T') QUEUE FINISHED" >> queue2b/STATUS
ollama stop qwen3.5:9b >/dev/null 2>&1
rm -f queue2b/queue.pid
