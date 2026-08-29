#!/usr/bin/env python3
"""Тесты гарда области поиска Serena."""
import json
import os
import subprocess
import sys

# путь берём от самого теста — файл работает и в комплекте, и после установки
HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard-serena-scope.py")
BLOCK, PASS = True, False

CASES = [
    # --- без области: блок ---
    ("mcp__serena__find_symbol", {"name_path_pattern": "runScan"}, BLOCK),
    ("mcp__serena__find_symbol", {"name_path_pattern": "runScan", "relative_path": ""}, BLOCK),
    ("mcp__serena__find_symbol", {"name_path_pattern": "runScan", "relative_path": "."}, BLOCK),
    ("mcp__serena__find_symbol", {"name_path_pattern": "X", "relative_path": "  "}, BLOCK),
    ("mcp__serena__search_for_pattern", {"substring_pattern": "HandleFunc"}, BLOCK),
    ("mcp__serena__search_for_pattern",
     {"substring_pattern": "X", "relative_path": "", "paths_include_glob": ""}, BLOCK),
    ("mcp__serena__find_file", {"file_mask": "*.go"}, BLOCK),
    ("mcp__serena__list_dir", {}, PASS),  # листинг каталога дёшев — под гард не берём

    # --- область задана: проходит ---
    ("mcp__serena__find_symbol",
     {"name_path_pattern": "runScan", "relative_path": "DmTrading"}, PASS),
    ("mcp__serena__find_symbol",
     {"name_path_pattern": "runScan", "relative_path": "DmTrading/internal/scan/worker.go"}, PASS),
    ("mcp__serena__search_for_pattern",
     {"substring_pattern": "HandleFunc", "relative_path": "GWS_Ltd"}, PASS),
    ("mcp__serena__search_for_pattern",
     {"substring_pattern": "HandleFunc", "paths_include_glob": "CSFParser/**/*.go"}, PASS),
    ("mcp__serena__find_file", {"file_mask": "*.go", "relative_path": "BuffBot"}, PASS),

    # --- инструменты вне карты: не трогаем ---
    ("mcp__serena__find_referencing_symbols",
     {"name_path": "X", "relative_path": "DmTrading/internal/x.go"}, PASS),
    ("mcp__serena__get_symbols_overview", {"relative_path": "DmTrading/cmd/bot/main.go"}, PASS),
    ("mcp__serena__read_memory", {"memory_file_name": "bots/dmarket"}, PASS),
    ("mcp__serena__activate_project", {"project": "SyncedProjects"}, PASS),

    # --- не Serena вообще ---
    ("Grep", {"pattern": "foo"}, PASS),
    ("Bash", {"command": "ls"}, PASS),
]


def run(tool: str, args: dict) -> bool:
    proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"tool_name": tool, "tool_input": args}),
        capture_output=True,
        text=True,
    )
    return proc.returncode == 2


def main() -> int:
    failed = 0
    for tool, args, want in CASES:
        got = run(tool, args)
        ok = got == want
        failed += not ok
        short = tool.replace("mcp__serena__", "")
        keys = ", ".join(f"{k}={v!r}" for k, v in args.items() if "path" in k or "glob" in k) or "—"
        print(f"{'✓' if ok else '✗'} {'БЛОК' if got else 'ok  '}  {short:<26} {keys[:52]}")
    print(f"\nвсего: {len(CASES)}   провалов: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
