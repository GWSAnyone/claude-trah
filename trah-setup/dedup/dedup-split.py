#!/usr/bin/env python3
"""Раскладка каталога функций по категориям — фаза 2 скилла dedup.

    tools/dedup-split.py /tmp/dedup-<Project>-<scope>

Берёт catalog.json (tools/func-catalog.py) и categorized.json (ответ
агента-раскладчика: [{file, line, name, category, purpose}]), пишет
categories/<category>.json — функции категории с назначением и головой тела.
Категории меньше трёх функций не пишутся: сравнивать в них нечего.
Печатает, сколько функций раскладчик потерял: потерянная функция ни с чем не
сравнивается, и её дубль молча проходит мимо.
"""
import json, os, sys
from collections import defaultdict

d = sys.argv[1]
catalog = json.load(open(os.path.join(d, 'catalog.json')))
cats = json.load(open(os.path.join(d, 'categorized.json')))
by_key = {(x['file'], x['line']): x for x in catalog}
groups = defaultdict(list)
seen = set()
for c in cats:
    x = by_key.get((c.get('file'), c.get('line')))
    if not x:
        continue
    seen.add((x['file'], x['line']))
    groups[c['category']].append({**x, 'purpose': c.get('purpose', '')})
out = os.path.join(d, 'categories')
os.makedirs(out, exist_ok=True)
for name in os.listdir(out):
    os.remove(os.path.join(out, name))
for cat, fns in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    if len(fns) < 3:
        print(f'  skip {cat}: {len(fns)}')
        continue
    json.dump(fns, open(os.path.join(out, cat + '.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'{len(fns):4d}  {cat}')
lost = len(catalog) - len(seen)
print(f'catalog {len(catalog)}, categorized {len(seen)}, lost {lost}')
