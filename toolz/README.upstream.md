# toolz – real-code benchmark (copied from the group repo)

This folder is a copy of the group's main benchmark, taken from the group repository
at commit `cf1f333` (12/11/2026). The scripts and data are unchanged.

## Dataset: `experiments/data/toolz_final_clean_*`

- **304 items** from the `toolz` 1.0.0 library: 176 with k_core = 1 (one function needed) and 128 with k_core = 3 (three functions).
- How the items were made:
  - Sources are doctest examples plus synthetic chains of 1–3 toolz functions.
  - Constants were changed so answers can't be copied from the docs.
  - Every function and class was alpha-renamed to `fn_NNN` / `Cls_NNN`, then each item was re-executed to confirm the answer is unchanged.
- Filters applied:
  - Oracle-solvable 3/3: the model answers correctly when given only the needed code.
  - Not guessable without code (no-context filter).
- Files:
  - `_items.jsonl`: setup, expression, answer and core fragments.
  - `_units.json`: renamed source of every unit, which is also the filler.
  - `_mapping.json`: original name → `fn_NNN`.

Example (k = 1):

```python
def fn_848(predicate, d, factory=dict):
    rv = factory()
    for (k, v) in d.items():
        if predicate(k):
            rv[k] = v
    return rv
# iseven = lambda x: x % 5 == 2
# fn_848(iseven, {3: 5, 5: 6, 6: 7, 7: 8})  ->  {7: 8}
```

## Scripts (`experiments/`)

| File | Role |
|---|---|
| `build_items.py` | Builds items from doctests and synthetic chains, mutates constants, runs a static backward slice, records a dynamic call trace (needs `pip install toolz==1.0.0`) |
| `rename.py` | Alpha-renames items and re-checks them by execution |
| `nocontext_filter.py` | Asks each item without code, to find guessable ones |
| `build_contexts.py` | Places the needed code at start/middle/end (or cluster/spread for k ≥ 2) in filler of a target length. The filler is **layout-independent** and logged as `filler_hash` |
| `run_eval.py` | Calls an OpenAI-compatible endpoint with thinking disabled, then scores the answers |
| `summarize.py` | Accuracy per task × layout, plus checks: thinking leak and real vs. estimated tokens |

You only need the last three to run the benchmark, and they use only the standard library.

## Group results (`experiments/results/`)

`main_{ds|qw}_{0|4k|16k|32k}.jsonl` hold the corrected main run: DeepSeek-V4-Flash and Qwen3.6-27B,
n = 40 per k-group, filler-seed 0, seed 7. `main_qw_16k_bf.jsonl` is a backfill of 7 items that hit rate limits.
`pilot-12-11-2026.md` is the group's write-up. Its findings: no lost-in-the-middle (p ≥ 0.6), recency (end ≥ start in 10/10
cells, about +7 pp), and a k1 → k3 gap that is mostly item difficulty.

```bash
python3 experiments/summarize.py experiments/results/main_ds_16k.jsonl
```

## Run

```bash
# check only: 80 items, 280 calls at 16k
python3 experiments/run_eval.py --data experiments/data/toolz_final_clean --tasks semantic \
    --k-groups 1,3 --filler-seed 0 --seed 7 --n 40 --lengths 16000 --dry-run --out /tmp/t.jsonl

# same design as the group, on local Ollama (OpenAI-compatible endpoint)
export LLM_BASE_URL=http://localhost:11434/v1 LLM_API_KEY=ollama
python3 experiments/run_eval.py --data experiments/data/toolz_final_clean --tasks semantic \
    --k-groups 1,3 --filler-seed 0 --seed 7 --n 40 --lengths 0,4000 --workers 1 \
    --model qwen2.5-coder:7b --out experiments/results/local_qwen25coder7b.jsonl
```

Notes:
- The prompts ask for `ANSWER: <output>` with no explanation, so this is a direct-answer setting.
- With Ollama, the context window must fit the prompt (16k prompts need `num_ctx` ≥ about 20k). Otherwise
  the prompt is cut without warning. Check that `usage.prompt_tokens` is close to `est_tokens`.
- Items were selected by oracle calibration on DeepSeek, so a weaker local model will score lower at
  oracle. Run `--lengths 0` first to see that model's own ceiling.
