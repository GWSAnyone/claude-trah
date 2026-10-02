#!/usr/bin/env python3
"""Кандидаты в дубли кода — первый шаг скилла dedup и ядро хука-защёлки.

    ~/.claude/dedup/dedup.sh <Target>... [--cross] [--ref] [--sim 0.45] [--top 80] [--out DIR]
    ~/.claude/dedup/dedup.sh --focus FILE... [--new-only] [--judge] [--json]

Корень и настройка — `.claude/dedup.json` вверх от текущего каталога (см.
скилл dedup, SETUP.md). Target — `.` (корень целиком) или каталог от корня, с
необязательной стороной: `:back` (Go без тестов), `:front` (JS, в web/ если он
есть, без вендорных lib/), `:css`, `:html`, `:rust` (.rs без target/, tests/ и
`mod tests`); абсолютный путь — проект вне корня. Несколько целей —
сравниваются все со всеми; `--cross` оставляет только группы, где встречаются
РАЗНЫЕ проекты. `--ref` добавляет общий код из `refs` настройки и оставляет
только группы, где проект заново пишет то, что там уже есть.

Три сигнала, сведённые в одни группы:

  shape   treepeat в режиме loose (имена и константы обезличены) — копия с
          переименованием. Запускается один раз на временной копии исходников
          всех целей, поэтому видит копии и между проектами.
  vocab   сходство СЛОВАРЯ: какие функции вызываются, к каким полям идёт
          обращение, какие ключи литералов, строки и CSS-классы, с весами TF-IDF.
          Ловит «одно дело, написанное по-разному»: у двух imageZone разные
          аргументы и структура, но общие `inv-card__imgzone`, `wearVar`.
          Кроме функций сравниваются крупные блоки внутри длинных функций —
          сборка `ItemRef` в трёх местах живёт посреди разных тел.
  name    одинаковое короткое имя в разных файлах (`ageWord`, `contains`).

Выход — DIR (по умолчанию /tmp/dedup-<цели>): candidates.md (сильнейшие
сверху, с общими словами-доказательствами), candidates.json и catalog.json
(все функции — для смыслового прохода моделями). Кандидат — не приговор.

Качество 30.09.2026 на эталоне SellManager (35 дублей, найденных чтением кода):
см. скилл dedup, раздел «Замеры».
"""
import argparse, fnmatch, json, os, re, shutil, subprocess, sys, tempfile
from collections import defaultdict

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from tree_sitter_language_pack import get_parser

# Настройка — у проекта, а не в коде: `.claude/dedup.json` в корне. Корень
# ищется вверх от текущего каталога (или задан DEDUP_ROOT), поэтому сессия из
# подкаталога находит ту же настройку. До 02.10.2026 инструмент жил двумя
# копиями (боты и ~/Projects), расходившимися ровно в этих строках.
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dedupconf  # noqa: E402

VERSION = '1.0'
ROOT = os.path.abspath(os.environ.get('DEDUP_ROOT') or dedupconf.find_root(os.getcwd()) or os.getcwd())
CONF = dedupconf.load(ROOT)
LAYOUT = CONF.get('layout', 'single')
ACCEPTED = os.path.join(ROOT, CONF.get('accepted', '.claude/dedup-accepted.txt'))
PROJECT_BRIEF = os.path.join(ROOT, CONF.get('brief', '.claude/dedup-brief.md'))
SKIP_DIRS = dedupconf.SKIP_DIRS | set(CONF.get('skip_dirs', []))
SKIP_FILES = dedupconf.SKIP_FILES + list(CONF.get('skip_files', []))
# Общий код: (проект, сторона, путь от корня). Правка сверяется и с ним, а сам он источником находок не бывает.
REFS = [tuple(r) for r in CONF.get('refs', [])]
SCOPES_ON = set(CONF.get('scopes', []))   # пусто — все стороны
MIN_LINES = 5          # короче — шум: геттеры, однострочные обёртки
MIN_TOKENS = 4         # разных слов меньше — сравнивать нечего
BLOCK_MIN = 6          # блок внутри функции: не короче стольких строк
BLOCK_HOST = 30        # и только внутри функций длиннее этого
GROUP_MAX = 12         # функций в группе-звезде, центр включён
# Имена, одинаковые в разных файлах по идиоме, а не по копированию.
IDIOM_NAMES = {'main', 'init', 'String', 'Error', 'Load', 'Save', 'load', 'save', 'render', 'get', 'set',
               'Len', 'Less', 'Swap', 'close', 'open', 'run', 'Run', 'New', 'Close', 'Get', 'Set',
               'ServeHTTP', 'Validate', 'MarshalJSON', 'UnmarshalJSON', 'Reset', 'Stop', 'Start'}
GO_BLOCKS = {'if_statement', 'for_statement', 'expression_switch_statement', 'type_switch_statement',
             'composite_literal', 'select_statement'}
JS_BLOCKS = {'if_statement', 'for_statement', 'for_in_statement', 'try_statement', 'object', 'call_expression'}
RS_BLOCKS = {'if_expression', 'match_expression', 'for_expression', 'while_expression', 'loop_expression',
             'struct_expression'}
BLOCKS = {'go': GO_BLOCKS, 'js': JS_BLOCKS, 'rust': RS_BLOCKS}
# Сторона цели: язык и расширения. web-стороны ищутся в <проект>/web.
SCOPES = dedupconf.SCOPES
WEB_SCOPES = {'front', 'css', 'html'}
PARSERS = {'go': 'go', 'js': 'javascript', 'css': 'css', 'html': 'html', 'rust': 'rust'}
HTML_SKIP = {'html', 'head', 'body'}   # обёртки страницы: весь документ целиком, а не блок
CSS_MIN_WORDS = 4      # правило CSS — от двух деклараций: `.as-pill--on ≡ .as-pill--success` — две


def text(src, n):
    return src[n.start_byte:n.end_byte].decode('utf8', 'replace')


def fn_of(src, n, lang):
    """(kind, name) если узел — именованная функция, иначе None."""
    if lang == 'go':
        if n.type in ('function_declaration', 'method_declaration'):
            name = text(src, n.child_by_field_name('name'))
            recv = n.child_by_field_name('receiver')
            if recv is not None:
                name = text(src, recv).strip('()').split()[-1].lstrip('*').split('[')[0] + '.' + name
            return ('method' if recv is not None else 'func'), name
        return None
    if lang == 'rust':
        if n.type != 'function_item':
            return None
        name = text(src, n.child_by_field_name('name'))
        p = n.parent.parent if n.parent is not None and n.parent.type == 'declaration_list' else None
        if p is not None and p.type in ('impl_item', 'trait_item'):
            t = p.child_by_field_name('type' if p.type == 'impl_item' else 'name')
            return 'method', text(src, t).split('<')[0].split('::')[-1].lstrip('&') + '.' + name
        return 'func', name
    if lang == 'css':
        if n.type != 'rule_set':
            return None
        sel = next((c for c in n.children if c.type == 'selectors'), None)
        return ('rule', ' '.join(text(src, sel).split())[:80]) if sel is not None else None
    if lang == 'html':
        if n.type != 'element' or n.end_point[0] - n.start_point[0] + 1 < BLOCK_MIN \
                or not n.children or n.children[0].type != 'start_tag':
            return None
        tag, attrs = html_tag(src, n.children[0])
        if tag in HTML_SKIP:
            return None
        if attrs.get('id'):
            return 'element', tag + '@' + attrs['id']
        cls = attrs.get('class', '').split()
        return 'element', tag + ('.' + cls[0] if cls else '')
    if n.type in ('function_declaration', 'generator_function_declaration', 'method_definition') \
            and n.child_by_field_name('name') is not None:
        return ('method' if n.type == 'method_definition' else 'function'), text(src, n.child_by_field_name('name'))
    if n.type in ('variable_declarator', 'assignment_expression', 'pair'):
        key = n.child_by_field_name('name') or n.child_by_field_name('left') or n.child_by_field_name('key')
        val = n.child_by_field_name('value') or n.child_by_field_name('right')
        if key is not None and val is not None and val.type in ('arrow_function', 'function_expression', 'function'):
            return 'const', text(src, key)
    return None



# Слова-идиомы языка: есть в каждом третьем методе с мьютексом и связывали
# несвязанное (LockItemConditions ≈ SetProxyConnLimits).
STOP = {'c:.Lock', 'c:.Unlock', 'c:.RLock', 'c:.RUnlock', 'f:Lock', 'f:Unlock', 'f:RLock', 'f:RUnlock',
        'f:mu', 'f:wmu', 'c:len', 'c:append', 'c:make', 'c:cap', 'c:copy', 'c:delete', 'c:new', 'c:panic',
        'f:length', 'c:.push', 'f:push',
        # Rust: обёртки Option/Result и преобразования — в каждой второй функции.
        'c:Some', 'c:Ok', 'c:Err', 'c:.clone', 'c:.unwrap', 'c:.expect', 'c:.into', 'c:.to_string',
        'c:.to_owned', 'c:.as_str', 'c:.as_ref', 'c:.iter', 'c:.collect', 'c:.lock', 'f:clone',
        'f:unwrap', 'f:expect', 'f:into', 'f:to_string', 'f:to_owned', 'f:as_str', 'f:as_ref', 'f:iter',
        'f:collect', 'f:lock', 'c:vec!', 'c:format!', 't:Self'}
# Sprintf/Errorf в стоп-лист не входят: без них выпадала WriteAtomic ≈
# sourceStore.save — общий формат имени временного файла и есть след копии.


def html_tag(src, start):
    """Имя тега и атрибуты открывающего тега HTML."""
    tag, attrs = '', {}
    for c in start.children:
        if c.type == 'tag_name':
            tag = text(src, c).lower()
        elif c.type == 'attribute':
            k = next((x for x in c.children if x.type == 'attribute_name'), None)
            v = next((x for x in c.children if x.type in ('quoted_attribute_value', 'attribute_value')), None)
            if k is not None:
                attrs[text(src, k).lower()] = text(src, v).strip('"\'') if v is not None else ''
    return tag, attrs


def words(src, node, lang):
    """Словарь узла: c: вызовы, f: поля и ключи, s: строки и классы, t: типы, n: числа;
    CSS — p: свойства и v: пары «свойство: значение»; HTML — e: теги, k: классы,
    i: id, a: атрибуты, s: текст."""
    raw = css_words(src, node) if lang == 'css' else html_words(src, node) if lang == 'html' \
        else raw_words(src, node)
    return [w for w in raw if w not in STOP]


def css_words(src, node):
    # Дубль в CSS — тот же набор деклараций под другим селектором, поэтому
    # словарь — декларации, а селектор в него не входит: одинаковый селектор в
    # двух файлах ловит сигнал name.
    out, stack = [], [node]
    while stack:
        n = stack.pop()
        if n.type == 'declaration':
            prop = next((c for c in n.children if c.type == 'property_name'), None)
            if prop is not None:
                p = text(src, prop).lower()
                val = ' '.join(text(src, n).split(':', 1)[1].rstrip(';').split()).lower()
                out += ['p:' + p, 'v:' + p + ': ' + val]
            continue
        stack.extend(n.children)
    return out


def html_words(src, node):
    out, stack = [], [node]
    while stack:
        n = stack.pop()
        if n.type in ('script_element', 'style_element', 'comment'):
            continue
        if n.type in ('start_tag', 'self_closing_tag'):
            tag, attrs = html_tag(src, n)
            out.append('e:' + tag)
            for k, v in attrs.items():
                if k == 'class':
                    out += ['k:' + c for c in v.split()]
                elif k == 'id':
                    out.append('i:' + v)
                elif k != 'style':
                    out.append('a:' + k)
                    if v and len(v) <= 40 and ' ' not in v:
                        out.append('a:' + k + '=' + v)
            continue
        if n.type == 'text':
            out += ['s:' + w for w in re.split(r'[\s,;:()\[\]{}"\'`=.!?]+', text(src, n))
                    if 2 < len(w) <= 60 and not w.isdigit()]
        stack.extend(n.children)
    return out


def raw_words(src, node):
    out, stack = [], [node]
    while stack:
        n = stack.pop()
        t = n.type
        if t == 'macro_invocation':
            m = n.child_by_field_name('macro')
            if m is not None:
                out.append('c:' + text(src, m).split('::')[-1] + '!')
        elif t == 'call_expression':
            f = n.child_by_field_name('function')
            if f is not None:
                if f.type == 'identifier':
                    out.append('c:' + text(src, f))
                elif f.type in ('member_expression', 'selector_expression', 'field_expression'):
                    p = f.child_by_field_name('property') or f.child_by_field_name('field')
                    if p is not None:
                        out.append('c:.' + text(src, p))
                elif f.type == 'scoped_identifier':
                    # Vec::new, fs::read — путь до последнего сегмента и имя.
                    out.append('c:' + '::'.join(text(src, f).split('::')[-2:]))
        elif t in ('property_identifier', 'field_identifier', 'shorthand_property_identifier'):
            out.append('f:' + text(src, n))
        elif t == 'keyed_element' and n.named_children:
            k = n.named_children[0]
            out.append('f:' + text(src, k).strip())
        elif t == 'type_identifier':
            out.append('t:' + text(src, n))
        elif t in ('number', 'int_literal', 'float_literal', 'integer_literal'):
            # Числа — словарь арифметики: 60, 24, 1000 у форматтеров времени,
            # 1000/10 у процента. Без них agoText≈ageWord был пуст словами.
            v = text(src, n)
            if v not in ('0', '1', '2'):
                out.append('n:' + v)
        elif t in ('string_fragment', 'interpreted_string_literal_content', 'raw_string_literal_content',
                   'string_content'):
            for w in re.split(r'[\s,;:()\[\]{}"\'`=]+', text(src, n)):
                if 2 < len(w) <= 60 and not w.isdigit():
                    out.append('s:' + w)
        stack.extend(n.children)
    return out


def targets_files(targets):
    """(target, lang, abs_path) исходников каждой цели."""
    for proj, scope, sub in targets:
        base = os.path.join(ROOT, sub)
        lang, exts = SCOPES[scope]
        is_ref = (proj, scope, sub) in REFS
        for d, dirs, names in os.walk(base):
            dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith('.')
                             and not (scope == 'back' and x == 'web')
                             and not (scope in WEB_SCOPES and x == 'lib' and not is_ref)
                             and not (scope == 'rust' and x in ('target', 'tests')))
            for f in sorted(names):
                if f.endswith(exts) and not any(fnmatch.fnmatch(f, p) for p in SKIP_FILES):
                    yield proj, lang, os.path.join(d, f)


CACHE = dedupconf.cache_dir(ROOT)


def note_error(what):
    """Последняя поломка — на диск: `dedup-setup.py status` и хук её показывают."""
    dedupconf.note_error(ROOT, what)
UNITS_VERSION = 2      # сменился разбор или словарь — поднять, иначе кэш отдаст старые единицы
# Отпечаток того, что определяет корпус. Сменился — старая базовая линия не годится:
# словарь взвешен TF-IDF по всему корпусу, и прежние пары всплыли бы «новыми»
# (30.09: `enter.rs::start` ≈ `pack.rs::Served.new` после отсева стендов).
CORPUS_KEY = dedupconf.short_hash(json.dumps([sorted(SKIP_DIRS), SKIP_FILES, REFS, LAYOUT, UNITS_VERSION]))


def file_units(path, lang, parsers, with_blocks):
    """Функции и крупные блоки одного файла — без проекта и признака эталона."""
    src = open(path, 'rb').read()
    lines = src.decode('utf8', 'replace').split('\n')
    rel = os.path.relpath(path, ROOT)
    if rel.startswith('..'):
        rel = path  # проект вне SyncedProjects: os.path.join(ROOT, rel) даёт его же
    blocks = BLOCKS.get(lang, set())
    out, seen = [], defaultdict(int)

    def unit(n, name, kind, host=None):
        a, b = n.start_point[0], n.end_point[0]
        short = name.split('#')[0].split('/')[-1].split('.')[-1]
        if lang in ('css', 'html'):
            # Селектор и тег с классом — не уникальные имена: `.d` бывает и в
            # основном правиле, и в @media. Номер повтора держит id пары разным.
            short = name
            seen[name] += 1
            if seen[name] > 1:
                name += '~' + str(seen[name])
        out.append({'file': rel, 'line': a + 1, 'end': b + 1, 'name': name,
                    'short': short, 'kind': kind,
                    'lines': b - a + 1, 'host': host, 'lang': lang,
                    'head': '\n'.join(lines[a:min(b + 1, a + 12)]), 'words': words(src, n, lang)})

    def sub_blocks(n, host, seq):
        for c in n.children:
            if c.type in blocks and c.end_point[0] - c.start_point[0] + 1 >= BLOCK_MIN:
                # Имя блока — порядковый номер в хозяине, а не строка: id пары
                # не должен меняться от правки выше по файлу.
                seq[0] += 1
                unit(c, host + '#' + str(seq[0]), 'block', host)
            elif fn_of(src, c, lang) is None:
                sub_blocks(c, host, seq)

    def walk(n, trail):
        if lang == 'rust' and n.type == 'mod_item' and n.child_by_field_name('name') is not None \
                and text(src, n.child_by_field_name('name')) == 'tests':
            return  # модульные тесты Rust — как *_test.go у Go
        hit = fn_of(src, n, lang)
        here = trail
        if hit:
            kind, name = hit
            full = name if lang in ('css', 'html') else '/'.join(trail + [name])
            unit(n, full, kind)
            if with_blocks and n.end_point[0] - n.start_point[0] + 1 > BLOCK_HOST:
                sub_blocks(n, full, [0])
            here = trail + [name]
        for c in n.children:
            walk(c, here)
    walk(parsers[lang].parse(src).root_node, [])
    return out


def catalog(targets, refs):
    """Единицы всех целей. Разбор файла кэшируется по mtime и размеру
    (~/.cache/dedup/files.pkl): хуку-защёлке на каждую правку нужен весь
    проект, и без кэша DmTrading разбирался бы заново каждый раз."""
    import pickle
    os.makedirs(CACHE, exist_ok=True)
    cache_path = os.path.join(CACHE, 'files.pkl')
    try:
        cache = pickle.load(open(cache_path, 'rb'))
    except (OSError, EOFError, pickle.PickleError, ValueError):
        cache = {}
    parsers = {lang: get_parser(name) for lang, name in PARSERS.items()}
    units, dirty = [], False
    for proj, lang, path in targets_files(targets + refs):
        is_ref = any(proj == r[0] for r in refs)
        st = os.stat(path)
        key = (path, not is_ref, UNITS_VERSION)
        hit = cache.get(key)
        if not hit or hit[0] != (st.st_mtime_ns, st.st_size):
            hit = ((st.st_mtime_ns, st.st_size), file_units(path, lang, parsers, not is_ref))
            cache[key], dirty = hit, True
        units.extend({**u, 'project': proj, 'ref': is_ref} for u in hit[1])
    if dirty:
        tmp = cache_path + '.tmp-' + str(os.getpid())
        pickle.dump(cache, open(tmp, 'wb'))
        os.replace(tmp, cache_path)
    return units


def pair_id(a, b):
    """Устойчивый id пары: файл и имя, без строк — переживает правки файла.
    Разделитель пути всегда `/`: файл принятых пар бывает общим у Linux и Windows."""
    x, y = sorted([a['file'].replace(os.sep, '/') + '::' + a['name'], b['file'].replace(os.sep, '/') + '::' + b['name']])
    return x + ' | ' + y


def load_accepted():
    """tools/dedup-accepted.txt: принятые пары (`<id пары>  # причина`) и
    имена-идиомы (`name:<короткое имя>  # причина`) — больше не всплывают."""
    pairs, names = set(), set()
    try:
        for raw in open(ACCEPTED):
            # Комментарий — ` # ` с пробелами: в именах блоков есть `#` (`host#2`).
            line = raw.split(' # ', 1)[0].strip() if not raw.lstrip().startswith('#') else ''
            if line.startswith('name:'):
                names.add(line[5:].strip())
            elif ' | ' in line:
                pairs.add(line)
    except OSError:
        pass
    return pairs, names


def comparable(u):
    """Годится ли единица в сравнение. Общему коду длина не нужна: помощники
    shared/web/lib — однострочники (`fmtCents`), и с порогом в 5 строк
    переписанный в проекте `moneyText` было не с чем сравнить (30.09)."""
    if u['lang'] == 'css':
        return len(set(u['words'])) >= CSS_MIN_WORDS  # правило в одну строку — обычное дело
    return (u['ref'] or u['lines'] >= MIN_LINES) and len(set(u['words'])) >= MIN_TOKENS


def owner(u):
    """Тип-получатель метода Go или замыкание-хозяин функции JS; None — свободная."""
    name = u['name'].split('#')[0]
    if u['kind'] == 'block':
        return name  # блоки одной функции похожи друг на друга по природе
    if u['kind'] == 'method' and u['lang'] in ('go', 'rust'):
        return name.split('.')[0]
    return name.rsplit('/', 1)[0] if '/' in name else None


def overlaps(a, b):
    """Один узел внутри другого — функция и её блок или замыкание: не дубль."""
    return a['file'] == b['file'] and (a['line'] <= b['line'] <= a['end'] or b['line'] <= a['line'] <= b['end'])


def vocab_pairs(units, sim):
    out = []
    for lang in sorted({u['lang'] for u in units}):
        idx = [i for i, u in enumerate(units) if u['lang'] == lang and comparable(u)]
        if len(idx) < 2:
            continue
        # max_df: слово в каждой пятой функции — идиома языка, а не след копии.
        vec = TfidfVectorizer(analyzer=lambda ws: ws, sublinear_tf=True, max_df=0.2)
        X = vec.fit_transform([units[i]['words'] for i in idx])
        vocab = np.array(vec.get_feature_names_out())
        for start in range(0, X.shape[0], 400):
            S = (X[start:start + 400] @ X.T).tocoo()
            for r, c, v in zip(S.row, S.col, S.data):
                r += start
                if r >= c or v < sim:
                    continue
                a, b = units[idx[r]], units[idx[c]]
                if overlaps(a, b) or (a['ref'] and b['ref']):
                    continue
                both = X[r].multiply(X[c]).toarray()[0]
                out.append((idx[r], idx[c], float(v), [vocab[k] for k in np.argsort(-both)[:8] if both[k] > 0]))
    return out


def shape_groups(units):
    """treepeat один раз на временной копии всех исходников целей."""
    work = tempfile.mkdtemp(prefix='dedup-')
    try:
        for f in {u['file'] for u in units}:
            dst = os.path.join(work, f.lstrip(os.sep))  # абсолютный путь проекта вне ROOT
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(os.path.join(ROOT, f), dst)
        sarif = os.path.join(work, 'out.sarif')
        subprocess.run(['uvx', 'treepeat', '-r', 'loose', 'detect', '-s', '75', '-ml', str(MIN_LINES + 1),
                        '-f', 'sarif', '-o', sarif, '-if', '', work],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        try:
            results = json.load(open(sarif))['runs'][0]['results']
        except (OSError, ValueError, KeyError, IndexError):
            print('⚠ treepeat не отработал — сигнал shape пуст', file=sys.stderr)
            return []
    finally:
        shutil.rmtree(work, ignore_errors=True)
    by_file = defaultdict(list)
    for i, u in enumerate(units):
        if u['kind'] != 'block':
            by_file[u['file'].lstrip(os.sep)].append(i)
    groups = []
    for res in results:
        members = []
        for rg in res['properties']['regions']:
            path = os.path.relpath(os.path.join(work, rg['path']), work) if not rg['path'].startswith(work) \
                else os.path.relpath(rg['path'], work)
            cover = [i for i in by_file.get(path, []) if units[i]['line'] <= rg['startLine'] and rg['endLine'] <= units[i]['end']]
            if cover:
                members.append(min(cover, key=lambda i: units[i]['lines']))
        groups.append((members, res['properties']['similarityPercent']))
    return groups


def name_groups(units):
    by = defaultdict(list)
    for i, u in enumerate(units):
        # HTML — нет: `div.card` в каждом файле, имя там ничего не говорит.
        if u['kind'] != 'block' and u['lang'] != 'html' and u['short'] not in IDIOM_NAMES \
                and (u['lines'] >= MIN_LINES or (u['lang'] == 'css' and comparable(u))):
            by[(u['lang'], u['short'])].append(i)
    return [ix for ix in by.values() if len({units[i]['file'] for i in ix}) > 1]


def judge_bin():
    """Голый бинарь CLI для судьи, НЕ обёртка `claude` с PATH: та добавила бы
    бриф сессии, MCP и флаги. Судья идёт без настроек, инструментов и модов,
    так что патчи режима trah ему не нужны и не мешают: сборка trah, если есть,
    иначе свежая версия из ~/.local/share/claude/versions."""
    if os.environ.get('DEDUP_JUDGE_BIN'):
        return os.environ['DEDUP_JUDGE_BIN']
    share = os.path.expanduser('~/.local/share/claude')
    trah = os.path.join(share, 'trah', 'current')
    if os.access(trah, os.X_OK):
        return trah
    vdir = os.path.join(share, 'versions')
    try:
        # На Windows версия лежит с `.exe` (не проверено на живой машине — см. SETUP.md).
        vers = [v for v in os.listdir(vdir) if re.fullmatch(r'\d+(\.\d+)*(\.exe)?', v)
                and os.access(os.path.join(vdir, v), os.X_OK)]
    except OSError:
        vers = []
    if vers:
        return os.path.join(vdir, max(vers, key=lambda v: tuple(map(int, v.removesuffix('.exe').split('.')))))
    return None


def judge_brief():
    """Бриф судьи: общий каркас комплекта и вставка проекта (что за код,
    примеры, ловушки) на место @PROJECT@. Собранный лежит в кэше корня."""
    core = open(os.path.join(HERE, 'judge-brief.md'), encoding='utf8').read()
    try:
        part = open(PROJECT_BRIEF, encoding='utf8').read().strip()
    except OSError:
        part = ''
    text_ = core.replace('@PROJECT@', part)
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, 'judge-brief.md')
    if not os.path.exists(path) or open(path, encoding='utf8').read() != text_:
        open(path, 'w', encoding='utf8').write(text_)
    return path, text_


JUDGE_MODEL = 'haiku'
JUDGE_BATCH = 5        # групп на один вызов модели
JUDGE_WORKERS = 4      # вызовов одновременно
JUDGE_LINES = 45       # строк кода на члена группы
JUDGE_MEMBERS = 4      # членов группы, что видит судья: центр и сильнейшие


def group_code(row):
    """Код группы для судьи: центр и сильнейшие соседи, обрезанные по строкам."""
    parts = []
    for n, u in enumerate(row['units'][:JUDGE_MEMBERS], 1):
        try:
            lines = open(os.path.join(ROOT, u['file']), encoding='utf8', errors='replace').read().split('\n')
        except OSError:
            continue
        body = lines[u['line'] - 1:u['line'] - 1 + min(u['lines'], JUDGE_LINES)]
        cut = ' (cut)' if u['lines'] > JUDGE_LINES else ''
        parts.append(f"### member {n}: {u['file']}:{u['line']} {u['name']}{cut}\n" + '\n'.join(body))
    return '\n\n'.join(parts)


def call_judge(batch, think=False):
    """Один вызов Haiku голым бинарём CLI, без хуков, MCP и настроек: ~3 с на
    вызов (замер 30.09). --bare не годится — он не видит вход по подписке
    («Not logged in»), а API-ключа в системе нет.

    Поломка не глотается молча: причина пишется в last-error.json. До 02.10 любая
    ошибка давала `{}`, и сломанный судья выглядел как «дублей нет»."""
    binary = judge_bin()
    if binary is None:
        note_error('судья: нет бинаря CLI (~/.local/share/claude/versions пуст, DEDUP_JUDGE_BIN не задан)')
        return {}
    brief_path, _ = judge_brief()
    env = {**os.environ, 'MAX_THINKING_TOKENS': '0'} if not think else dict(os.environ)
    prompt = '\n\n'.join(f"## group {gid}\n{code}" for gid, code in batch)
    r = None
    try:
        r = subprocess.run([binary, '-p', '--model', JUDGE_MODEL, '--no-session-persistence',
                            '--setting-sources', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                            '--disable-slash-commands', '--tools', '', '--output-format', 'json',
                            # Без размышления: с ним одна группа шла 25 с и 2064
                            # выходных токена ради ответа в 70 (замер 30.09).
                            # --effort low его не выключает.
                            '--settings', '{"alwaysThinkingEnabled":%s}' % ('true' if think else 'false'),
                            '--append-system-prompt-file', brief_path],
                           input=prompt, capture_output=True, text=True, timeout=180, cwd='/tmp', env=env)
        out = json.loads(r.stdout)
        res = (out[-1] if isinstance(out, list) else out).get('result', '')
        arr = json.loads(res[res.index('['):res.rindex(']') + 1])
        return {int(x['id']): x for x in arr if 'id' in x}
    except (subprocess.SubprocessError, ValueError, KeyError, TypeError, OSError) as e:
        tail = ((r.stderr or r.stdout or '')[-300:] if r is not None else '')
        note_error(f'судья ({os.path.basename(binary)}): {type(e).__name__}: {e} {tail}'.strip())
        return {}


JUDGE_RETHINK = 0.9    # ниже этой оценки DUP быстрого судьи перепроверяется с размышлением


def judge(rows, n, rethink=False):
    """Метки DUP/IDIOM/NO для первых n групп.

    Быстрый проход (без размышления) — все группы. rethink — ещё раз, с
    размышлением, группы, где быстрый сказал DUP при оценке инструмента ниже
    JUDGE_RETHINK: туда проходит мусор. Замер 30.09 на отложенном CSMoneyBot
    (50 групп, слепая разметка): быстрый — мусора пропущено 5/16, дублей
    оставлено 32/34, 19 с; с размышлением целиком — 2/16 и 33/34, 197 с;
    rethink — 4/16 и 32/34, 126 с. Судья с размышлением непостоянен: два его
    прогона на тех же 9 группах разошлись, и выигрыш на такой выборке — в
    пределах разброса. Поэтому по умолчанию только быстрый. Кэш — по хэшу брифа, кода и режима
    (~/.cache/dedup/judge.json): тот же код — та же метка без вызова."""
    import hashlib
    from concurrent.futures import ThreadPoolExecutor
    path = os.path.join(CACHE, 'judge.json')
    try:
        cache = json.load(open(path))
    except (OSError, ValueError):
        cache = {}
    _, brief = judge_brief()
    asked = calls = 0

    def run(picked, think):
        nonlocal asked, calls
        todo = []
        for k in picked:
            code = group_code(rows[k])
            # В ключе бриф и режим: новый бриф — новые метки, а не старые из кэша.
            mode = ('think:' if think else '') + ('' if JUDGE_MODEL == 'haiku' else JUDGE_MODEL + ':')
            h = hashlib.sha1((mode + brief + code).encode()).hexdigest()
            if h in cache:
                rows[k]['judge'] = cache[h]
            else:
                todo.append((k, h, code))
        batches = [todo[i:i + JUDGE_BATCH] for i in range(0, len(todo), JUDGE_BATCH)]
        asked += len(todo)
        calls += len(batches)
        # Второй круг — по одной группе то, что не вернулось: пакет целиком
        # теряется от одного кривого JSON в ответе (5 групп CSGOMarketParser 30.09).
        for attempt in range(2):
            with ThreadPoolExecutor(JUDGE_WORKERS) as pool:
                for batch, got in zip(batches, pool.map(lambda b: call_judge([(k, c) for k, _, c in b], think), batches)):
                    for k, h, _ in batch:
                        if k in got and got[k].get('label') in ('DUP', 'IDIOM', 'NO'):
                            v = {x: got[k].get(x, '') for x in ('label', 'why', 'members', 'keep')}
                            v['by'] = 'think' if think else 'fast'
                            rows[k]['judge'] = cache[h] = v
            lost = [t for b in batches for t in b if 'judge' not in rows[t[0]] or rows[t[0]]['judge'].get('by') is None]
            if not lost or attempt:
                break
            batches = [[t] for t in lost]
            calls += len(batches)

    picked = []
    for k, r in enumerate(rows[:n]):
        if r['signals'] == ['file']:
            r['judge'] = {'label': 'DUP', 'why': 'скопированный файл', 'members': [], 'keep': '', 'by': 'file'}
        else:
            picked.append(k)
    run(picked, False)
    if rethink:
        run([k for k in picked if (rows[k].get('judge') or {}).get('label') == 'DUP'
             and rows[k]['score'] < JUDGE_RETHINK], True)
    # Под блокировкой и с догрузкой: параллельные прогоны (стенд брифов, хуки
    # нескольких сессий) иначе затирали друг другу метки — выживал последний.
    with dedupconf.lock(path + '.lock'):
        try:
            disk = json.load(open(path))
        except (OSError, ValueError):
            disk = {}
        disk.update(cache)
        tmp = path + '.tmp-' + str(os.getpid())
        json.dump(disk, open(tmp, 'w'), ensure_ascii=False)
        os.replace(tmp, path)
    return asked, calls


FOCUS_VOCAB = 0.5      # порог сходства словаря для защёлки: ниже — шум для правки
FOCUS_NAMED = 0.3      # тот же порог, если и имя совпало
FOCUS_MAX = 8          # пар на одну проверку хука: больше — это уже не правка, а долг


def focus(path, new_only):
    """Функции одного файла против проекта и общего кода — для хука-защёлки.

    Сравнение — разреженное умножение строк файла на матрицу словаря (схема
    обратного индекса SourcererCC), без treepeat и без пар «все со всеми»: на
    правку нужны секунды. new_only — только пары, которых нет в базовой линии
    <CACHE>/baseline-<проект>-<сторона>-<CORPUS_KEY>.json; найденные туда
    дописываются, и одно и то же не повторяется на следующей правке. Первая
    правка в проекте строит линию по всему проекту разом и молчит: весь
    старый долг — не новость. Смена пропусков или общего кода меняет
    CORPUS_KEY, и линия строится заново сама."""
    full = os.path.abspath(path)
    rel = os.path.relpath(full, ROOT)
    if rel.startswith('..'):
        return []
    scope = next((s for s, (_, exts) in SCOPES.items() if rel.endswith(exts)), None)
    if scope is None or (SCOPES_ON and scope not in SCOPES_ON) or rel.endswith('_test.go'):
        return []
    if any(rel == r[2] or rel.startswith(r[2].rstrip(os.sep) + os.sep) for r in REFS):
        return []  # правка самого общего кода — не находка против него
    if scope in WEB_SCOPES and (os.sep + 'lib' + os.sep) in rel:
        return []  # вендорная копия общей библиотеки
    if LAYOUT == 'subprojects':
        if os.sep not in rel:
            return []
        proj = target = rel.split(os.sep)[0]
    else:
        proj, target = os.path.basename(ROOT), '.'
    targets = parse_targets([target + ':' + scope])
    if not targets:
        return []
    units = catalog(targets, [r for r in REFS if r[1] == scope])
    lang = SCOPES[scope][0]
    idx = [i for i, u in enumerate(units) if u['lang'] == lang and comparable(u)]
    if len(idx) < 2:
        return []
    vec = TfidfVectorizer(analyzer=lambda ws: ws, sublinear_tf=True, max_df=0.2)
    X = vec.fit_transform([units[i]['words'] for i in idx])
    vocab = np.array(vec.get_feature_names_out())
    if not new_only:
        return pairs_in(units, idx, X, vocab, {rel})
    os.makedirs(CACHE, exist_ok=True)
    bpath = os.path.join(CACHE, f'baseline-{proj}-{scope}-{CORPUS_KEY}.json')
    # Под замком: две сессии на одном проекте иначе затирали друг другу линию,
    # и пара, записанная первой, всплывала у второй ещё раз.
    with dedupconf.lock(bpath + '.lock'):
        try:
            base = set(json.load(open(bpath)))
        except (OSError, ValueError):
            base = None
        # Первый раз — линия по всем файлам проекта одним проходом, иначе — один файл.
        files = {rel} if base is not None else {u['file'] for u in units if not u['ref']}
        found = pairs_in(units, idx, X, vocab, files)
        fresh = [f for f in found if base is not None and f['id'] not in base]
        base = (base or set()) | {f['id'] for f in found}
        tmp = bpath + '.tmp-' + str(os.getpid())
        json.dump(sorted(base), open(tmp, 'w'))
        os.replace(tmp, bpath)
    return fresh


def pairs_in(units, idx, X, vocab, files):
    """Сильные пары, где хотя бы одна сторона — в files."""
    acc_pairs, acc_names = load_accepted()
    rows = [k for k, i in enumerate(idx) if units[i]['file'] in files]
    found = []
    for start in range(0, len(rows), 400):
        chunk = rows[start:start + 400]
        S = (X[chunk] @ X.T).tocoo()
        for r, c, v in zip(S.row, S.col, S.data):
            i, j = idx[chunk[r]], idx[c]
            if v < FOCUS_NAMED or i == j:
                continue
            a, b = units[i], units[j]
            named = a['short'] == b['short'] and a['short'] not in IDIOM_NAMES
            if (v < FOCUS_VOCAB and not named) or overlaps(a, b) or a['ref']:
                continue
            if a['file'] == b['file'] and owner(a) is not None and owner(a) == owner(b):
                continue
            if a['short'] in acc_names or b['short'] in acc_names or pair_id(a, b) in acc_pairs:
                continue
            both = X[chunk[r]].multiply(X[c]).toarray()[0]
            found.append({'id': pair_id(a, b), 'vocab': round(float(v), 2), 'named': named,
                          'units': [{k: u[k] for k in ('file', 'line', 'end', 'name', 'kind', 'lines', 'ref')}
                                    for u in (a, b)],
                          'shared': [vocab[k][2:] for k in np.argsort(-both)[:5] if both[k] > 0],
                          'mine': f"{a['file']}:{a['line']} {a['name']}",
                          'other': f"{'общий ' if b['ref'] else ''}{b['file']}:{b['line']} {b['name']}"})
    uniq = {}
    for f in found:
        if f['id'] not in uniq or f['vocab'] > uniq[f['id']]['vocab']:
            uniq[f['id']] = f

    def inside(x, y):
        return x['file'] == y['file'] and y['line'] <= x['line'] and x['end'] <= y['end']

    # Копия целого узла — одна находка: скопированная страница давала пары
    # `div.app`, вложенного в него `main.main` и ещё глубже — всё один и тот же код.
    kept = [f for f in uniq.values()
            if not any(g is not f and inside(f['units'][0], g['units'][0]) and inside(f['units'][1], g['units'][1])
                       for g in uniq.values())]
    return sorted(kept, key=lambda f: -(f['vocab'] + 0.2 * f['named']))


def parse_targets(raw):
    out = []
    for t in raw:
        path, _, scope = t.partition(':')
        path = os.path.expanduser(path) or '.'
        # Абсолютный путь — проект вне корня; os.path.join(ROOT, path) тогда
        # даёт сам path, и имя проекта — его последний каталог. `.` — сам корень.
        if os.path.isabs(path):
            proj = os.path.basename(path.rstrip(os.sep))
        else:
            proj = os.path.basename(ROOT) if path in ('.', './') else path
        default = sorted(SCOPES_ON) or (['back', 'front']
                                        + (['rust'] if os.path.isfile(os.path.join(ROOT, path, 'Cargo.toml')) else []))
        for s in ([scope] if scope else default):
            # Веб-стороны — в <проект>/web, если он есть (так у ботов), иначе весь проект.
            web = os.path.join(path, 'web')
            sub = web if s in WEB_SCOPES and os.path.isdir(os.path.join(ROOT, web)) else path
            if os.path.isdir(os.path.join(ROOT, sub)):
                out.append((proj, s, sub))
    return out


def main():
    if sys.argv[1:2] == ['--version']:
        print(f'dedup {VERSION}, корень {ROOT}, настройка {"есть" if CONF else "нет"}')
        return 0
    if len(sys.argv) > 2 and sys.argv[1] == '--focus':
        # dedup.sh --focus FILE... [--new-only] [--judge] [--json] — пары
        # функций файлов, для хука-защёлки. --judge — метка Haiku каждой паре.
        # Код 3 — судья не ответил хотя бы по одной паре (причина в last-error.json):
        # хук отличает «дублей нет» от «судья сломан».
        files = [x for x in sys.argv[2:] if not x.startswith('--')]
        found = []
        for f in files:
            found.extend(focus(f, '--new-only' in sys.argv))
        found = found[:FOCUS_MAX]
        unjudged = 0
        if '--judge' in sys.argv and found:
            rows = [{'units': f['units'], 'signals': ['vocab'], 'score': f['vocab']} for f in found]
            judge(rows, len(rows))
            for f, r in zip(found, rows):
                f['judge'] = r.get('judge')
            unjudged = sum(1 for f in found if not f['judge'])
        if '--json' in sys.argv:
            print(json.dumps(found, ensure_ascii=False))
            return 3 if unjudged else 0
        for f in found:
            j = f.get('judge') or {}
            print(f"{f['vocab']:.2f}{' name' if f['named'] else ''}  {f['mine']}  ≈  {f['other']}  "
                  f"[{', '.join(f['shared'])}]" + (f"  → {j.get('label')}: {j.get('why', '')}" if j else ''))
        return 3 if unjudged else 0
    ap = argparse.ArgumentParser()
    ap.add_argument('targets', nargs='+')
    ap.add_argument('--cross', action='store_true', help='только группы из разных проектов')
    ap.add_argument('--ref', action='store_true', help='сверка с общим кодом из refs настройки')
    ap.add_argument('--sim', type=float, default=0.35, help='порог сходства словаря (0.3 — полнее, больше шума)')
    ap.add_argument('--top', type=int, default=80)
    ap.add_argument('--out')
    ap.add_argument('--judge', type=int, default=0, metavar='N',
                    help='разметить первые N групп моделью Haiku (DUP/IDIOM/NO), кэш по хэшу кода')
    ap.add_argument('--only-dup', action='store_true', help='в candidates.md — только группы с меткой DUP')
    ap.add_argument('--rethink', action='store_true',
                    help='DUP с оценкой < 0.9 перепроверить судьёй с размышлением (в ~7 раз дольше)')
    a = ap.parse_args()
    targets = parse_targets(a.targets)
    refs = [r for r in REFS if a.ref and r[1] in {t[1] for t in targets}]
    units = catalog(targets, refs)
    out_dir = a.out or '/tmp/dedup-' + '-'.join(os.path.basename(x.rstrip(os.sep)).replace(':', '_')
                                                 for x in a.targets) \
        + ('-cross' if a.cross else '') + ('-ref' if a.ref else '')
    os.makedirs(out_dir, exist_ok=True)
    json.dump([{k: u[k] for k in ('project', 'file', 'line', 'name', 'kind', 'lines', 'head')}
               for u in units if u['kind'] != 'block' and not u['ref']],
              open(os.path.join(out_dir, 'catalog.json'), 'w'), ensure_ascii=False, indent=1)

    ev = defaultdict(lambda: {'signals': set(), 'vocab': 0.0, 'shared': [], 'shape': 0.0})
    acc_pairs, acc_names = load_accepted()
    skipped = 0

    def link(x, y, sig, vocab=0.0, shared=None, shape=0.0):
        nonlocal skipped
        if x == y or overlaps(units[x], units[y]) or (units[x]['ref'] and units[y]['ref']):
            return
        if units[x]['short'] in acc_names or units[y]['short'] in acc_names \
                or pair_id(units[x], units[y]) in acc_pairs:
            skipped += 1
            return
        e = ev[(min(x, y), max(x, y))]
        e['signals'].add(sig)
        if vocab > e['vocab']:
            e['vocab'], e['shared'] = vocab, shared or []
        e['shape'] = max(e['shape'], shape)

    for i, j, v, top in vocab_pairs(units, a.sim):
        link(i, j, 'vocab', vocab=v, shared=top)
    for members, pct in shape_groups(units) if units else []:
        for x in members:
            for y in members:
                if x < y:
                    link(x, y, 'shape', shape=pct)
    for ix in name_groups(units):
        for x in ix:
            for y in ix:
                if x < y:
                    link(x, y, 'name')

    def strength(i, j, e):
        # Основа — сильнейший из двух сигналов: 100% формы у крошечного
        # firstNonEmpty весит как полное совпадение словаря, а не как его
        # слабый словарь (был на 351-м месте из 368).
        sig = e['signals']
        base = max(e['vocab'], e['shape'] / 100)
        agree = 0.25 * (('vocab' in sig) + ('shape' in sig) + ('name' in sig) - 1)
        cross = units[i]['project'] != units[j]['project'] or units[i]['ref'] or units[j]['ref']
        size = min(units[i]['lines'], units[j]['lines'])
        # Методы одного типа и замыкания одного окна в одном файле похожи
        # по природе — общие поля (`Items.Load` ≈ `Items.Put`), а не копия.
        kin = units[i]['file'] == units[j]['file'] and owner(units[i]) is not None \
            and owner(units[i]) == owner(units[j])
        return base + agree + 0.1 * ('name' in sig) + 0.05 * (units[i]['file'] != units[j]['file']) \
            + 0.15 * cross + 0.1 * min(1.0, size / 40) - 0.3 * kin

    # Режим решает, какие пары вообще рассматриваются: --cross — только между
    # разными проектами, --ref — только «проект ↔ общий код». Раньше группа
    # проходила фильтр, если в ней нашёлся хоть один чужой, и в --ref всплывали
    # связи внутри одного бота (LockItemConditions ≈ SetProxyConnLimits).
    def wanted(i, j):
        ui, uj = units[i], units[j]
        if a.ref and not a.cross:
            return ui['ref'] != uj['ref']
        if a.cross:
            return ui['ref'] != uj['ref'] or ui['project'] != uj['project']
        return True
    edges = {k: e for k, e in ev.items() if wanted(*k)}

    # Пара разных уровней: `header` одного бота ≈ `nav` другого, когда свой `nav`
    # первого похож на него сильнее. Уходит пара, где ЧАСТЬ одного члена похожа
    # на другой член сильнее, чем весь член; копия целиком (div.app ≈ div.app)
    # сильнее пар своих частей и остаётся.
    adj = defaultdict(dict)
    for (i, j), e in edges.items():
        adj[i][j] = adj[j][i] = strength(i, j, e)

    def part_of(z, x):
        return z != x and units[z]['file'] == units[x]['file'] \
            and units[x]['line'] <= units[z]['line'] and units[z]['end'] <= units[x]['end']

    edges = {(i, j): e for (i, j), e in edges.items()
             if not any(part_of(z, x) and s > adj[x][y] for x, y in ((i, j), (j, i)) for z, s in adj[y].items())}
    # Копия целого узла — одна находка, как и в защёлке: шапка страницы CSMoneyBot
    # шла четырьмя группами — header и три его части, каждая против той же копии.
    # Только если пара целых не слабее пары частей: слабо похожие функции Go не
    # должны прятать точную копию блока внутри них.
    by_file = defaultdict(list)
    for k in {m for e in edges for m in e}:
        by_file[units[k]['file']].append(k)
    up = {k: [z for z in by_file[units[k]['file']] if part_of(k, z)] for ks in by_file.values() for k in ks}
    pairs = set(edges)
    edges = {(i, j): e for (i, j), e in edges.items()
             if not any((min(x, y), max(x, y)) in pairs and adj[x][y] >= adj[i][j] - 0.1
                        for x in up[i] + [i] for y in up[j] + [j] if (x, y) != (i, j))}

    rows = []
    # Скопированный файл — одна находка, а не десятки групп: relist_rules.go
    # BuyOrderBot и CSGOMarketParser давали по группе на каждый метод.
    fn_total = defaultdict(int)
    for u in units:
        if u['kind'] != 'block':
            fn_total[u['file']] += 1
    per_files = defaultdict(set)
    for (i, j), e in edges.items():
        fi, fj = units[i]['file'], units[j]['file']
        if fi != fj and strength(i, j, e) >= 1.0 and units[i]['kind'] != 'block' and units[j]['kind'] != 'block':
            key = tuple(sorted([fi, fj]))
            per_files[key].update((i, j))
    file_copies = set()
    for (fa, fb), ms in per_files.items():
        na = len({m for m in ms if units[m]['file'] == fa})
        nb = len({m for m in ms if units[m]['file'] == fb})
        if min(na, nb) >= 3 and min(na / fn_total[fa], nb / fn_total[fb]) >= 0.4:
            file_copies.add((fa, fb))
            ua = next(units[m] for m in ms if units[m]['file'] == fa)
            ub = next(units[m] for m in ms if units[m]['file'] == fb)
            what = {'css': 'правил', 'html': 'блоков'}.get(ua['lang'], 'функций')
            rows.append({'score': 3.0 + min(na, nb) / 100, 'signals': ['file'], 'shared': [],
                         'why': f'файл скопирован: {na} из {fn_total[fa]} {what} {fa} совпадают '
                                f'с {nb} из {fn_total[fb]} {what} {fb}',
                         'vocab': 0, 'shape': 0, 'pairs': [],
                         'projects': sorted({ua['project'], ub['project']} - {r[0] for r in REFS})
                         + (['REF'] if ua['ref'] or ub['ref'] else []),
                         'units': [{'file': u['file'], 'line': 1, 'name': '(file)', 'kind': 'file',
                                    'lines': fn_total[u['file']], 'ref': u['ref'], 'seed': k == 0}
                                   for k, u in enumerate((ua, ub))]})
    edges = {k: e for k, e in edges.items()
             if tuple(sorted([units[k[0]]['file'], units[k[1]]['file']])) not in file_copies}

    # Звёзды, а не связные компоненты: цепочка A≈B≈C≈… склеивала в одну группу
    # 253 функции SellManager. Группа — центр и его ПРЯМЫЕ соседи (не больше
    # GROUP_MAX сильнейших). Группы могут пересекаться: функция с двумя разными
    # копиями стоит в обеих, и каждая найденная пара попадает хотя бы в одну.
    nbr = defaultdict(dict)
    for (i, j), e in edges.items():
        s = strength(i, j, e)
        nbr[i][j] = nbr[j][i] = (s, e)
    order = sorted(edges.items(), key=lambda kv: -strength(kv[0][0], kv[0][1], kv[1]))
    covered, seeds = set(), set()
    for (i, j), _ in order:
        if (i, j) in covered:
            continue
        if a.ref and not a.cross:
            seed = i if units[i]['ref'] else j          # центр — общий код
        elif i in seeds and j not in seeds:
            seed = j                                    # центр уже был — берём другой конец
        elif j in seeds and i not in seeds:
            seed = i
        elif i in seeds and j in seeds:
            seed = None                                 # оба были центрами: пара сама по себе
        else:
            seed = i if len(nbr[i]) >= len(nbr[j]) else j
        if seed is None:
            seed, near = i, [j]
        else:
            other = j if seed == i else i
            near = [k for k in sorted(nbr[seed], key=lambda k: -nbr[seed][k][0])
                    if (min(seed, k), max(seed, k)) not in covered][:GROUP_MAX - 1]
            if other not in near:
                near = near[:GROUP_MAX - 2] + [other]
        seeds.add(seed)
        # Соседи центра между собой не проверялись: в группу попадали функция и
        # её же блок — один код дважды, и судья честно звал их «идентичными».
        members = [seed]
        for k in near:
            if not any(overlaps(units[k], units[m]) for m in members):
                members.append(k)
        if len(members) < 2:
            continue
        # Покрыты все пары внутри группы, а не только с центром: иначе та же
        # группа повторялась с каждым участником в роли центра (шесть копий
        # memo-обёрток SellManager подряд).
        for x in members:
            for y in members:
                if x < y:
                    covered.add((x, y))
        projs = {units[m]['project'] for m in members if not units[m]['ref']}
        has_ref = any(units[m]['ref'] for m in members)
        if not projs:
            continue
        links = [nbr[seed][k] for k in members[1:]]
        sig = set().union(*(e['signals'] for _, e in links))
        best = max(links, key=lambda se: se[1]['vocab'])[1]
        shape = max(e['shape'] for _, e in links)
        why = []
        if shape:
            why.append(f'форма {shape:.0f}% при обезличенных именах')
        if best['vocab']:
            kinds = {'c': 'вызовы', 'f': 'поля', 's': 'строки', 't': 'типы', 'n': 'числа', 'p': 'свойства',
                     'v': 'декларации', 'e': 'теги', 'k': 'классы', 'i': 'id', 'a': 'атрибуты'}
            by = defaultdict(list)
            for w in best['shared'][:6]:
                by[kinds.get(w[0], '?')].append(w[2:])
            why.append(f"словарь {best['vocab']:.2f}: " + '; '.join(k + ' ' + ', '.join(v) for k, v in by.items()))
        if 'name' in sig:
            why.append(f"одно имя «{units[seed]['short']}» в разных файлах")
        if len(projs) > 1:
            why.append('разные проекты')
        if has_ref:
            why.append('есть в общем коде')
        rows.append({'score': round(max(s for s, _ in links), 3), 'signals': sorted(sig), 'shared': best['shared'],
                     'why': ' · '.join(why), 'pairs': [pair_id(units[seed], units[k]) for k in members[1:]],
                     'vocab': round(best['vocab'], 3), 'shape': shape,
                     'projects': sorted(projs) + (['REF'] if has_ref else []),
                     'units': [{'file': units[m]['file'], 'line': units[m]['line'], 'name': units[m]['name'],
                                'kind': units[m]['kind'], 'lines': units[m]['lines'], 'ref': units[m]['ref'],
                                'seed': m == seed}
                               # Порядок — центр, затем соседи по силе: судья видит
                               # первые JUDGE_MEMBERS. В порядке файлов настоящая
                               # пара группы из 12 часто не попадала ему на глаза.
                               for m in members]})
    rows.sort(key=lambda r: -r['score'])
    judged = None
    if a.judge:
        s = __import__('time').time()
        asked, calls = judge(rows, a.judge, a.rethink)
        judged = (asked, calls, __import__('time').time() - s)
    json.dump(rows, open(os.path.join(out_dir, 'candidates.json'), 'w'), ensure_ascii=False, indent=1)

    fn_count = sum(1 for u in units if u['kind'] != 'block' and not u['ref'])
    md = [f"# Кандидаты в дубли — {' '.join(a.targets)}" + (' · между проектами' if a.cross else '')
          + (' · против общего кода' if a.ref else ''), '',
          f'{fn_count} функций, {len(rows)} групп (порог словаря {a.sim}). Сильнейшие сверху.', '']
    shown = [r for r in rows if not a.only_dup or (r.get('judge') or {}).get('label') == 'DUP']
    for n, r in enumerate(shown[:a.top], 1):
        j = r.get('judge')
        md.append(f"## {n}. " + (f"**{j['label']}** · " if j else '') + f"{' + '.join(r['signals'])} · vocab {r['vocab']}"
                  + (f" · shape {r['shape']:.0f}%" if r['shape'] else '') + ' · ' + ', '.join(r['projects']))
        for u in r['units']:
            md.append(f"- {'**общий** ' if u['ref'] else ''}`{u['file']}:{u['line']}` {u['name']}"
                      f" ({u['kind']}, {u['lines']} lines)")
        md.append('  почему: ' + r['why'])
        if j:
            md.append(f"  судья: {j.get('why', '')}" + (f" · оставить: {j['keep']}" if j.get('keep') else ''))
        md.append('')
    open(os.path.join(out_dir, 'candidates.md'), 'w').write('\n'.join(md))
    # Группы пересекаются — считаем различные функции в них, а не сумму строк.
    seen = {(u['file'], u['line']) for r in rows for u in r['units'] if not u['ref'] and u['kind'] != 'block'}
    top = sum(1 for r in rows if r['score'] >= 1.0)
    print(f"{' '.join(a.targets)}: {fn_count} functions, {len(rows)} groups ({top} strong, score ≥ 1.0), "
          f"{len(seen)} functions involved" + (f', {skipped} accepted pairs skipped' if skipped else '')
          + f" → {out_dir}/candidates.md")
    if judged:
        asked, calls, sec = judged
        lab = defaultdict(int)
        for r in rows[:a.judge]:
            lab[(r.get('judge') or {}).get('label') or 'unjudged'] += 1
        print(f"  judge: {a.judge} groups, {asked} asked in {calls} calls, {sec:.0f}s · "
              + ', '.join(f'{k} {v}' for k, v in sorted(lab.items())))


if __name__ == '__main__':
    sys.exit(main())
