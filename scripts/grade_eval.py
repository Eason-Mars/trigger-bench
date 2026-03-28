#!/usr/bin/env python3
"""
grade_eval.py — Self-Improvement Skill 自动评分脚本
用法：python3 grade_eval.py <eval_result_dir> <evals_json>
输出：grading.json + 控制台 pass/fail 摘要
"""
import json, os, sys
from pathlib import Path

def check_file_exists(path: str, min_lines: int = 0) -> tuple[bool, str]:
    p = Path(os.path.expanduser(path))
    if not p.exists():
        return False, f"File not found: {path}"
    if min_lines > 0:
        lines = p.read_text(encoding='utf-8').strip().splitlines()
        if len(lines) < min_lines:
            return False, f"File exists but only {len(lines)} lines (need ≥{min_lines})"
    return True, f"File exists: {path} ({p.stat().st_size} bytes)"

def check_file_contains(path: str, contains: list[str]) -> tuple[bool, str]:
    p = Path(os.path.expanduser(path))
    if not p.exists():
        return False, f"File not found: {path}"
    content = p.read_text(encoding='utf-8')
    missing = [kw for kw in contains if kw not in content]
    if missing:
        return False, f"Missing keywords: {missing}"
    return True, f"All keywords found: {contains}"

def grade_assertion(assertion: dict) -> dict:
    check = assertion.get("check", "")
    path = assertion.get("path", "")
    
    if check == "file_exists":
        passed, evidence = check_file_exists(path, assertion.get("min_lines", 0))
    elif check == "file_contains":
        passed, evidence = check_file_contains(path, assertion.get("contains", []))
    else:
        passed, evidence = False, f"Unknown check type: {check}"
    
    return {
        "text": assertion["name"],
        "passed": passed,
        "evidence": evidence
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 grade_eval.py <evals_json>")
        sys.exit(1)
    
    evals_path = sys.argv[1]
    with open(evals_path, encoding='utf-8') as f:
        evals = json.load(f)
    
    total_pass = 0
    total_fail = 0
    all_results = []
    
    print(f"\n{'='*60}")
    print(f"Self-Improvement Skill — Eval Grading")
    print(f"{'='*60}\n")
    
    for eval_item in evals["evals"]:
        eval_id = eval_item["id"]
        assertions = eval_item.get("assertions", [])
        if not assertions:
            print(f"[Eval {eval_id}] No assertions defined, skipping")
            continue
        
        print(f"[Eval {eval_id}] {eval_item['prompt'][:60]}...")
        grading = []
        eval_pass = 0
        eval_fail = 0
        
        for assertion in assertions:
            result = grade_assertion(assertion)
            grading.append(result)
            if result["passed"]:
                eval_pass += 1
                total_pass += 1
                print(f"  ✅ {result['text']}")
            else:
                eval_fail += 1
                total_fail += 1
                print(f"  ❌ {result['text']}")
                print(f"     → {result['evidence']}")
        
        pass_rate = eval_pass / (eval_pass + eval_fail) * 100 if (eval_pass + eval_fail) > 0 else 0
        print(f"  → Eval {eval_id}: {eval_pass}/{eval_pass+eval_fail} ({pass_rate:.0f}%)\n")
        
        all_results.append({
            "eval_id": eval_id,
            "prompt": eval_item["prompt"][:80],
            "assertions": grading,
            "pass_rate": pass_rate
        })
    
    overall_pass_rate = total_pass / (total_pass + total_fail) * 100 if (total_pass + total_fail) > 0 else 0
    
    print(f"{'='*60}")
    print(f"OVERALL: {total_pass}/{total_pass+total_fail} assertions passed ({overall_pass_rate:.0f}%)")
    print(f"{'='*60}\n")
    
    # Save grading.json
    output = {
        "skill_name": evals["skill_name"],
        "total_pass": total_pass,
        "total_fail": total_fail,
        "overall_pass_rate": overall_pass_rate,
        "evals": all_results
    }
    
    out_path = Path(evals_path).parent / "grading.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Grading saved to: {out_path}")
    
    return 0 if total_fail == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
