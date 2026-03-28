#!/usr/bin/env python3
"""Run trigger evaluation for a skill description (OpenClaw-compatible version).

Tests whether a skill's description causes Claude to trigger for a set of
queries. Uses direct Claude -p stdin prompting instead of .claude/commands/
mechanism (which is not available in OpenClaw environments).

Outputs results as JSON, fully compatible with the original run_eval.py format.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


def parse_skill_md(skill_path: Path) -> tuple[str, str, str]:
    """Parse SKILL.md to extract name, description, and full content.

    Returns (name, description, content).
    Standalone version — no dependency on scripts.utils.
    """
    skill_md = skill_path / "SKILL.md"
    content = skill_md.read_text()

    # Extract name from frontmatter
    name_match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
    name = name_match.group(1).strip() if name_match else skill_path.name

    # Extract description from frontmatter
    desc_match = re.search(r"^description:\s*(.+)$", content, re.MULTILINE)
    description = desc_match.group(1).strip() if desc_match else ""

    return name, description, content


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    model: str | None = None,
) -> bool:
    """Run a single query and return whether the skill was triggered.

    Sends a TRIGGER/SKIP classification prompt to Claude via stdin.
    No .claude/commands/ mechanism needed — works in OpenClaw environments.
    """
    prompt = f"""You are deciding whether to read a skill file before answering a query.

Available skill:
<skill name="{skill_name}">
{skill_description}
</skill>

User query: "{query}"

Decision rules:
- Reply TRIGGER if this query clearly calls for the skill above
- Reply SKIP if this query is unrelated or a different task type
- Reply only TRIGGER or SKIP, nothing else."""

    cmd = ["claude", "-p", "--output-format", "text"]
    if model:
        cmd.extend(["--model", model])

    # Remove CLAUDECODE env var to allow nesting claude -p inside a
    # Claude Code session (same pattern as original run_eval.py).
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
        )
        if result.returncode != 0:
            print(
                f"Warning: claude -p exited {result.returncode} for query: {query[:50]!r}\n"
                f"stderr: {result.stderr[:200]}",
                file=sys.stderr,
            )
            return False

        output = result.stdout.strip().upper()
        return "TRIGGER" in output

    except subprocess.TimeoutExpired:
        print(f"Warning: timeout ({timeout}s) for query: {query[:50]!r}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Warning: exception for query {query[:50]!r}: {e}", file=sys.stderr)
        return False


def run_eval(
    eval_set: list[dict],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    model: str | None = None,
    verbose: bool = False,
) -> dict:
    """Run the full eval set and return results (same format as original run_eval.py)."""
    results = []

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_info = {}
        for item in eval_set:
            for run_idx in range(runs_per_query):
                future = executor.submit(
                    run_single_query,
                    item["query"],
                    skill_name,
                    description,
                    timeout,
                    model,
                )
                future_to_info[future] = (item, run_idx)

        query_triggers: dict[str, list[bool]] = {}
        query_items: dict[str, dict] = {}
        for future in as_completed(future_to_info):
            item, _ = future_to_info[future]
            query = item["query"]
            query_items[query] = item
            if query not in query_triggers:
                query_triggers[query] = []
            try:
                triggered = future.result()
                query_triggers[query].append(triggered)
                if verbose:
                    print(
                        f"  {'TRIGGER' if triggered else 'SKIP'}: {query[:60]!r}",
                        file=sys.stderr,
                    )
            except Exception as e:
                print(f"Warning: query failed: {e}", file=sys.stderr)
                query_triggers[query].append(False)

    for query, triggers in query_triggers.items():
        item = query_items[query]
        trigger_rate = sum(triggers) / len(triggers)
        should_trigger = item["should_trigger"]
        if should_trigger:
            did_pass = trigger_rate >= trigger_threshold
        else:
            did_pass = trigger_rate < trigger_threshold
        results.append({
            "query": query,
            "should_trigger": should_trigger,
            "trigger_rate": trigger_rate,
            "triggers": sum(triggers),
            "runs": len(triggers),
            "pass": did_pass,
        })

    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run trigger evaluation for a skill description (OpenClaw-compatible)"
    )
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override description to test")
    parser.add_argument("--num-workers", type=int, default=10, help="Number of parallel workers")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per query in seconds")
    parser.add_argument("--runs-per-query", type=int, default=3, help="Number of runs per query")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="Trigger rate threshold")
    parser.add_argument(
        "--model",
        default=None,
        help="Model to use for claude -p (default: user's configured model)",
    )
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    args = parser.parse_args()

    eval_set = json.loads(Path(args.eval_set).read_text())
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    name, original_description, _ = parse_skill_md(skill_path)
    description = args.description or original_description

    if args.verbose:
        print(f"Skill: {name}", file=sys.stderr)
        print(f"Description: {description}", file=sys.stderr)
        print(f"Eval set: {len(eval_set)} queries × {args.runs_per_query} runs", file=sys.stderr)
        print(f"Model: {args.model or '(default)'}", file=sys.stderr)
        t0 = time.time()

    output = run_eval(
        eval_set=eval_set,
        skill_name=name,
        description=description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        model=args.model,
        verbose=args.verbose,
    )

    if args.verbose:
        elapsed = time.time() - t0
        summary = output["summary"]
        print(
            f"Results: {summary['passed']}/{summary['total']} passed ({elapsed:.1f}s)",
            file=sys.stderr,
        )
        for r in output["results"]:
            status = "PASS" if r["pass"] else "FAIL"
            rate_str = f"{r['triggers']}/{r['runs']}"
            print(
                f"  [{status}] rate={rate_str} expected={r['should_trigger']}: {r['query'][:70]}",
                file=sys.stderr,
            )

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
