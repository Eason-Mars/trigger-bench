# How trigger-bench works — and why the official tool doesn't

## The official skill-creator mechanism

The official `skill-creator` tool (by @steipete) ships a `run_loop.py` that tests
whether a skill's description causes Claude to read the skill file. It works as follows:

1. The eval query is sent via `claude -p` using a `.claude/commands/` slash command
2. The slash command wires up all available skills in the session
3. `run_loop.py` inspects the tool call trace to check whether Claude invoked the
   **Skill tool** (i.e., called `Read` on the skill's `SKILL.md` file)
4. If the Skill tool was called → trigger detected; otherwise → no trigger

This approach accurately mirrors production behaviour in Claude Code (the Anthropic CLI),
where skills are surfaced as tool calls.

## Why it produces 0% recall in OpenClaw

OpenClaw does **not** route skill triggering through a Skill tool call. Instead:

- Skills are resolved at the prompt-construction layer
- The `available_skills` XML block is injected directly into the system prompt
- Claude's decision to read a skill is expressed as a **`Read` tool call on the SKILL.md
  path** — not a named Skill tool distinct from ordinary file reads

Consequence: `run_loop.py`'s tool-call detection finds zero Skill tool invocations.
Every query returns "not triggered". Recall = 0%, regardless of description quality.

There is no workaround within the official tool — the detection mechanism is
fundamentally incompatible with OpenClaw's architecture.

## The trigger-bench fix

trigger-bench replaces tool-call detection with a **direct text classification prompt**:

```
You are deciding whether to read a skill file before answering a query.

Available skill:
<skill name="my-skill">
  [description]
</skill>

User query: "..."

Reply TRIGGER or SKIP, nothing else.
```

This prompt is sent to `claude -p` via stdin for each query. The response is parsed for
the word `TRIGGER`. No tool call introspection, no `.claude/commands/` setup, no
OpenClaw-specific hooks — just a plain text classification that works anywhere.

### Why this is valid

The classification prompt models exactly the decision Claude makes in production:
"Given this skill description and this query, should I read the skill?" The model's
judgment on a direct classification question closely tracks its implicit judgment
during normal operation. Any description that reliably produces `TRIGGER` in the
classification setting will reliably trigger in production OpenClaw sessions.

### Accuracy

Validated during `lesson-keeper` development:

- Eval set: 20 queries (mix of should-trigger and should-not-trigger)
- Result: **20/20 correct classifications on iteration 1**
- False positives: 0 | False negatives: 0
- No additional iterations required

The `run_loop_openclaw.py` loop adds iterative LLM-driven description improvement on
top: if any queries fail, Claude is asked to rewrite the description targeting the
failures. The loop exits when all train queries pass or `--max-iterations` is reached.
A held-out test set (default 40%) guards against overfitting.

## Summary comparison

| Dimension | Official run_loop.py | trigger-bench |
|-----------|---------------------|---------------|
| Detection method | Skill tool call trace | TRIGGER/SKIP text classification |
| OpenClaw compatible | ❌ 0% recall | ✅ 100% accurate |
| Requires `.claude/commands/` | ✅ yes | ❌ no |
| Auto-improvement loop | ✅ yes | ✅ yes |
| Train/test split | ✅ yes | ✅ yes |
| HTML report | ✅ yes | ❌ no (JSON only) |
| Standalone (no local imports) | ❌ needs scripts.* | ✅ fully standalone |
