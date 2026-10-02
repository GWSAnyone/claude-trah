"""Настройка защёлки дублей у проекта — одна на ядро, хук и `dedup-setup.py`.

Лёгкий модуль без numpy и tree-sitter: хук зовёт его на КАЖДУЮ правку, и
тянуть туда научный стек ради поиска одного файла незачем.

Настройка лежит в корне проекта, `.claude/dedup.json`:

    state       setup | on | off   — нет файла значит setup
    layout      single | subprojects — корень один проект или каждый каталог
                первого уровня отдельный (боты, соседние крейты)
    scopes      [go back | front | css | html | rust] — пусто значит все
    skip_dirs, skip_files — добавка к пропускам по умолчанию
    refs        [[проект, сторона, путь от корня]] — общий код для сверки
    every       каждая какая правка проверяется (5)
    accepted    файл принятых пар от корня (.claude/dedup-accepted.txt)
    brief       вставка проекта в бриф судьи (.claude/dedup-brief.md)
"""
import hashlib
import json
import os

CONFIG_NAME = os.path.join('.claude', 'dedup.json')
CACHE_HOME = os.path.expanduser('~/.cache/dedup')

# Сторона → (язык разборщика, расширения).
SCOPES = {'back': ('go', ('.go',)), 'front': ('js', ('.js',)), 'css': ('css', ('.css',)),
          'html': ('html', ('.html', '.htm')), 'rust': ('rust', ('.rs',))}
CODE_EXTS = tuple(e for _, exts in SCOPES.values() for e in exts)

SKIP_DIRS = {'data', 'logs', '_backup', '_backups', 'backup', 'backups', 'testdata', 'node_modules', 'vendor',
             'docs', '.git', 'bin', 'tmp', 'target', 'dist', 'build', 'examples', 'benches'}
# tests.rs и *_tests.rs — тела `mod tests;` и тестов рядом с модулем; build.rs — сценарии сборки.
SKIP_FILES = ['*_test.go', '*.min.js', '*.min.css', '*.bak*', 'tests.rs', '*_tests.rs', 'build.rs']


class lock:
    """Исключительный замок на файл — и на Linux, и на Windows (там нет fcntl).

    with dedupconf.lock(path + '.lock'): ...
    """
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
        self.f = open(self.path, 'a+')
        if os.name == 'nt':
            import msvcrt
            import time
            while True:
                try:
                    self.f.seek(0)
                    msvcrt.locking(self.f.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
        else:
            import fcntl
            fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        if os.name == 'nt':
            import msvcrt
            try:
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        self.f.close()


def tool_cmd(*args):
    """Команда ядра без bash: `uv run` с зависимостями и dedup.py рядом.

    dedup.sh — то же для человека в терминале; хук и setup зовут это, потому что
    на Windows bash может не быть."""
    if os.environ.get('DEDUP_TOOL'):  # подмена ядра — для тестов хука
        return [os.environ['DEDUP_TOOL'], *args]
    here = os.path.dirname(os.path.abspath(__file__))
    return ['uv', 'run', '-q', '--with', 'tree-sitter-language-pack', '--with', 'scikit-learn',
            os.path.join(here, 'dedup.py'), *args]


def short_hash(text):
    return hashlib.sha1(text.encode()).hexdigest()[:8]


def find_root(start):
    """Каталог с `.claude/dedup.json` от start вверх, не выше домашнего."""
    d, home = os.path.abspath(start), os.path.expanduser('~')
    while True:
        if os.path.isfile(os.path.join(d, CONFIG_NAME)):
            return d
        if d in (home, os.sep) or os.path.dirname(d) == d:
            return None
        d = os.path.dirname(d)


def git_root(start):
    d = os.path.abspath(start)
    while os.path.dirname(d) != d:
        if os.path.exists(os.path.join(d, '.git')):
            return d
        d = os.path.dirname(d)
    return None


def load(root):
    try:
        return json.load(open(os.path.join(root, CONFIG_NAME), encoding='utf8'))
    except (OSError, ValueError):
        return {}


def save(root, conf):
    path = os.path.join(root, CONFIG_NAME)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp-' + str(os.getpid())
    with open(tmp, 'w', encoding='utf8') as f:
        json.dump(conf, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(tmp, path)


def cache_dir(root):
    """Свой кэш у каждого корня: разбор, метки судьи, линии, последняя ошибка."""
    return os.path.join(CACHE_HOME, 'roots', os.path.basename(root.rstrip(os.sep)) + '-' + short_hash(root))


def note_error(root, what):
    import time
    try:
        os.makedirs(cache_dir(root), exist_ok=True)
        with open(os.path.join(cache_dir(root), 'last-error.json'), 'w', encoding='utf8') as f:
            json.dump({'when': time.strftime('%Y-%m-%d %H:%M:%S'), 'what': str(what)[:600]}, f, ensure_ascii=False)
    except OSError:
        pass


def last_error(root):
    try:
        return json.load(open(os.path.join(cache_dir(root), 'last-error.json'), encoding='utf8'))
    except (OSError, ValueError):
        return None
