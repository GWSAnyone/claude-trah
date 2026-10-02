#!/usr/bin/env python3
"""PostToolUse: защёлка дублей — правка не должна писать заново то, что в коде уже есть.

Каждая правка кода (Go, JS, CSS, HTML, Rust) ищет настройку проекта
`.claude/dedup.json` вверх от правленого файла. Дальше по состоянию:

  нет настройки / setup — НИЧЕГО не сканируется. Один раз за сессию на проект
          модели говорится: защёлка тут не настроена, спроси владельца —
          настроить по гайду (~/.claude/skills/dedup/SETUP.md) или выключить.
  on    — правка кладёт файл в список сессии и выходит сразу. На каждой
          `every`-й (5) — ядро `--focus <файлы> --new-only --judge --json`:
          функции правленых файлов против проекта, только пары не из базовой
          линии, с меткой Haiku. Модели показываются только DUP.
  off   — молчание.

Почему не на каждую правку: поиск с судьёй — 5–10 с (замер 30.09.2026).
Почему не асинхронно: ответ нужен, пока правка свежая.

Сломанная защёлка не выглядит как «дублей нет»: ошибка ядра или судьи
сообщается модели один раз за сессию на проект, с причиной из last-error.json.

`exit 2` не блокирует: для PostToolUse он означает «показать stderr модели».
Выключить на сессию: DEDUP_LATCH=0.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

DEDUP_HOME = Path(os.environ.get('DEDUP_HOME') or Path.home() / '.claude' / 'dedup')
sys.path.insert(0, str(DEDUP_HOME))
import dedupconf  # noqa: E402

TIMEOUT = 120
PATH_FIELDS = ('file_path', 'notebook_path', 'relative_path')
PY = Path(sys.executable).name  # python3 здесь, python.exe на Windows
GUIDE = Path.home() / '.claude' / 'skills' / 'dedup' / 'SETUP.md'


def edited_path(payload):
    inp = payload.get('tool_input')
    if not isinstance(inp, dict):
        return None
    field = next((f for f in PATH_FIELDS if isinstance(inp.get(f), str) and inp[f].strip()), None)
    if field is None:
        return None
    p = Path(inp[field])
    if not p.is_absolute():
        # relative_path у Serena — от корня ЕЁ проекта, а это не всегда cwd
        # сессии (сессия в ~/Projects/engine, Serena на ~/Projects): берём
        # первый существующий файл от cwd вверх.
        cwd = Path(payload.get('cwd') or os.getcwd())
        p = next((d / p for d in [cwd, *cwd.parents] if (d / p).is_file()), cwd / p)
    p = p.resolve()
    parts = set(p.parts)
    if not p.is_file() or not p.name.endswith(dedupconf.CODE_EXTS) or parts & {'target', 'node_modules', 'vendor'}:
        return None
    if p.name.endswith(('_test.go', '.min.js', '.min.css')):
        return None
    return p


def session_state(session):
    return Path(dedupconf.CACHE_HOME) / 'sessions' / f'{session}.json'


def with_state(session, change):
    """Состояние сессии под замком: change(st) правит его и возвращает ответ."""
    path = session_state(session)
    with dedupconf.lock(str(path) + '.lock'):
        try:
            st = json.loads(path.read_text(encoding='utf8'))
        except (OSError, ValueError):
            st = {}
        out = change(st)
        tmp = path.with_suffix('.tmp-' + str(os.getpid()))
        tmp.write_text(json.dumps(st, ensure_ascii=False), encoding='utf8')
        os.replace(tmp, path)
    return out


def once(session, key):
    """True ровно в первый раз за сессию для этого ключа."""
    def change(st):
        told = st.setdefault('told', [])
        if key in told:
            return False
        told.append(key)
        return True
    return with_state(session, change)


def ask_setup(session, path, payload):
    root = dedupconf.git_root(path.parent)
    cwd = Path(payload.get('cwd') or os.getcwd()).resolve()
    if root is None:
        if cwd not in path.parents:
            return 0  # файл вне репозитория и вне каталога сессии — не проект
        root = str(cwd)
    if not once(session, 'setup:' + root):
        return 0
    setup = DEDUP_HOME / 'dedup-setup.py'
    sys.stderr.write(
        f'ЗАЩЁЛКА ДУБЛЕЙ в проекте {root} не настроена. Это не ошибка правки: '
        'доделай текущую работу, а в ответе владельцу задай один вопрос — '
        'настроить защёлку вместе с ним (гайд ' + str(GUIDE) + ', несколько коротких '
        'вопросов о проекте) или выключить её здесь '
        f'(`{PY} {setup} off --root {root}`). '
        'В этой сессии напоминания больше не будет.\n')
    return 2


def main():
    if os.environ.get('DEDUP_LATCH') == '0':
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    path = edited_path(payload)
    if path is None:
        return 0
    session = str(payload.get('session_id') or 'nosession')[:40]
    root = dedupconf.find_root(path.parent)
    conf = dedupconf.load(root) if root else {}
    state = conf.get('state', 'setup')
    if state == 'off':
        return 0
    if state != 'on':
        return ask_setup(session, path, payload)

    every = max(1, int(conf.get('every', 5)))

    def count(st):
        r = st.setdefault('roots', {}).setdefault(root, {'count': 0, 'files': []})
        r['count'] += 1
        if str(path) not in r['files']:
            r['files'].append(str(path))
        if r['count'] % every:
            return []
        files, r['files'] = r['files'], []
        return files
    files = with_state(session, count)
    if not files:
        return 0

    broken = None
    try:
        r = subprocess.run(dedupconf.tool_cmd('--focus', *files, '--new-only', '--judge', '--json'),
                           capture_output=True, text=True, timeout=TIMEOUT, cwd=root,
                           env={**os.environ, 'DEDUP_ROOT': root})
        out = r.stdout.strip().splitlines()
        found = json.loads(out[-1]) if out else []
        if r.returncode not in (0, 3):
            broken = f'ядро вернуло код {r.returncode}: {r.stderr.strip()[-300:]}'
        elif r.returncode == 3:
            err = dedupconf.last_error(root) or {}
            broken = f'судья не ответил: {err.get("what", "причина не записана")}'
    except FileNotFoundError:
        found, broken = [], 'нет uv — ядру нужен uv (https://docs.astral.sh/uv/)'
    except subprocess.TimeoutExpired:
        found, broken = [], f'проверка не уложилась в {TIMEOUT} с'
    except (ValueError, OSError) as e:
        found, broken = [], f'{type(e).__name__}: {e}'
    if broken:
        dedupconf.note_error(root, broken)

    dups = [f for f in found if (f.get('judge') or {}).get('label') == 'DUP']
    msg = []
    if dups:
        batch = {os.path.realpath(f) for f in files}
        lines = []
        for f in dups:
            j = f['judge']
            # Судья называет наследника номером члена пары: 1 — новая функция, 2 — существующая.
            keep = {'1': f['mine'].split(' ', 1)[-1], '2': f['other'].split(' ', 1)[-1]}.get(
                str(j.get('keep', '')).strip(), j.get('keep', ''))
            other = os.path.realpath(os.path.join(root, f['units'][1]['file']))
            moving = ('\n  второй член тоже правлен в этой пачке — возможно, это недоделанный '
                      'перенос: доведи его, в принятые такую пару не вноси') if other in batch else ''
            lines.append(f"- {f['mine']}\n  ≈ {f['other']}\n  {j.get('why', '')}"
                         + (f' · оставить: {keep}' if keep else '') + moving)
        accepted = conf.get('accepted', '.claude/dedup-accepted.txt')
        msg.append(
            'ЗАЩЁЛКА ДУБЛЕЙ: последние правки написали то, что в коде уже есть '
            f'(проверено {len(files)} файл(ов), судья Haiku):\n' + '\n'.join(lines) + '\n\n'
            'То же дело — вызови существующую функцию (в CSS — возьми существующий класс, '
            'в HTML — общий кусок разметки) вместо своей копии. Не дубль или дубль '
            f'нарочно — внеси id пары в {os.path.join(root, accepted)} с причиной '
            '(id: `~/.claude/dedup/dedup.sh --focus <файл> --json`, поле id).')
    if broken and once(session, 'broken:' + root):
        msg.append(f'ЗАЩЁЛКА ДУБЛЕЙ СЛОМАНА в {root}: {broken}. Проверки идут вхолостую. '
                   'Скажи владельцу; диагностика — '
                   f'`{PY} {DEDUP_HOME / "dedup-setup.py"} status --root {root}`.')
    if not msg:
        return 0
    sys.stderr.write('\n\n'.join(msg) + '\n')
    return 2


if __name__ == '__main__':
    sys.exit(main())
