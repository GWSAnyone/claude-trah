#!/usr/bin/env python3
"""Сборка форка в vsix и установка сайдлоадом.

    tools/build.py            собрать dist/claude-code.vsix
    tools/build.py --install  собрать и поставить в VS Code

Нативного бинаря claude в пакете нет намеренно: расширение берёт исполняемый
файл из настройки claudeCode.claudeProcessWrapper (см. README).
"""

import argparse
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "ext")
DIST = os.path.join(ROOT, "dist")
OUT = os.path.join(DIST, "claude-code.vsix")


def pack() -> str:
    os.makedirs(DIST, exist_ok=True)
    files = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, _dirs, names in os.walk(SRC):
            for name in sorted(names):
                path = os.path.join(root, name)
                zf.write(path, os.path.relpath(path, SRC))
                files += 1
    print(f"упаковано {files} файлов -> {OUT} ({os.path.getsize(OUT) / 1048576:.1f} МБ)")
    return OUT


def install(vsix: str) -> int:
    code = shutil.which("code")
    if not code:
        print("code в PATH не найден", file=sys.stderr)
        return 1
    return subprocess.call([code, "--install-extension", vsix, "--force"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", action="store_true", help="поставить после сборки")
    args = ap.parse_args()
    vsix = pack()
    return install(vsix) if args.install else 0


if __name__ == "__main__":
    sys.exit(main())
