# trigger-bench

> The only skill trigger testing suite built natively for OpenClaw.
> OpenClaw 专属 Skill 触发测试工具——官方工具在 OpenClaw 里不可用，这是唯一修复版本。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## The problem / 问题背景

The official `skill-creator` tool ships a `run_loop.py` that tests skill trigger
accuracy by inspecting Claude's tool call trace for a **Skill tool invocation**.
This works correctly in the Anthropic Claude Code CLI.

**In OpenClaw, it produces 0% recall.**

OpenClaw does not route skill triggering through a named Skill tool. Skills are
injected into the system prompt as an `available_skills` XML block, and Claude's
decision to read a skill manifests as a plain `Read` file call — indistinguishable
from any other file read. The official tool's detection logic finds nothing and
reports every query as "not triggered", regardless of description quality.

> 官方 `skill-creator` 的 `run_loop.py` 通过检测 Skill tool call 来判断触发。
> 但 OpenClaw 不走 Skill tool 路由——触发逻辑在 system prompt 层完成，
> 导致官方工具 recall 恒为 0%，无论 skill description 写得多好都没用。

---

## How it works / 工作原理

trigger-bench replaces tool-call detection with a **direct TRIGGER/SKIP
classification prompt** sent to `claude -p` via stdin:

```
You are deciding whether to read a skill file before answering a query.

Available skill:
<skill name="my-skill">
  [description]
</skill>

User query: "..."

Reply TRIGGER or SKIP, nothing else.
```

No `.claude/commands/` setup. No tool call introspection. No OpenClaw-specific
hooks. Just a plain text classification that closely models Claude's actual
triggering decision in production.

The `run_loop_openclaw.py` script wraps this into a full **eval → improve → re-eval**
loop: if any queries fail, Claude is asked to rewrite the description targeting the
failures. A held-out test split guards against overfitting.

> trigger-bench 用 TRIGGER/SKIP 文本分类 prompt 替代 tool call 检测。
> `run_loop_openclaw.py` 在此基础上实现「评测 → 改写 → 再评测」的自动迭代，
> 直到所有测试 query 全部通过或达到最大迭代次数。

---

## Installation / 安装

### Via ClawHub (recommended)

```bash
npx clawhub@latest install trigger-bench
```

### Manual

```bash
git clone https://github.com/Eason-Mars/trigger-bench \
  ~/.openclaw/workspace/.agents/skills/trigger-bench
```

No additional dependencies — uses `claude -p` (already available in any OpenClaw
environment) and Python's standard library only.

---

## Quick Start / 快速上手

### Step 1 — Create an eval set

Create a JSON file with queries that should and should not trigger your skill:

```json
[
  {"query": "I need to document this lesson", "should_trigger": true},
  {"query": "write a python script to parse JSON", "should_trigger": false}
]
```

An example eval set is provided at `evals/example-evals.json`.

### Step 2 — Run a single evaluation

```bash
python3 ~/.openclaw/workspace/.agents/skills/trigger-bench/scripts/run_eval_openclaw.py \
  --eval-set /path/to/your-evals.json \
  --skill-path ~/.openclaw/workspace/.agents/skills/YOUR_SKILL \
  --runs-per-query 3 \
  --verbose
```

### Step 3 — Run the auto-improvement loop

```bash
python3 ~/.openclaw/workspace/.agents/skills/trigger-bench/scripts/run_loop_openclaw.py \
  --eval-set /path/to/your-evals.json \
  --skill-path ~/.openclaw/workspace/.agents/skills/YOUR_SKILL \
  --model claude-opus-4-5 \
  --max-iterations 5 \
  --runs-per-query 3 \
  --verbose
```

The loop exits when all train queries pass (printing `all_passed`) or after
`--max-iterations`. The JSON output includes `best_description` — copy this into
your `SKILL.md` frontmatter.

---

## Scripts reference / 脚本参考

### `run_eval_openclaw.py` — Single evaluation pass

```
--eval-set         Path to eval set JSON (required)
--skill-path       Path to skill directory with SKILL.md (required)
--description      Override description to test (default: from SKILL.md)
--num-workers      Parallel workers (default: 10)
--timeout          Timeout per query in seconds (default: 30)
--runs-per-query   Runs per query for averaging non-determinism (default: 3)
--trigger-threshold  Min trigger rate to count as triggered (default: 0.5)
--model            Model override for claude -p
--verbose          Print per-query PASS/FAIL to stderr
```

Output: JSON to stdout — `summary.passed / summary.total` + per-query results.

### `run_loop_openclaw.py` — Eval + auto-improve loop

```
--eval-set         Path to eval set JSON (required)
--skill-path       Path to skill directory (required)
--model            Model for evaluation AND improvement (required)
--description      Override starting description
--max-iterations   Max improvement loop iterations (default: 5)
--holdout          Fraction of eval set held out for test (default: 0.4)
--results-dir      Save results.json to a timestamped subdirectory here
--verbose          Print iteration-by-iteration progress to stderr
(+ same --num-workers / --timeout / --runs-per-query / --trigger-threshold)
```

Output: JSON with `best_description`, `best_score`, full `history` array.

### `grade_eval.py` — Assertion-based programmatic grading

```
usage: grade_eval.py <evals_json>
```

Accepts an assertion-based JSON format (different from trigger evals) with
`file_exists` and `file_contains` assertion types. Outputs `grading.json` and
a console pass/fail summary. Used for verifying skill output artifacts.

---

## Real-world results / 实测结果

trigger-bench was first used to develop and validate the `lesson-keeper` skill.

| Metric | Result |
|--------|--------|
| Eval set size | 20 queries |
| Iterations to 100% | **1** |
| Final score | **20 / 20** |
| False positives | 0 |
| False negatives | 0 |

The description reached perfect precision and recall on the first iteration of
`run_loop_openclaw.py`. No further improvement was needed.

> lesson-keeper 开发中，trigger-bench 在**第 1 次迭代**即达到满分 20/20，
> 零误触发，零漏触发。这是 OpenClaw 环境下首个经过完整触发测试验证的 Skill。

---

## Credits / 致谢

Inspired by [skill-creator](https://github.com/steipete/skill-creator) by [@steipete](https://github.com/steipete).

The official skill-creator tool defined the eval loop architecture and description
improvement prompting strategy. trigger-bench adapts those ideas for OpenClaw
environments where the original tool cannot function.

---

## License

MIT © Eason Zhang
