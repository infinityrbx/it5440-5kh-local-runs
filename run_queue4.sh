#!/usr/bin/env bash
# Overnight queue 4: D2 SemTrace-Dep on qwen2.5-coder:7b (pilot.py v5), same settings and puzzles as the
# qwen3.5 runs (k=5, depth 2, CoT, max 2048 output tokens, seeds 2 and 3 = 50 puzzles), 4k first, then 16k.
# Restart-safe per step. Progress: queue4/STATUS.  Start: mkdir -p queue4 && nohup bash run_queue4.sh > queue4/queue.log 2>&1 &
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1
mkdir -p queue4
echo $$ > queue4/queue.pid
caffeinate -i -w $$ &
M=qwen2.5-coder:7b
step() {                                   # step <n> <name> <tokens> <n> <seed> <out>
  local n=$1 name=$2 tok=$3 cnt=$4 seed=$5 out=$6
  if [ -f "queue4/step$n.done" ]; then echo "$(date '+%F %T') step $n $name: already done, skipped" >> queue4/STATUS; return 0; fi
  echo "$(date '+%F %T') step $n $name: START" >> queue4/STATUS
  local before; before=$(ls pilot/results/*.jsonl 2>/dev/null | sort)
  ( cd pilot && python3 pilot.py --model $M --k 5 --depth 2 --tokens $tok --n $cnt --cot --max-out 2048 --seed $seed ) \
      > "queue4/step$n.log" 2>&1
  local rc=$?
  local new; new=$(comm -13 <(echo "$before") <(ls pilot/results/*.jsonl | sort) | tail -1)
  if [ $rc -eq 0 ] && [ -n "$new" ] && [ "$(wc -l < "$new")" -eq $((cnt * 6)) ]; then
    mv "$new" "pilot/results/$out"; touch "queue4/step$n.done"
    echo "$(date '+%F %T') step $n $name: DONE -> pilot/results/$out" >> queue4/STATUS
  else
    echo "$(date '+%F %T') step $n $name: FAILED (exit $rc, file ${new:-none}, see queue4/step$n.log)" >> queue4/STATUS
  fi
}
ollama list | grep -q "^qwen2.5-coder:7b" || ollama pull qwen2.5-coder:7b
step 1 d2-q25c-4k-seed2  4000  20 2 q25c_4k_seed2_n20.jsonl
step 2 d2-q25c-4k-seed3  4000  30 3 q25c_4k_seed3_n30.jsonl
step 3 d2-q25c-16k-seed2 16000 20 2 q25c_16k_seed2_n20.jsonl
step 4 d2-q25c-16k-seed3 16000 30 3 q25c_16k_seed3_n30.jsonl
echo "$(date '+%F %T') QUEUE FINISHED" >> queue4/STATUS
ollama stop $M >/dev/null 2>&1
rm -f queue4/queue.pid
