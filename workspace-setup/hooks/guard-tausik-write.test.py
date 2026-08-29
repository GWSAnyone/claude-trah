import json, subprocess, os, textwrap
HOOK = os.path.expanduser("~/.claude/hooks/guard-tausik-write.py")
env = dict(os.environ, TAUSIK_ROLE="supervisor", CLAUDE_PROJECT_DIR="/home/kaltsit/Ledevia/SyncedProjects")

def run(cmd, tool="Bash", inp=None):
    payload = {"tool_name": tool, "tool_input": inp or {"command": cmd}}
    p = subprocess.run(["python3", HOOK], input=json.dumps(payload), capture_output=True, text=True, env=env)
    return p.returncode, (p.stderr or "").split("\n")[2] if p.returncode else ""

plan_heredoc = textwrap.dedent('''\
cd /home/kaltsit/Ledevia/SyncedProjects; python3 - <<'PY'
p = 'docs/plans/2026-08-11-market-api-contract.md'
s = open(p, encoding='utf-8').read()
s = s.replace("> База: BuyOrderBot `6425be9` · Статус: в работе", "> Статус: закрыто", 1)
open(p, 'w', encoding='utf-8').write(s)
PY''')

code_heredoc = textwrap.dedent('''\
cd /home/kaltsit/Ledevia/SyncedProjects; python3 - <<'PY'
p = 'CSMoneyBot/internal/scan/pool.go'
open(p, 'w').write("package scan")
PY''')

tz_task = textwrap.dedent('''\
tz start . frontswitch --effort high -- "Три задачи по плану.
  2. проверить, что все имена, которые импортируют страницы из '.../lib/<файл>' в BuyOrderBot/web, есть в каноне;
  3. заменить файл;
  5. дописать путь в shared/web/vendored.txt;
Отчёт: что проверил перед каждой заменой." 2>&1 | tail -2''')

cases = [
    ("план через heredoc (должен ПРОЙТИ)", plan_heredoc, 0),
    ("код через heredoc (должен БЛОКИРОВАТЬСЯ)", code_heredoc, 2),
    ("чтение с 2>/dev/null (ПРОЙТИ)", "ls docs/ && ls docs/notes 2>/dev/null", 0),
    ("редирект в план (ПРОЙТИ)", "echo x >> docs/queue/note.md", 0),
    ("редирект в код (БЛОК)", "echo x > CSMoneyBot/main.go", 2),
    ("markdown-цитата в echo (ПРОЙТИ)", "echo '> База: bot' >> docs/plans/p.md", 0),
    ("цель редиректа в кавычках, код (БЛОК)", 'echo x > "CSMoneyBot/main.go"', 2),
    ("цель редиректа в кавычках, план (ПРОЙТИ)", 'echo x > "docs/plans/мой план.md"', 0),
    # Указатель чекпоинта — единственное исключение из «только docs/*.md».
    # Без него сессия не может записать своё состояние, и после сжатия
    # контекста хук возвращает вчерашний указатель: работа продолжается
    # с чужого места, причём молча.
    ("указатель чекпоинта (ПРОЙТИ)", 'echo "{}" > .claude/.checkpoint-gwsdesktop-556a4872', 0),
    ("указатель pending (ПРОЙТИ)", 'echo "{}" > .claude/.checkpoint-pending-gwsdesktop-556a4872', 0),
    # `sed` без `-i` — чтение, а не запись. Гард, запрещающий читать, мешает
    # работе и учит не верить его отказам — а среди них есть настоящие.
    ("sed -n на чтение (ПРОЙТИ)", "sed -n '1,80p' ~/.claude/hooks/guard-tausik-write.py", 0),
    ("sed -n на код (ПРОЙТИ)", "sed -n '1,40p' CSMoneyBot/internal/scan/pool.go", 0),
    ("sed -i по коду (БЛОК)", "sed -i 's/a/b/' CSMoneyBot/internal/scan/pool.go", 2),
    ("sed -i.bak по коду (БЛОК)", "sed -i.bak 's/a/b/' CSMoneyBot/main.go", 2),
    # Карту экосистемы надзиратель ведёт сам: он один видит всё хозяйство.
    ("корневой CLAUDE.md (ПРОЙТИ)", "echo x >> CLAUDE.md", 0),
    ("CLAUDE.md бота (БЛОК)", "echo x >> DmTrading/CLAUDE.md", 2),
    # Черновик во временном каталоге — не работа: сравнить две версии файла
    # или выгрузить ответ ручки надзирателю нужно постоянно.
    ("выгрузка в /tmp (ПРОЙТИ)", 'git show abc^:CLAUDE.md > /tmp/claude_before.md && diff -q /tmp/claude_before.md CLAUDE.md', 0),
    ("код через /tmp-путь в проекте (БЛОК)", 'echo x > /tmp/../home/kaltsit/Ledevia/SyncedProjects/CSMoneyBot/main.go', 2),
    ("настройки в .claude (БЛОК)", 'echo x > .claude/settings.json', 2),
    ("хук в .claude (БЛОК)", 'echo x > .claude/hooks/checkpoint.py', 2),
    # ── Разбор не должен принимать ДАННЫЕ за команду ──────────────────
    #
    # Поймано живьём 19.08: надзиратель отдавал работнику задачу через
    # `tz start … -- "<текст>"`, а внутри текста стояло `'.../lib/<файл>'`.
    # За `>` шла закрывающая кавычка, и гард прочёл это как перенаправление
    # в файл, взяв целью три абзаца задачи. Он ответил «надзиратель не пишет
    # код» на ту самую команду, которой сам же советует отдавать работу.
    ("задача работнику с `<файл>` в тексте (ПРОЙТИ)", tz_task, 0),
    ("текст с `;` и `|` внутри кавычек (ПРОЙТИ)",
     'tz say frontswitch "сделай a; потом b | и c > d"', 0),
    ("сообщение коммита со скобкой (ПРОЙТИ)",
     'git commit -m "правка <файла> и прочее"', 0),
    # А настоящее перенаправление в код ловится по-прежнему — иначе починка
    # разбора превратилась бы в дыру.
    ("редирект в код после кавычек (БЛОК)",
     'tz say frontswitch "текст" > CSMoneyBot/main.go', 2),
    ("редирект в код с 2>&1 рядом (БЛОК)",
     'go build ./... 2>&1 > CSMoneyBot/out.go', 2),
    ("редирект в план после кавычек (ПРОЙТИ)",
     'echo "строка" >> docs/plans/p.md', 0),
]
bad = 0
# ── Цель за переменной. Обе команды взяты живьём 20.08.2026 ──────────────
#
# Надзиратель закрывал две записи очереди — работа, ради которой он и есть, —
# и получил «надзиратель не пишет код» дважды подряд, разными способами.
# Отказ был неисполним: переписывать нечего, цели разрешены, просто гард их
# не разглядел.

queue_loop = textwrap.dedent('''\
cd /home/kaltsit/Ledevia/SyncedProjects; python3 - <<'PY'
items={
"docs/queue/2026-08-19-1952-gwsdesktop-docs-00-workspace-md-razdel.md":"""
## Закрыто 20.08

Раздел `docs/00-workspace.md` про `_backups` переписан 19.08.
""",
"docs/queue/2026-08-19-2046-gwsdesktop-502-cherez-lib-api-js.md":"""
## Закрыто 20.08

Разбор по заходам — `docs/plans/2026-08-12-frontend-refactor.md`, Фаза 2в.
""",
}
for path,tail in items.items():
    t=open(path,encoding='utf-8').read().replace("status: new","status: done",1)
    open(path,"w",encoding='utf-8').write(t.rstrip()+"\n"+tail)
    print("закрыта:",path.split('/')[-1][:40])
PY''')

# То же устройство, но пишет в код: перебор по литералам обязан это ловить.
code_loop = textwrap.dedent('''\
cd /home/kaltsit/Ledevia/SyncedProjects; python3 - <<'PY'
items={"CSMoneyBot/internal/scan/pool.go": "package scan"}
for path,body in items.items():
    open(path,"w").write(body)
PY''')

# Путь назван прозой ВНУТРИ записываемого текста — это не цель записи.
prose_path = textwrap.dedent('''\
cd /home/kaltsit/Ledevia/SyncedProjects; python3 - <<'PY'
items={"docs/queue/x.md": """
Починено в `CSMoneyBot/internal/scan/pool.go`, смотри `cmd/bot/main.go`.
"""}
for path,tail in items.items():
    open(path,"w").write(tail)
PY''')

# То же, но текст записи — обычная строка, не тройная: фраза с путём внутри
# не должна становиться целью.
prose_plain = textwrap.dedent('''\
cd /home/kaltsit/Ledevia/SyncedProjects; python3 - <<'PY'
items={"docs/queue/x.md": "Починено в CSMoneyBot/internal/scan/pool.go, смотри cmd/bot/main.go."}
for path,tail in items.items():
    open(path,"w").write(tail)
PY''')

queue_var = textwrap.dedent('''\
cd /home/kaltsit/Ledevia/SyncedProjects; f=docs/queue/2026-08-19-1952-gwsdesktop.md; sed -i 's/^status: new$/status: done/' "$f"; cat >> "$f" <<'EOF'

## Закрыто 20.08 — исправлено в тот же вечер
EOF
echo "закрыта 1952"; /usr/bin/grep -m1 "^status:" "$f"''')

code_var = textwrap.dedent('''\
cd /home/kaltsit/Ledevia/SyncedProjects; f=CSMoneyBot/internal/scan/pool.go; sed -i 's/a/b/' "$f"''')

cases += [
    ("две записи очереди циклом (ПРОЙТИ)", queue_loop, 0),
    ("код циклом по словарю (БЛОК)", code_loop, 2),
    ("путь к коду прозой в тексте записи (ПРОЙТИ)", prose_path, 0),
    ("путь к коду прозой в обычной строке (ПРОЙТИ)", prose_plain, 0),
    ("запись очереди через $f (ПРОЙТИ)", queue_var, 0),
    ("код через $f (БЛОК)", code_var, 2),
    ("код через ${f} (БЛОК)", 'f=CSMoneyBot/main.go; echo x > "${f}"', 2),
    ("план через $f (ПРОЙТИ)", 'f=docs/plans/p.md; echo x >> "$f"', 0),
    # Имя, которого мы не знаем, остаётся неразвёрнутым — и это отказ, а не
    # пропуск: цель, которую не разобрали, судить не по чему.
    ("неизвестная переменная (БЛОК)", 'echo x > "$SOMEWHERE/main.go"', 2),
    # Значение через другую переменную: `d` уже известна к моменту `f`.
    ("переменная через переменную (ПРОЙТИ)", 'd=docs/plans; f=$d/p.md; echo x >> "$f"', 0),
]

# ── Собственная память сессии и ревизии git ─────────────────────────────
#
# Обе беды из доклада надзирателя 20.08.2026, обе — работа, которую он должен
# делать и не мог.

MEM = "/home/kaltsit/.claude/projects/-home-kaltsit-Ledevia-SyncedProjects/memory"

# Восстановление срезанного хвоста плана: прежняя версия берётся ревизией,
# пишется обратно в тот же разрешённый файл. Гард видел целью строку
# `HEAD:docs/plans/…` — путь, которого нет и в который никто не пишет.
revive_plan = textwrap.dedent('''\
cd /home/kaltsit/Ledevia/SyncedProjects; python3 - <<'PY'
import subprocess
p = "docs/plans/2026-08-19-context-diet.md"
old = subprocess.run(["git","show","HEAD:docs/plans/2026-08-19-context-diet.md"],capture_output=True,text=True).stdout
for path in [p]:
    open(path,"w").write(old)
PY''')

cases += [
    # Память — единственный канал, которым знание переживает конец сессии.
    ("память сессии (ПРОЙТИ)", f"echo x > {MEM}/urok.md", 0),
    ("индекс памяти (ПРОЙТИ)", f"echo x >> {MEM}/MEMORY.md", 0),
    ("память через ~ (ПРОЙТИ)",
     "echo x > ~/.claude/projects/-home-kaltsit-Ledevia-SyncedProjects/memory/u.md", 0),
    # Рядом с памятью лежат транскрипты разговоров: правило узкое намеренно.
    ("транскрипт рядом (БЛОК)",
     "echo x > ~/.claude/projects/-home-kaltsit-Ledevia-SyncedProjects/556a4872.jsonl", 2),
    ("не-md в памяти (БЛОК)", f"echo x > {MEM}/urok.py", 2),

    # Двоеточие до первой косой черты — ревизия или адрес, а не путь.
    ("восстановление плана ревизией (ПРОЙТИ)", revive_plan, 0),
    ("ревизия целью tee (ПРОЙТИ)", 'git show "HEAD:docs/x.md" | tee "HEAD:docs/x.md"', 0),
    ("адрес не путь (ПРОЙТИ)", "curl -s https://example.com/a.go > /tmp/a.go", 0),
    # Двоеточие ПОСЛЕ косой черты — обычное имя файла, запрет действует.
    ("двоеточие в имени файла (БЛОК)", "echo x > CSMoneyBot/a:b.go", 2),
]

for name, cmd, want in cases:
    code, why = run(cmd)
    ok = "ok " if code == want else "ПЛОХО"
    if code != want: bad += 1
    print(f"{ok} {name}: код={code} {why}")
print("итог:", "всё сходится" if not bad else f"{bad} расхождений")
