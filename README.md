# IT5440 · 5-KH · Local model runs (code, logs, results)

Position-effect ("lost in the middle") runs on two **local** models through Ollama, on the three
datasets the group uses. Everything needed to check or rerun the numbers in `REPORT.md` is here.

| Model (Ollama tag) | Size | Runs |
|---|---|---|
| `qwen2.5-coder:7b` | 7B, Q4 | D2 (4k, 16k, n=50), D1 (no filler, 4k, 16k), toolz (no filler, 4k) |
| `qwen3.5:9b` | 9B, Q4, thinking **off** | D2 (4k, 16k, n=50), D1 (no filler, 4k, 16k), toolz (no filler, 4k) |

Hardware: Apple M2 Pro, 16 GB unified memory (about 10–11 GB usable by the GPU), Ollama 0.40,
`temperature 0`, context window 24,576 tokens. One request at a time.

## Layout

```
pilot/                 D2 SemTrace-Dep generator + runner (pilot.py v5, fixed filler), results/*.jsonl
d1/experiments/        D1 SemTrace: the group's builder/runner (copy of commit cf1f333) + our results
toolz/experiments/     toolz real-code benchmark: the group's pipeline and data + our results (local_*.jsonl)
run_queue*.sh          the overnight queues exactly as they were run (one step after another, restart-safe)
queue2_check.py        guard used by the queues: no thinking leak, answers in `ANSWER:` format
logs/queue*/           STATUS (timestamps of every step) and the stdout of each step
analysis/analyze.py    recomputes every number from the raw jsonl → analysis/SUMMARY.md, summary.json
REPORT.md              the write-up for the group
```

Every result line is one model call: prompt metadata, raw model output, parsed answer, score,
prompt/output token counts and a `filler_hash`. The filler hash is identical across positions
for each item (checked by `analyze.py`), so start / middle / end differ only in position.

## Local changes to the group's code

Only `run_eval.py` (same file in `d1/` and `toolz/`), all opt-in through environment variables:

* `OLLAMA_NATIVE=1` sends requests to Ollama's native `/api/chat` with `"think": false`.
  Ollama's OpenAI-compatible `/v1` endpoint **ignores** `think:false` for qwen3.5, so the
  model spent its whole output budget thinking and returned empty answers
  (`d1/experiments/results/d1_q35_0.jsonl`, kept as evidence, not used).
* `OLLAMA_NUM_CTX` sets the context window for those calls (default 24576).
* `LLM_EXTRA_BODY` merges extra JSON into `/v1` requests; `reasoning_chars` also reads `reasoning`.

With none of these set, the file behaves exactly like the group's version.

`d1/experiments/compare_pilot.py`: `partial()` now strips Markdown backticks before parsing, as
`run_eval.same_value` already did. The old version scored backticked answers 0 (26 of qwen2.5-coder's
60 no-filler answers). The `partial` field in the existing logs comes from the old version, so
`analysis/analyze.py` and `analysis/figures.py` recompute it from `pred` (`analysis/d1score.py`). It also scores the list inside answers wrapped as `array([...])` (numpy style) or written
with a doubled `ANSWER: ANSWER:` prefix (19 qwen3.5 rows); exact match stays strict.

`analysis/toolzscore.py` rescores toolz rows whose output repeats `ANSWER:` (`run_eval.semantic_pred` keeps the
second `ANSWER:` in `pred`; one qwen3.5 row). Everything else uses the group's `same_value()` unchanged.

`pilot/pilot.py` (D2) is ours. v5 builds the filler once per item and reuses it at every
position, gives every generated function a unique name, and sizes `num_ctx` from the target
length. It uses Ollama's native API with thinking off.

## Rerun

Requirements: Python 3.10+ (standard library only), Ollama running on `localhost:11434`.

```bash
ollama pull qwen2.5-coder:7b && ollama pull qwen3.5:9b

# D2 (one puzzle = 6 calls; ≈ 13 min per puzzle at 16k, ≈ 7 min at 4k, with CoT, on an M2 Pro)
cd pilot
python3 pilot.py --model qwen3.5:9b --k 5 --depth 2 --tokens 16000 --n 20 --cot --max-out 2048 --seed 2
python3 pilot.py --model qwen3.5:9b --k 5 --depth 2 --tokens 4000  --n 20 --cot --max-out 2048 --seed 2
#   (seed 3, --n 30 for the second half of the 50 puzzles)

# D1 and toolz with qwen3.5 (thinking off via the native API)
export OLLAMA_NATIVE=1 OLLAMA_NUM_CTX=24576 LLM_BASE_URL=http://localhost:11434/v1 LLM_API_KEY=ollama
cd d1 && python3 experiments/compare_pilot.py --arms semtrace --lengths 0,4000,16000 \
    --workers 1 --model qwen3.5:9b --out experiments/results/d1_q35n_rerun.jsonl
cd toolz && python3 experiments/run_eval.py --data experiments/data/toolz_final_clean --tasks semantic \
    --k-groups 1,3 --filler-seed 0 --seed 7 --n 40 --lengths 0,4000 --workers 1 \
    --model qwen3.5:9b --out experiments/results/local_q35n_rerun.jsonl
```

Or run a whole queue unattended: `mkdir -p queue3 && nohup bash run_queue3.sh > queue3/queue.log 2>&1 &`
(progress in `queue3/STATUS`). The qwen2.5-coder queue (`run_queue.sh`) uses a Modelfile alias with
`num_ctx 24576` because the `/v1` endpoint cannot set it per call.

Recompute all tables: `python3 analysis/analyze.py`.

## Run log

| Queue | Started → finished | Steps |
|---|---|---|
| `run_queue.sh` | 12/11 22:38 → 13/11 07:56 | toolz no filler + 4k, D1 no filler + 4k + 16k (qwen2.5-coder); D2 16k seed 2 (qwen3.5) |
| `run_queue2.sh` | 14/11 21:22 → 15/11 06:39 | D1 qwen3.5 via /v1 (**discarded**, thinking leak, guard stopped the 16k step); D2 4k seed 2; D2 16k seed 3 |
| `run_queue2b.sh` | 15/11 06:39 → 12:16 | D1 qwen3.5 via native API: no filler, guard, 16k |
| `run_queue3.sh` | 15/11 23:24 → 16/11 06:43 | toolz qwen3.5 no filler + guard + 4k; D2 4k seed 3; D1 qwen3.5 4k |
| `run_queue4.sh` | 16/11 22:18 → 17/11 11:10 | D2 qwen2.5-coder:7b: 4k seed 2 + 3, 16k seed 2 + 3 (`pilot/results/q25c_*.jsonl`) |

Exact timestamps per step are in `logs/queue*/STATUS`.
