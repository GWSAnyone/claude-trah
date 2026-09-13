#!/usr/bin/env python3
"""Судья вкуса — по рубрике Senior SWE-Bench, заземлённый в репозитории.

Судит ДРУГАЯ модель (по умолчанию Fable 5.1), чтобы не мерить Opus его же
вкусом. Судья видит только репозиторий и дифф — не условие прогона и не
стенограмму. Оценки A–F по осям, вердикт «сеньор смёржит как есть», три
конкретных дефекта с file:line.

    judge.py <run_dir>...        → пишет run_dir/judge.json, печатает сводку
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

СУДЬЯ = os.environ.get("QBENCH_JUDGE", "claude-fable-5-1")
ОЦЕНКА = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}

ПРОМПТ = """You are a staff engineer reviewing a patch submitted to a repository you maintain. Judge it the way Senior SWE-Bench judges: not "does it work" but "would a senior maintainer merge this as-is, and is it the way THIS codebase does things".

The task the author was given:
<task>
{task}
</task>

The patch is the current uncommitted state of the working tree (`git diff HEAD` plus any untracked files). Before grading, read the repository's own conventions from the code itself — the package's __init__ docstrings, one or two sibling modules of the same kind, tests/conftest.py, README.md, CHANGELOG.md. Ground every judgement in something you read; cite file:line.

Grade each axis A/B/C/D/F. A = a senior maintainer would not change a character. C = works, but a reviewer would ask for changes before merging. F = wrong approach or breaks a convention the codebase relies on.

Axes:
1. minimality — only what the task needs: no unrequested scope, no extra abstraction, no config knobs, no defensive code for impossible cases, no touching files the mechanism made unnecessary to touch.
2. approach — the right mechanism and the right layer: the way the codebase already extends itself was used rather than bypassed.
3. hygiene — names, imports, error types, return types consistent with the package; nothing leaks a bare Exception/ValueError where the package has its own types.
4. fluency — reads like the sibling modules: same shape, same idiom, same level of comment density; a stranger could not tell which module was added last.
5. craftsmanship — tests are meaningful (behaviour, edge cases the siblings also cover), reuse the shared fixtures, and the documentation the siblings keep (docstring, changelog) is kept.
6. practice_alignment — logging idiom, error idiom, registry idiom, test idiom, changelog rule: each followed or not.

Then:
- merge_as_is: true/false — would you merge without requesting changes.
- defects: up to three, each {{"where": "file:line", "what": "<one sentence>", "senior_would": "<one sentence>"}}. Only defects you can point at.
- sound: up to three things done exactly right, one line each.

Do not reward length, comments, or "robustness" the siblings do not have. Do not penalise the absence of things the task did not ask for. Do not edit anything.

Output ONLY a fenced ```json block with keys: minimality, approach, hygiene, fluency, craftsmanship, practice_alignment (each a letter), merge_as_is (bool), defects (list), sound (list), one_line_verdict (string)."""


def judge(run_dir: Path) -> dict:
    repo = run_dir / "repo"
    task = (run_dir / "task.txt").read_text(encoding="utf-8").strip() \
        if (run_dir / "task.txt").exists() else ""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("CLAUDECODE") and not k.startswith("CLAUDE_CODE_")}
    proc = subprocess.run(
        ["claude", "-p", ПРОМПТ.format(task=task), "--output-format", "json",
         "--model", СУДЬЯ, "--max-turns", "40", "--dangerously-skip-permissions"],
        cwd=repo, env=env, capture_output=True, text=True, timeout=900)
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        data = {}
    if isinstance(data, list):
        data = next((r for r in reversed(data) if r.get("type") == "result"), {})
    text = data.get("result", "") if isinstance(data, dict) else ""
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
    verdict = json.loads(m.group(1)) if m else {"parse_error": text[-500:]}
    verdict["judge_model"] = СУДЬЯ
    verdict["judge_cost"] = data.get("total_cost_usd") if isinstance(data, dict) else None
    letters = [verdict.get(k) for k in ("minimality", "approach", "hygiene",
                                        "fluency", "craftsmanship", "practice_alignment")]
    nums = [ОЦЕНКА[x] for x in letters if x in ОЦЕНКА]
    verdict["mean_score"] = round(sum(nums) / len(nums), 2) if nums else None
    (run_dir / "judge.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    return verdict


def main() -> int:
    dirs = [Path(p) for p in sys.argv[1:]]
    if not dirs:
        sys.exit(__doc__)
    rows = []
    for d in dirs:
        if (d / "judge.json").exists():
            v = json.loads((d / "judge.json").read_text(encoding="utf-8"))
        else:
            v = judge(d)
        rows.append((d.name, v))
    print("tag\tmin\tappr\thyg\tflu\tcraft\tpract\tmean\tmerge\tverdict")
    for name, v in rows:
        print("\t".join(str(v.get(k, "?")) for k in
                        ("_tag", "minimality", "approach", "hygiene", "fluency",
                         "craftsmanship", "practice_alignment", "mean_score",
                         "merge_as_is", "one_line_verdict")).replace("?", name, 1))
    means = [v["mean_score"] for _, v in rows if v.get("mean_score")]
    merges = [v.get("merge_as_is") for _, v in rows if "merge_as_is" in v]
    if means:
        print(f"\nmean_score {sum(means)/len(means):.2f}   merge_as_is {sum(bool(m) for m in merges)}/{len(merges)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
