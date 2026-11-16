# D1 – SemTrace-3/4 (re-implementation of [2])

This is a copy of the group's D1 code, taken from the group repo
the group repository at commit `cf1f333` (12/11/2026), folder `experiments/`.
The code itself is unchanged. It only has a new folder and this README.

## What D1 is

Each item is one function `f(x)`. It creates `arr = [0] * k`, with k between 4 and 10. Each slot is
assigned `arr[j] = x ± y`, and the assignment lines are shuffled. The question asks what `f(x)`
returns. `digits=2` follows [2]; `digits=4` is the group's H1 setting (x is 1000–9999 and |y| has up
to 4 digits). The item generator is `semtrace_item()` in `experiments/compare_pilot.py`, seeded by
`(digits, i, seed)`.

Example (digits=4, i=0, seed=11):

```python
def fn_45f8b1(x):
    arr = [0] * 4
    arr[3] = x + 8019
    arr[2] = x - 678
    arr[0] = x - 7089
    arr[1] = x - 499
    return arr
# fn_45f8b1(6233) -> [-856, 5734, 5555, 14252]
```

The filler is the anonymised toolz units (`data/toolz_anon_units.json`), then stdlib modules. The
layouts are start / middle / end, and length 0 means oracle (no filler). Tasks: semantic, plus
lexical (copy the function) at the middle layout.

## Files

| File | Role |
|---|---|
| `experiments/compare_pilot.py` | D1 generator plus run loop (arms `semtrace`, `toolz`) |
| `experiments/build_contexts.py` | Context builder; filler is **layout-independent** (fixed version, logs `filler_hash`) |
| `experiments/run_eval.py` | OpenAI-compatible API call (`LLM_BASE_URL` / `LLM_API_KEY`), scoring |
| `experiments/build_items.py` | Only `strip_docstrings` is used here |
| `experiments/summarize_compare.py` | Accuracy table, middle drop D with bootstrap CI, amplitude A |
| `experiments/data/toolz_anon_*` | Filler units (and items for the toolz arm) |
| `experiments/results/toolz_anon_oracle_calib.jsonl` | Needed only for the `toolz` arm |
| `experiments/results/compare_deepseek.jsonl`, `compare_gemma.jsonl` | The group's 09/11 D1 results. **Old builder**: these records have no `filler_hash`, so filler could differ between layouts |

## Run

Everything runs from this folder (`d1/`) and needs only the Python standard library.

```bash
# check: 60 items (30 x 2 digits), 300 calls at oracle + 16k
python3 experiments/compare_pilot.py --model X --arms semtrace --lengths 0,16000 --dry-run --out /tmp/x.jsonl

# local Ollama via its OpenAI-compatible endpoint
export LLM_BASE_URL=http://localhost:11434/v1 LLM_API_KEY=ollama
python3 experiments/compare_pilot.py --model qwen2.5-coder:7b --arms semtrace \
    --lengths 0,16000 --workers 1 --out experiments/results/d1_qwen25coder7b.jsonl

# summary
python3 experiments/summarize_compare.py experiments/results/d1_*.jsonl
```

Notes:
- The run can be resumed. Running it again with the same `--out` repeats only the missing or failed calls.
- The semantic answer is capped at 300 tokens, and the prompt asks for `ANSWER: <output>` with no
  explanation, so this is a direct-answer setting, not step-by-step.
- `thinking: disabled` is sent in DeepSeek's format. Ollama may ignore it. For thinking models
  (such as qwen3.5) check that the output holds no reasoning text, or use a non-thinking model.
- With Ollama, set the model's context window large enough for 16k/32k prompts. Otherwise
  Ollama silently cuts the prompt. Check that `usage.prompt_tokens` in the output roughly equals
  `est_tokens`.
- The priority run is to repeat the 09/11 D1 cells (semtrace4 at 16k and 32k, DeepSeek) with the
  fixed builder. That shows whether the old +0.47 middle drop holds up.
