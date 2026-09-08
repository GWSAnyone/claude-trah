#!/usr/bin/env python3
"""Точечный поиск по большому бандлу: g.py <файл> <регексп> [макс]

Печатает только совпавшие строки, обрезанные до 200 символов.
"""
import re
import sys

path, pat = sys.argv[1], sys.argv[2]
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 40
rx = re.compile(pat)
n = 0
with open(path, encoding="utf-8", errors="replace") as f:
    for i, line in enumerate(f, 1):
        if rx.search(line):
            print(f"{i}: {line.rstrip()[:200]}")
            n += 1
            if n >= limit:
                print("… обрезано")
                break
print(f"[всего показано: {n}]")
