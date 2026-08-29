#!/usr/bin/env python3
"""Насколько сессии ПОЛЬЗУЮТСЯ оснасткой: Serena, подагенты, навыки, MCP.

Считает по стенограммам ~/.claude/projects/*/ *.jsonl.
Наружу выдаёт только числа: содержимое стенограмм в вывод не попадает.

Три поправки против первой редакции:
  * подагентов запускает инструмент `Agent`, а не `Task` — считаем оба;
  * «чтение шеллом» — только когда утилита СТОИТ ПЕРВОЙ и получает путь;
    `... | head -40` над выводом команды чтением файла не является;
  * живая сессия — та, где человек говорил не меньше двух раз;
    одноразовые прогоны `--print` считаются отдельно.

Использование:
    harness-usage.py [--since ГГГГ-ММ-ДД] [--per-day N] [--min-turns N]
"""
import argparse
import collections
import json
import pathlib
import re
import statistics
import time

ROOT = pathlib.Path.home() / ".claude" / "projects"

READERS = r"(?:cat|head|tail|sed|awk|grep|rg|find|nl|less|wc)"
# Утилита в позиции команды: начало строки либо после ; && || ( — но НЕ после |.
LEADING_READ = re.compile(
    r"(?:^|[;&]{1,2}\s*|\(\s*)(?:sudo\s+|env\s+\S+=\S+\s+|command\s+)*" + READERS + r"\b([^|;&\n]*)")
PATHISH = re.compile(r"(?:^|\s)(?:\./|/|~|\w[\w.-]*/)[^\s'\"]*")

SYMBOLIC = ("mcp__serena__find_symbol", "mcp__serena__get_symbols_overview",
            "mcp__serena__find_referencing_symbols", "mcp__serena__replace_symbol_body",
            "mcp__serena__insert_after_symbol", "mcp__serena__insert_before_symbol",
            "mcp__serena__find_declaration", "mcp__serena__find_implementations")
AGENT_TOOLS = ("Agent", "Task")


def content_blocks(entry):
    msg = entry.get("message")
    if not isinstance(msg, dict):
        return []
    c = msg.get("content")
    return c if isinstance(c, list) else []


def shell_reads_a_file(cmd):
    """Команда читает файл утилитой, а не фильтрует чужой вывод."""
    for m in LEADING_READ.finditer(cmd):
        tail = m.group(1)
        if PATHISH.search(tail):
            return True
    return False


def scan_file(path):
    main = {"tools": collections.Counter(), "agents": collections.Counter(),
            "skills": collections.Counter(), "shell_read": 0, "bash": 0,
            "user_turns": 0, "assistant_turns": 0, "ts_first": None, "ts_last": None,
            "cwd": None, "sidechain_turns": 0}
    try:
        fh = open(path, "r", errors="replace")
    except OSError:
        return None
    with fh:
        for line in fh:
            if '"type"' not in line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            t = e.get("type")
            if t not in ("user", "assistant"):
                continue
            if e.get("isSidechain"):
                if t == "assistant":
                    main["sidechain_turns"] += 1
                continue
            ts = e.get("timestamp")
            if ts:
                if main["ts_first"] is None or ts < main["ts_first"]:
                    main["ts_first"] = ts
                if main["ts_last"] is None or ts > main["ts_last"]:
                    main["ts_last"] = ts
            if e.get("cwd") and not main["cwd"]:
                main["cwd"] = e["cwd"]
            if t == "assistant":
                main["assistant_turns"] += 1
            blocks = content_blocks(e)
            if t == "user":
                raw = e.get("message", {}).get("content")
                if isinstance(raw, str):
                    main["user_turns"] += 1
                elif blocks and not any(isinstance(b, dict) and b.get("type") == "tool_result"
                                        for b in blocks):
                    main["user_turns"] += 1
            for b in blocks:
                if not isinstance(b, dict) or b.get("type") != "tool_use":
                    continue
                name = b.get("name") or "?"
                main["tools"][name] += 1
                inp = b.get("input") or {}
                if name in AGENT_TOOLS:
                    main["agents"][inp.get("subagent_type") or "(без типа)"] += 1
                elif name == "Skill":
                    main["skills"][inp.get("skill") or "(без имени)"] += 1
                elif name == "Bash":
                    main["bash"] += 1
                    if shell_reads_a_file(inp.get("command") or ""):
                        main["shell_read"] += 1
    return main


def report(rows, title):
    n = len(rows)
    print(f"\n{'='*70}\n{title}: {n} сессий\n{'='*70}")
    if not n:
        return

    def used(r, prefix):
        return any(name.startswith(prefix) for name in r["tools"])

    def share(pred, label):
        k = sum(1 for r in rows if pred(r))
        print(f"  {label:22} {k:4d}/{n}  {100*k/n:5.1f}%")

    share(lambda r: used(r, "mcp__serena__"), "serena (любой)")
    share(lambda r: any(r["tools"].get(x) for x in SYMBOLIC), "serena символьный")
    share(lambda r: r["tools"].get("ToolSearch"), "ToolSearch")
    share(lambda r: any(r["tools"].get(x) for x in AGENT_TOOLS), "подагенты (Agent)")
    share(lambda r: r["tools"].get("Skill"), "навыки (Skill)")
    share(lambda r: used(r, "mcp__sequential-thinking__"), "sequential-thinking")
    share(lambda r: used(r, "mcp__context7__"), "context7")
    share(lambda r: used(r, "mcp__playwright__"), "playwright")
    share(lambda r: r["tools"].get("WebSearch") or r["tools"].get("WebFetch"), "WebSearch/WebFetch")
    share(lambda r: r["shell_read"], "чтение файла шеллом")

    calls = [sum(r["tools"].values()) for r in rows]
    print(f"  вызовов на сессию: медиана {statistics.median(calls):.0f}, "
          f"среднее {statistics.mean(calls):.1f}, всего {sum(calls)}")

    tot = collections.Counter()
    for r in rows:
        tot.update(r["tools"])
    bash = sum(r["bash"] for r in rows)
    sh = sum(r["shell_read"] for r in rows)
    sym = sum(tot.get(x, 0) for x in SYMBOLIC)
    ser = sum(k for name, k in tot.items() if name.startswith("mcp__serena__"))
    print(f"  serena {ser} (символьных {sym}) | Read {tot.get('Read',0)} "
          f"| Bash {bash}, из них чтение файла {sh} ({100*sh/bash if bash else 0:.1f}%)")

    ag = collections.Counter()
    for r in rows:
        ag.update(r["agents"])
    if ag:
        print(f"  подагенты: {sum(ag.values())} запусков — "
              + ", ".join(f"{nm}:{k}" for nm, k in ag.most_common(8)))
    sk = collections.Counter()
    for r in rows:
        sk.update(r["skills"])
    if sk:
        print(f"  навыки: {sum(sk.values())} вызовов — "
              + ", ".join(f"{nm}:{k}" for nm, k in sk.most_common(10)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since")
    ap.add_argument("--per-day", type=int, default=0)
    ap.add_argument("--min-turns", type=int, default=2)
    a = ap.parse_args()

    t0 = time.time()
    files = sorted(ROOT.glob("*/*.jsonl"))
    rows, total_bytes = [], 0
    for f in files:
        try:
            total_bytes += f.stat().st_size
        except OSError:
            pass
        m = scan_file(f)
        if not m or not m["assistant_turns"]:
            continue
        if a.since and (m["ts_first"] or "") < a.since:
            continue
        m["project"] = f.parent.name
        rows.append(m)

    dates = sorted(r["ts_first"][:10] for r in rows if r["ts_first"])
    print(f"стенограмм {len(files)}, с ходами ассистента {len(rows)}, "
          f"{dates[0]} … {dates[-1]}, {total_bytes/2**20:.0f} МиБ, разбор {time.time()-t0:.1f} с")

    live = [r for r in rows if r["user_turns"] >= a.min_turns]
    oneshot = [r for r in rows if r["user_turns"] < a.min_turns]
    report(live, f"ЖИВЫЕ сессии (реплик человека ≥ {a.min_turns})")
    report(oneshot, "одноразовые прогоны (реплик человека меньше)")

    zavr = [r for r in live if "tausozavr" in (r["project"] or "")]
    report(zavr, "живые сессии в tausozavr")

    byproj = collections.Counter(r["project"] for r in live)
    print("\n=== живые сессии по проектам (топ 10) ===")
    for p, k in byproj.most_common(10):
        print(f"  {k:4d}  {p}")

    if a.per_day:
        print(f"\n=== живые сессии по дням, последние {a.per_day} ===")
        byday = collections.defaultdict(list)
        for r in live:
            if r["ts_first"]:
                byday[r["ts_first"][:10]].append(r)
        print(f"  {'день':10} {'сесс':>5} {'serena':>7} {'агент':>6} {'навык':>6} "
              f"{'шелл-чт':>8} {'вызовов':>8}")
        for day in sorted(byday)[-a.per_day:]:
            rr = byday[day]
            print(f"  {day:10} {len(rr):5d} "
                  f"{sum(1 for r in rr if any(n.startswith('mcp__serena__') for n in r['tools'])):7d} "
                  f"{sum(1 for r in rr if any(r['tools'].get(x) for x in AGENT_TOOLS)):6d} "
                  f"{sum(1 for r in rr if r['tools'].get('Skill')):6d} "
                  f"{sum(r['shell_read'] for r in rr):8d} "
                  f"{sum(sum(r['tools'].values()) for r in rr):8d}")


if __name__ == "__main__":
    main()
