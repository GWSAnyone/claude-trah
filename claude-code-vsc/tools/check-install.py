#!/usr/bin/env python3
"""Проверка готовности установленного расширения к перезапуску VS Code.

Печатает только выводы, не содержимое файлов.
"""
import json
import os
import re

home = os.path.expanduser("~")

print("== extensions.json ==")
p = os.path.join(home, ".vscode/extensions/extensions.json")
for e in json.load(open(p)):
    i = e.get("identifier", {}).get("id", "")
    if "claude" in i.lower():
        meta = e.get("metadata") or {}
        print(
            i,
            e.get("version"),
            "| loc:", (e.get("location") or {}).get("path"),
            "| source:", meta.get("source"),
            "| pinned:", meta.get("pinned"),
        )

print("== settings.json: строки про claude ==")
s = os.path.join(home, ".config/Code/User/settings.json")
if os.path.exists(s):
    for line in open(s):
        if "claude" in line.lower():
            print("  " + line.strip())
else:
    print("  НЕТ ФАЙЛА", s)

print("== состав установленного 2.1.260 ==")
root = os.path.join(home, ".vscode/extensions/anthropic.claude-code-2.1.260")
for rel in ("extension.js", "webview/index.js", "webview/index.css",
            "package.json", "resources/native-binary/claude"):
    f = os.path.join(root, rel)
    print(f"  {rel}: {'есть, ' + str(os.path.getsize(f)) + ' Б' if os.path.exists(f) else 'НЕТ'}")

print("== ссылки на нативный бинарь в extension.js ==")
txt = open(os.path.join(root, "extension.js"), encoding="utf-8", errors="replace").read()
for m in re.finditer(r"native-binary", txt):
    a = max(0, m.start() - 120)
    print("  …" + txt[a:m.end() + 120].replace("\n", "⏎") + "…")
