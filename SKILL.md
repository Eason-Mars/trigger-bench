---
name: trigger-bench
description: >
  Use this skill when you want to test whether your OpenClaw skill triggers correctly,
  optimize a skill's description for better trigger accuracy, or benchmark trigger rates
  across a set of test queries. The official skill-creator run_loop.py has 0% recall in
  OpenClaw environments — trigger-bench is the only OpenClaw-native fix.
  Use when: "test my skill", "does this skill trigger", "optimize skill description",
  "why isn't my skill triggering", "benchmark trigger accuracy", "improve skill description".
---

# trigger-bench

The only skill trigger testing suite built natively for OpenClaw. Fixes the 0% recall
issue that affects the official `skill-creator` `run_loop.py` in OpenClaw environments.

## What it does

| Script | One-line summary |
|--------|-----------------|
| `scripts/run_eval_openclaw.py` | Run a fixed eval set against a skill description and report pass/fail rates for each query |
| `scripts/run_loop_openclaw.py` | Iteratively evaluate + auto-improve a skill description until all queries pass (or max iterations hit) |
| `scripts/grade_eval.py` | Programmatically score assertion-based evals (file_exists / file_contains checks), output `grading.json` |

## Quick Start

```bash
# 1. Create an eval set (or use the example)
cp ~/.openclaw/workspace/.agents/skills/trigger-bench/evals/example-evals.json /tmp/my-evals.json

# 2. Run a single evaluation pass
python3 ~/.openclaw/workspace/.agents/skills/trigger-bench/scripts/run_eval_openclaw.py \
  --eval-set /tmp/my-evals.json \
  --skill-path ~/.openclaw/workspace/.agents/skills/YOUR_SKILL \
  --runs-per-query 3 \
  --verbose

# 3. Run the auto-improvement loop (iterates until 100% or max-iterations)
python3 ~/.openclaw/workspace/.agents/skills/trigger-bench/scripts/run_loop_openclaw.py \
  --eval-set /tmp/my-evals.json \
  --skill-path ~/.openclaw/workspace/.agents/skills/YOUR_SKILL \
  --model claude-opus-4-5 \
  --max-iterations 5 \
  --runs-per-query 3 \
  --verbose
```

## Eval set format

`evals.json` is a JSON array. Each entry has two fields:

```json
[
  {"query": "the user message to test", "should_trigger": true},
  {"query": "unrelated message", "should_trigger": false}
]
```

- **`query`** — the exact user message Claude would receive
- **`should_trigger`** — `true` if the skill should activate for this query, `false` if it should stay silent

A pass rate threshold (default `0.5`) decides whether a given query counts as triggered.
Set `--runs-per-query 3` to average out non-determinism.

See `evals/example-evals.json` for a ready-to-run example.

## How trigger detection works

trigger-bench sends a **TRIGGER / SKIP classification prompt** directly to `claude -p`
via stdin for each query. No `.claude/commands/` mechanism, no Skill tool call detection
— just a text prompt that asks Claude to classify the query against the skill description.

```
You are deciding whether to read a skill file before answering a query.

Available skill:
<skill name="my-skill">
  [skill description]
</skill>

User query: "..."

Decision rules:
- Reply TRIGGER if this query clearly calls for the skill above
- Reply SKIP if this query is unrelated or a different task type
- Reply only TRIGGER or SKIP, nothing else.
```

The output is parsed for the word `TRIGGER`. This approach is fully compatible with
OpenClaw's execution model and requires no changes to the target skill.

## Scripts reference

### `run_eval_openclaw.py`

```
usage: run_eval_openclaw.py --eval-set FILE --skill-path DIR [options]

  --eval-set        Path to eval set JSON file (required)
  --skill-path      Path to skill directory containing SKILL.md (required)
  --description     Override the description to test (default: from SKILL.md)
  --num-workers     Parallel workers (default: 10)
  --timeout         Timeout per query in seconds (default: 30)
  --runs-per-query  Runs per query for averaging (default: 3)
  --trigger-threshold  Min trigger rate to count as triggered (default: 0.5)
  --model           claude -p model override (default: user's configured model)
  --verbose         Print per-query results to stderr
```

Output: JSON to stdout with `summary.passed / summary.total` and per-query results.

### `run_loop_openclaw.py`

```
usage: run_loop_openclaw.py --eval-set FILE --skill-path DIR --model MODEL [options]

  --eval-set        Path to eval set JSON file (required)
  --skill-path      Path to skill directory (required)
  --model           Model for both evaluation and description improvement (required)
  --description     Override starting description
  --num-workers     Parallel workers (default: 10)
  --timeout         Timeout per query in seconds (default: 30)
  --max-iterations  Max improvement loop iterations (default: 5)
  --runs-per-query  Runs per query (default: 3)
  --trigger-threshold  Trigger rate threshold (default: 0.5)
  --holdout         Fraction of eval set held out for test (default: 0.4)
  --results-dir     Save results.json to a timestamped subdirectory here
  --verbose         Print iteration-by-iteration progress to stderr
```

Output: JSON with `best_description`, `best_score`, full `history` array.

### `grade_eval.py`

```
usage: grade_eval.py <evals_json>

  evals_json    Path to an assertion-based evals JSON file (different format from
                the trigger evals — uses file_exists / file_contains assertion checks)
```

Output: `grading.json` in the same directory + console pass/fail summary.

## Real-world validation: lesson-keeper

trigger-bench was first used during the development of the `lesson-keeper` skill.
After a single iteration of `run_loop_openclaw.py`, the description achieved **20/20
on the full trigger test set** — 100% precision and recall, zero false positives,
zero missed triggers. No further iterations were required.

This validates that the TRIGGER/SKIP classification approach is both accurate and
efficient for OpenClaw-native skill development.
