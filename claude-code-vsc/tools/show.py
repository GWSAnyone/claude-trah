#!/usr/bin/env python3
"""Показать несошедшиеся ханки: контекст, удаляемое, размер добавляемого."""
import sys

sys.path.insert(0, "/home/kaltsit/vsc-port-260/tools")
from port import ханки  # noqa: E402

ФАЙЛ = sys.argv[1] if len(sys.argv) > 1 else "ext/extension/webview/index.js"
НУЖНЫЕ = {int(x) for x in sys.argv[2].split(",")} if len(sys.argv) > 2 else None

for н, х in enumerate(ханки(ФАЙЛ, 6), 1):
    if НУЖНЫЕ and н not in НУЖНЫЕ:
        continue
    print(f"\n===== ханк {н}: вендорная строка {х['строка']}, "
          f"+{len(х['плюс'])} −{len(х['минус'])}")
    print("--- контекст ДО:")
    for с in х["до"]:
        print("   ", с[:100])
    if х["минус"]:
        print("--- УДАЛЯЕТСЯ:")
        for с in х["минус"]:
            print("  -", с[:100])
    if len(sys.argv) > 3 and sys.argv[3] == "плюс":
        print("--- ДОБАВЛЯЕТСЯ:")
        for с in х["плюс"]:
            print("  +", с)
    print("--- контекст ПОСЛЕ:")
    for с in х["после"][:4]:
        print("   ", с[:100])
