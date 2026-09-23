# Переезд машины lotm-desktop на claude-trah под Windows и чистка окружения

Начат 23.09.2026. Ветка `windows` в `D:\claude-trah` (клон `GWSAnyone/claude-trah`).

## Решения владельца (23.09)

- Домашний каталог `C:\Users\lotm` **отвязать от TAUSIK**: TAUSIK остаётся только в
  проектах на `D:\`, `~/.claude` становится чистым глобальным профилем.
- **Основа комплекта — claude-trah**, портированный под Windows. `D:\tausozavr` уходит
  в архив после того, как из него забрано ценное (порт обёртки, `patch-tweakcc.py`,
  куски брифа под эту машину).
- Делать все фазы: 0 страховка → 1 противоречия → 2 мёртвый груз → 3 свести в одно →
  4 взять из trah → 5 патчи бинарника. Удаления — каждое отдельным «да».

## Где я сейчас

**Обновлено 2026-09-23 14:55.**
**Фаза:** 5 — живая проверка `sys-compact-on-order`. Копия собрана (`8395b79`), эта
сессия уже идёт на `~/.local/share/claude/trah/current.exe` (`cfg trah`, `TRAH_MODE=1`).
**В работе прямо сейчас:** заказан `/compact` через `python ~/.claude/hooks/compact-order.py`.
**Следующее действие:** посмотреть в стенограмме, исполнился ли кадр командой
(`<command-name>/compact</command-name>` после кадра с `selfSent`) — если да, фаза 5
закрыта, дальше дефект 7 (`compact-order` берёт cwd процесса) и пункты «Дальше» 3–7;
если `/compact` приехал текстом — разбирать `selfSent` (`childTokenPresented`) на Windows.
**Незакоммичено:** `D:\claude-trah` — только фантомы CRLF (16 файлов, содержимое не
изменено); коммиты `7feab62`, `8395b79` не запушены.
**Открытые вопросы:** push ветки `windows`; удалить ли ветки `worktree-agent-*` в
`D:\asynchronus` (правки 41 worktree сохранены в `D:\_backups\2026-09-23-cleanup\asynchronus-worktrees\`).

Сделано после переключения: хаб TAUSIK `ff71ce8` — bootstrap больше не стирает скиллы
проекта, роздано на 14 проектов без потерь (снимок `pre-sync\`); `mis-etalon` в реестре.

Фаза 0 сделана: `D:\_backups\2026-09-23-cleanup\` — `claude-config.zip` (без
стенограмм и кешей, 28 932 записи), `tausozavr-uncommitted.patch` (git diff --binary),
`tausozavr-untracked.zip` (14 файлов). Клон trah на ветке `windows`.

Фаза 1 (частично): дом отвязан от TAUSIK — 30 записей перенесены в
`D:\_backups\2026-09-23-cleanup\home-tausik-detached\` (`restore.json`). Остаток
`~/.tausik` (db держат живые MCP-серверы; 9 файлов уже удалены срывом `shutil.move`,
полная копия в бэкапе) — удалить после закрытия сессий. Автопамять обновлена
(`mcp-render-patch`, `tausozavr`, новая `claude-trah-migration`).

Открыто в фазе 1: `/commit` в хабе `~/.tausik-lib` (Co-Authored-By + heredoc против
брифа) — хаб сам TAUSIK-проект на ветке `release/1.8-batch-s126`, а бриф говорит
`port/hook-coverage`; нужно решение владельца. `serena-first.md` и ошибки брифа —
заменяются в фазе 4 версиями trah.

**Важно для фазы 4:** в незакоммиченных правках tausozavr уже лежат Windows-починки
старого комплекта (см. автопамять `tausozavr-windows-defects`): `.gitattributes eol=lf`,
`в_json` в install-kit, `nudge-serena` (os.sep/normcase, shlex без escape, PowerShell),
`trah.py` раскладывает правки по модулям chunk-*.js, `current.exe` копией, `patch-tweakcc.py`.
Их переносить, а не изобретать заново.

Фаза 2 сделана: удалены `~/.local/share/claude/trah` (1,1 ГБ) и
`D:\tausozavr-backup-claude-20260823-204809`; в `phase2-dead-weight\` (с `restore.json`)
уехали MCP-патч, 5 бэкапов settings, skill-compass, heart, 5 неподключённых хуков,
тесты из живых hooks; дубль `outputStyle` снят. `security-guidance` оставлен (решение владельца).

Фаза 4 (порт кода) — **все 33 набора проверок зелёные под Windows** (`python trah tests`).
Сделано на ветке `windows` (не закоммичено):
- `.gitattributes eol=lf` (+ `*.cmd` CRLF), рабочее дерево переведено в LF;
  `.gitignore` — только корневые `/.claude/`, `/.serena/`; шаблон проекта дописан
  (`project-template/.claude/brief.md`, `rules/docs-layout.md`).
- `bin/claude`: ветка `IS_WIN` (claude.exe, без `-x`, `cygpath -w` для брифа/MCP/`/dev/null`,
  `current.exe`, JSON-экранирование корня Serena); `CLAUDE_WRAPPER_PLATFORM` для тестов.
  `bin/claude.cmd` — шим из живой установки.
- `hooks/sockmsg.py`: named pipe + строка `auth` с `CLAUDE_CODE_MESSAGING_TOKEN`;
  `есть_канал()`; `compact-order` на него. Проверено живьём кадром в сессию.
- `/tmp` → TMPDIR-если-есть-иначе-`tempfile.gettempdir()` (6 файлов).
- `checkpoint.py`: `transcripts_dir` кодирует как CLI (`[^A-Za-z0-9-]`→`-`), толчок в try.
- `guard-destructive`: `rm -rf /c`/`C:\`, PowerShell `Remove-Item` по корню/дому,
  согласие, управляемое соседним отказом («не надо пока коммитить» = отказ);
  `modules.json` — гард на `Bash|PowerShell`.
- `nudge-serena`: `under()` normcase/os.sep, shlex без escape на nt, командлеты PS,
  системные каталоги Windows чужие.
- `check-edit` / `cache-tap`: запуск Git Bash, а не WSL `System32\bash.exe`
  (иначе КАЖДАЯ правка .sh = «не разбирается»).
- `install-kit`/`inventory`/`swap-remind-hook`: `в_шаблон()` — пути прямыми косыми в JSON;
  ключи памятки posix.
- `restore-claude-wrapper`: на Windows обслуживает `~/.local/claude-wrapper/{claude-wrapper.sh,claude.cmd}`,
  предупреждает, если `claude` в PATH резолвится мимо шима.
- Тесты: общее ухо `hooks/ear_for_tests.py` (unix-сокет / named pipe через ctypes) для
  4 наборов петли сжатия; прочие — нормализация путей.

Коммит `3bea5e5` (ветка `windows`, без push, с разрешения владельца).

**ПЕРЕКЛЮЧЕНИЕ СДЕЛАНО 23.09.2026 ~12:00.** Машина живёт на trah-комплекте:
- `install-kit.py --replace-hooks --replace-theirs`: 58 файлов, 12 копий `*.bak-20260923-115553`
  (brief, CLAUDE.md, senior-reviewer, 2 памяти Serena, serena-first, 4 хука, settings*).
- Вручную (`scratchpad/post_install.py`): вернул `ops_register` (TAUSIK) на SessionStart;
  statusLine → `cache-tap.py` → `~/.claude/statusline/claude-hud.sh` (прежняя команда hud);
  env прежних настроек сохранён. Копия настроек до этого — `settings.json.bak-post-*`.
- Обёртка `~/.local/claude-wrapper/claude-wrapper.sh` обновлена хуком из комплекта, подаёт бриф.
- tausikd остановлен, `Pritonozavr.lnk` из автозагрузки → `phase2-dead-weight\`.
- `trah-kit-path` = `D:\claude-trah\trah-setup`.
- Проверено живьём: `nudge-compact` прислал лесенку (30M/60M) в эту же сессию по named pipe.
- В сессию уходит ~34 КБ текста (бриф 25,1 + стиль 5,5 + заглушки + MEMORY) вместо ~41 КБ
  + ~200 имён инструментов TAUSIK.

Решения владельца по ходу: sequential-thinking — убрать (раздел и инструменты агентов убраны);
tausikd — остановить и убрать из автозапуска; коммит ветки — да.

`trah-setup/global-CLAUDE.md` закоммичен — `7feab62`.

## Хаб TAUSIK (23.09, после переключения)

- Ветка хаба — `port/hook-coverage` (с неё раздаёт `update-libs.py`); строка
  `release/1.8-batch-s126` в `CLAUDE.md` хаба — устаревший автоблок, не факт.
- `/commit` приведён к брифу: без Co-Authored-By, сообщение файлом, `OWNER_OK=1 git commit -F`.
  Коммит хаба `5b2e000`, **запушен** в `Okianiwa/tausik-core` (разрешение владельца).
  Строка в `D:\tausik-ops\ratchet-log.md` от 2026-09-23.
- **Починка затирания скиллов при `/fab sync --bootstrap`** (владелец: «аккуратнее, пофиксить»):
  `bootstrap/bootstrap_copy.py::copy_skills` удалял ВСЁ вне набора → сносил проектные скиллы
  (`web-visual`, дважды). Теперь удаляет только своё: встроенные + имена реестра + памятка
  прошлой раскладки `skills/.tausik-deployed.json` (пишется каждым прогоном). Тест
  `test_non_vendor_skill_cleaned_up` заменён на `test_skill_dropped_from_tausik_is_cleaned_up`
  + новый `test_project_owned_skill_survives`; 35/35 в test_vendor. **НЕ закоммичено.**
  Полный прогон хаба идёт фоном (`tasks/bx2ey37bu.output`); единственный увиденный провал
  `test_audit_orphan_files::test_real_repo_check_zero_or_known` — зовёт `venv/bin/python`
  (POSIX), к правке не относится.
- Снимок `.claude` всех 13 проектов пишется фоном: `scratchpad/snap_projects.py snap` →
  `D:\_backups\2026-09-23-cleanup\pre-sync\` (+manifest.json с sha256); сверка — `compare`.

Следующий шаг: дождаться теста и снимка → спросить разрешение на коммит+push фикса bootstrap
→ `python D:\tausik-ops\update-libs.py --sync --bootstrap` → `snap_projects.py compare`,
вернуть пропавшее из снимка.

## Дальше

1. **Фаза 5 — закрыта 23.09, проверено вживую.** `~/.local/share/claude/trah/2.1.280.exe`
   + symlink `current.exe`; `check` 33/33 якоря, манифест 24/24 записано, `verify` — 14
   проверяемых доставлены, `trah.py tests` 33/33. Форк `~/.local/share/tweakcc-fixed`
   (`059a5e2 Support CC 2.1.280`), сборка `npx pnpm@10`. Правки сборщика под Windows:
   `EXE`-суффикс копии и ссылки; `platform` у правки (`sys-compact-on-order` — две: linux
   `S/w/g/b/C`, windows `h/p/g/w/E`); `сумма` через hashlib; черновик сверки латиницей (LIEF
   не открывает кириллический путь); `encoding="utf-8"` у subprocess (cp1251 терял «ОТЧЁТ»);
   правки файлом `edits.json`/`check.json` — `node -e` упирался в 32 767 (`ENAMETOOLONG`).
   **Живая проверка 23.09 11:55Z:** `compact-order.py` из сессии 87b3fb09 → в стенограмме
   запись `"content":"/compact"` с `origin {kind:peer, selfSent:true}`, за ней
   `compact_boundary` (`trigger: manual`, 194 567 → 11 159 токенов), затем
   `compact-continue` вернул работу сам. Петля заказного сжатия на Windows работает.
   Дефект 7 починен тем же днём (см. «Дефекты trah»).
2. Хаб TAUSIK: `/commit` велит Co-Authored-By и heredoc — противоречит брифу; хаб на ветке
   `release/1.8-batch-s126`, а прежний бриф говорил `port/hook-coverage`. Решение владельца.
3. Остаток `~/.tausik` (держат живые MCP-серверы) — удалить после закрытия сессий.
4. Навыки `checkpoint`/`frontend-design` из комплекта — примеры из чужой экосистемы.
5. Известные дефекты петли: `nudge-compact` пишет ступень до отправки; текст «told at 15M»
   при пороге 30M; `compact-order` берёт cwd процесса, guard — из payload.
6. VS Code: `bin/claude-trah` → `claudeCode.claudeProcessWrapper`, если владелец пользуется расширением.
7. `D:\tausozavr` — в архив (правки сохранены в `D:\_backups\2026-09-23-cleanup\`).

## Факты разведки (23.09)

- Якоря: 32 из 33 правок trah встречаются в `claude.exe` 2.1.280 (байтовый счёт).
  Разошёлся только `sys-compact-on-order`: в Windows-сборке объект
  `k={mode:"prompt",agentId:qe(),value:h,uuid:p,priority:g,origin:w,skipSlashCommands:!0,isMeta:!0,skipAttachments:!0}`.
- Канал сессии на Windows — named pipe `\\.\pipe\LOCAL\cc-msg-<id>`
  (`CLAUDE_CODE_MESSAGING_SOCKET`). Протокол: строка `{"type":"auth","token":$CLAUDE_CODE_MESSAGING_TOKEN}`,
  затем кадр. Проверено живьём: `scratchpad/pipe_probe.py` доставил кадр в сессию.
- `selfSent` на Windows = `childTokenPresented` (бинарь: `if(n===1||e.platform==="windows")return e.childTokenPresented;`).
  Родословная процессов не проверяется.
- В Python 3.11 под Windows `socket.AF_UNIX` нет → `sockmsg.py` переписать на pipe.
- tweakcc на Windows-exe работал: `~/.local/share/claude/trah/2.1.245` + `current.exe`
  собраны 25.08 с правками `D:\tausozavr\workspace-setup\bin\patch-tweakcc.py`
  (`TWEAKCC_MODULE`, `TWEAKCC_DUMP_DIR` — бандл порезан на chunk-*.js с 2.1.245).
- Автосжатие на машине выключено (`autoCompactEnabled: false`) — конфликта двух
  механизмов сжатия нет.

## Дефекты trah, которые чинить при порте

1. `install-kit.py:539` — `@HOME@`/`@PY@` подставляются в сырой JSON → `\U` под Windows.
   То же `inventory.py:261`. `@PY@` без кавычек ломается на пробелах в пути.
2. Гард коммита: `«не надо пока коммитить»` = согласие (`guard-destructive.py:742`,
   отказ кончается раньше согласия). Согласие по умолчанию при отсутствии стенограммы.
3. `guard-destructive` в реестре только на `Bash` — PowerShell не видит.
4. `nudge-compact.py:437` — ступень записана до отправки, отправка без try.
5. `checkpoint.py:472` — на Windows `nudge()` падает (getuid) → PreCompact-сторож не блокирует.
6. `checkpoint.py:646` — `transcripts_dir` на Windows вырождается в cwd → sweep увезёт чужие чекпоинты.
7. ~~`compact-order` берёт cwd процесса, `guard`/`continue` — cwd из payload.~~ Починено
   23.09: `checkpoint.session_cwd()` берёт `cwd` из хвоста стенограммы сессии; им пользуются
   `compact-order.py` и `checkpoint.py path`. Проверка в `compact-order.test.py` («cwd
   сессии»). Разложено в `~/.claude/hooks`, прежние копии — `D:\_backups\2026-09-23-cleanup\hooks-before-defect7`.
8. `project-template/.claude/*` не в git (`.gitignore: .claude/`).
9. `covered_by` у `trah-delegation` недостижим; `dev/check-brief-delivery.py` падает на импорте.
10. POSIX-предположения: `sha256sum`, symlink `current`, `/tmp`, `lib/python*/site-packages`,
    `read_text()` без encoding, bash-обёртка, `stat -c`, `md5sum`, `sort -V`.

## Фазы

### 1. Противоречия (живые файлы)
- `~/.claude/skills/commit/SKILL.md`: убрать Co-Authored-By и heredoc → `-F файл`.
- `C:\Users\lotm\CLAUDE.md` (13 КБ TAUSIK) → заглушка (часть отвязки дома).
- `serena-first.md`: убрать дубли брифа и разрешение Read для не-кода.
- `settings.autonomy.json`: коммит/пуш в автономе — решить с владельцем.
- Автопамять: `mcp-render-patch` (не чинит себя, патч мёртв с 2.1.233), `tausozavr`, `workspace-architecture`.
- Ошибки брифа (пути `Sites_job`/`Claude_mcp`, `get_diagnostics_for_symbol`, sequential-thinking,
  чужие примеры) — исправлять уже в кусках trah при переходе, не в tausozavr.

### 2. Мёртвый груз (каждое — отдельное «да»)
Патч отрисовки MCP; `~/.local/share/claude/trah/2.1.241` (старая сборка); неподключённые
хуки; `skill-compass`; 6 бэкапов `settings.json`; `D:\tausozavr-backup-claude-20260823-204809`
(352 МБ); старые версии плагинов в кеше; `~/.claude/security` (если плагин не нужен);
`*.test.py` в живых `hooks`; дубль `outputStyle`; `tools/heart`.

### 3. Свести в одно
Один путь правил (бриф trah + кусок машины); `CLAUDE.md` — указатели; один гард
разрушительных команд; одна версия `checkpoint`; роли систем памяти одной строкой;
ревью-агенты подрезать; `guard-session-launch` — ложные срабатывания (или убрать вместе с tausozavr).

### 4. Порт trah
Диспетчер `pretooluse.py` + `modules.json` (с PowerShell); `check-edit`; исправленный гард
коммита; `nudge-wait`; `sockmsg.py` на named pipe; install-kit под Windows; обёртка
(`claude.cmd` + `claude-wrapper.sh` из tausozavr как образец).

### 5. Патчи бинарника
tweakcc-fixed (или свой tweakcc + patch-tweakcc) на копии `claude.exe` 2.1.280; якорь
`sys-compact-on-order` под Windows-имена; проба доставки через `sink.py`; петля самосжатия.

## Что пробовали и отвергли
- Переезд на trah «как есть» — Linux-only (см. дефекты 1, 10).
