#!/usr/bin/env python3
"""Настройка защёлки дублей в проекте. Гайд — ~/.claude/skills/dedup/SETUP.md.

    dedup-setup.py survey [--root R]   что в проекте есть: стороны, файлы, кандидаты в пропуск
    dedup-setup.py on     [--root R] [--layout single|subprojects] [--scopes rust,back]
                          [--skip-dirs a,b] [--skip-files 'x*,y'] [--refs proj:scope:path,...]
                          [--every 5] [--accepted PATH] [--brief PATH]
    dedup-setup.py off    [--root R]   выключить здесь
    dedup-setup.py setup  [--root R]   вернуть «не настроено» — хук снова предложит настройку
    dedup-setup.py status [--root R]   состояние, последняя ошибка, базовые линии

Корень по умолчанию — найденная вверх настройка, иначе корень git, иначе
текущий каталог. Без numpy: работает и там, где ядро ещё не запускалось.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dedupconf  # noqa: E402

# Каталоги, которые часто держат копии нарочно или не являются своим кодом.
CANDIDATES = {'research', 'bench', 'benches', 'examples', 'example', 'fixtures', 'generated', 'gen', 'third_party',
              'external', 'deps', 'dist', 'build', 'out', 'vendor', 'node_modules', 'target', 'lib', 'static'}


def pick_root(arg):
    if arg:
        return os.path.abspath(os.path.expanduser(arg))
    cwd = os.getcwd()
    return dedupconf.find_root(cwd) or dedupconf.git_root(cwd) or cwd


def survey(root):
    counts, seen_skip = {}, {}
    for d, dirs, names in os.walk(root):
        keep = []
        for x in dirs:
            if x in CANDIDATES or x in dedupconf.SKIP_DIRS:
                seen_skip.setdefault(x, []).append(os.path.relpath(os.path.join(d, x), root))
            if x not in dedupconf.SKIP_DIRS and not x.startswith('.'):
                keep.append(x)
        dirs[:] = keep
        for n in names:
            for scope, (_, exts) in dedupconf.SCOPES.items():
                if n.endswith(exts):
                    c = counts.setdefault(scope, [0, 0])
                    c[0] += 1
                    try:
                        with open(os.path.join(d, n), 'rb') as f:
                            c[1] += sum(1 for _ in f)
                    except OSError:
                        pass
    print(f'корень {root}')
    print('стороны (файлов / строк):')
    for scope, (n, lines) in sorted(counts.items(), key=lambda kv: -kv[1][1]):
        print(f'  {scope:6} {n:6} / {lines}')
    if not counts:
        print('  кода на поддерживаемых языках нет (Go, JS, CSS, HTML, Rust)')
    print('каталоги-кандидаты в пропуск (уже пропускаются по умолчанию: ' + ', '.join(sorted(dedupconf.SKIP_DIRS)) + '):')
    for name, where in sorted(seen_skip.items()):
        mark = ' (по умолчанию)' if name in dedupconf.SKIP_DIRS else ''
        print(f'  {name}{mark}: ' + ', '.join(where[:4]) + (f' и ещё {len(where) - 4}' if len(where) > 4 else ''))
    top = [x for x in sorted(os.listdir(root)) if os.path.isdir(os.path.join(root, x)) and not x.startswith('.')]
    print('каталоги первого уровня: ' + ', '.join(top[:30]) + (' …' if len(top) > 30 else ''))
    print('uv: ' + ('есть' if shutil.which('uv') else 'НЕТ — ядру он нужен'))


def split(s):
    return [x.strip() for x in (s or '').split(',') if x.strip()]


def turn_on(root, a):
    conf = dedupconf.load(root)
    conf['state'] = 'on'
    if a.layout:
        conf['layout'] = a.layout
    for key, val in (('scopes', a.scopes), ('skip_dirs', a.skip_dirs), ('skip_files', a.skip_files)):
        if val is not None:
            conf[key] = split(val)
    if a.refs is not None:
        conf['refs'] = [r.split(':', 2) for r in split(a.refs)]
        bad = [r for r in conf['refs'] if len(r) != 3 or r[1] not in dedupconf.SCOPES]
        if bad:
            sys.exit(f'refs: ждал проект:сторона:путь, сторона из {", ".join(dedupconf.SCOPES)} — не так: {bad}')
    if a.every:
        conf['every'] = a.every
    for key, val in (('accepted', a.accepted), ('brief', a.brief)):
        if val:
            conf[key] = val
    unknown = set(conf.get('scopes', [])) - set(dedupconf.SCOPES)
    if unknown:
        sys.exit(f'scopes: неизвестные стороны {sorted(unknown)}; есть {", ".join(dedupconf.SCOPES)}')
    dedupconf.save(root, conf)
    print(f'включено: {os.path.join(root, dedupconf.CONFIG_NAME)}')
    print(json.dumps(conf, ensure_ascii=False, indent=2))
    if not shutil.which('uv'):
        print('ВНИМАНИЕ: нет uv — проверки не пойдут, пока его не поставить.')
        return
    r = subprocess.run(dedupconf.tool_cmd('--version'), capture_output=True, text=True, cwd=root,
                       env={**os.environ, 'DEDUP_ROOT': root})
    print('ядро: ' + (r.stdout.strip() or r.stderr.strip()[-300:]))
    print('Базовая линия построится сама на первой проверке: старый долг проекта — не новость.')


def set_state(root, state):
    conf = dedupconf.load(root)
    conf['state'] = state
    dedupconf.save(root, conf)
    print(f'{state}: {os.path.join(root, dedupconf.CONFIG_NAME)}')


def status(root):
    found = dedupconf.find_root(root)
    print(f'корень {root}; настройка ' + (os.path.join(found, dedupconf.CONFIG_NAME) if found else 'не найдена'))
    conf = dedupconf.load(found) if found else {}
    print(f'состояние: {conf.get("state", "setup")}')
    if conf:
        print(json.dumps(conf, ensure_ascii=False, indent=2))
    if found:
        err = dedupconf.last_error(found)
        print('последняя ошибка: ' + (f'{err["when"]} — {err["what"]}' if err else 'нет'))
        cache = dedupconf.cache_dir(found)
        lines = sorted(x for x in os.listdir(cache) if x.startswith('baseline-') and x.endswith('.json')) \
            if os.path.isdir(cache) else []
        print(f'кэш {cache}; базовых линий {len(lines)}' + (': ' + ', '.join(lines) if lines else ''))
    print('uv: ' + ('есть' if shutil.which('uv') else 'НЕТ'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['survey', 'on', 'off', 'setup', 'status'])
    ap.add_argument('--root')
    ap.add_argument('--layout', choices=['single', 'subprojects'])
    ap.add_argument('--scopes')
    ap.add_argument('--skip-dirs')
    ap.add_argument('--skip-files')
    ap.add_argument('--refs')
    ap.add_argument('--every', type=int)
    ap.add_argument('--accepted')
    ap.add_argument('--brief')
    a = ap.parse_args()
    root = pick_root(a.root)
    if a.command == 'survey':
        survey(root)
    elif a.command == 'on':
        turn_on(root, a)
    elif a.command in ('off', 'setup'):
        set_state(root, a.command)
    else:
        status(root)
    return 0


if __name__ == '__main__':
    sys.exit(main())
