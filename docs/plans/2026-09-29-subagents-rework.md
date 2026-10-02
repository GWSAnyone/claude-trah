# Подагенты trah: один-два универсальных вместо general-purpose и Explore

Начато 29.09.2026. Задача владельца: разобрать, какие промпты основной агент даёт
general-purpose и Explore; собрать мнения пользователей о Sonnet 5.5; спроектировать
одного-двух своих агентов (исследование веба, скачивание и распаковка исходников
модов, чтение и картография) с продуманными промптами и настройками — для
`~/Projects` и остальных папок. critical-reviewer не трогать; senior-reviewer и
test-writer пересмотреть. Переехать на 2.1.284 (там Sonnet 5.5).

## Где я сейчас  (обновлено 2026-09-29 15:35)

**Фаза:** бриф подагента в TUI закрыт и запушен (`fdb2e23`, пробы 14:54: все четверо видят «# Brief for a subagent»). Новая задача: заказанное сжатие не срабатывало при активном `/goal`.
**Причина:** `/goal` — Stop-хук с оценщиком; «не выполнено» = блокирующая ошибка, ход продолжается, заказ `/compact` ждёт конца хода в очереди. В cli.js 2.1.284 `if(A)return …preventContinuation:!0` (остановка хуком) стоит раньше `if(ve.length>0)return{blockingErrors:ve…}`, значит `continue:false` из Stop-хука побеждает отказ оценщика.
**Сделано:** `trah-setup/hooks/compact-continue.py`, функция `придержать_ход`: на Stop при свежей метке `.compact-ordered-*` без `held` отвечает `continue:false`, дописывает `held`, mtime метки возвращает прежним. Проводка Stop в `settings-hooks.json`. Тесты 26/0, `./trah tests` 33/0. Разложено `./trah all` (бэкап `~/.claude/settings.json.bak-20260929-145722`). Живая сессия подхватила хук без перезапуска: пробная метка получила `held`, CLI показал «Stop hook stopped continuation».
**Сжатие при /goal — проверено вживую 15:40:** оценщик сказал «не выполнено», хук остановил ход, `/compact` исполнился, compact-continue вернул работу.
**Новая задача (владелец, 15:45): архив ответов подагентов.** Замер `/tmp/sub-brief/agents-audit.py` по всем транскриптам машины: файл пишут только critical-reviewer (`docs/reports/`) и researcher/GP (`docs/research/`); senior-reviewer — 73 запуска, карты 9–26 тыс. символов, ни одной на диске (Write у него нет). Новые implementer/test-writer/researcher в настоящей работе ещё не запускались, только пробы брифа.
**Сделано:** хук `trah-setup/hooks/agent-report.py` на SubagentStop — поля события в cli.js 2.1.284: `agent_id`, `agent_transcript_path`, `agent_type`, `last_assistant_message`. Пишет `<cwd>/.claude/agent-reports/<дата>-<время>-<тип>-<задача>-<id>.md`: шапка, бриф, ответ; продолжение через SendMessage дописывается в тот же файл; в папке свой `.gitignore` «*». Тест 16/0, `./trah tests` 34/0. Проводка в `settings-hooks.json`, способность в `bin/inventory.py`, абзац «Every answer is also on disk» в `fragments/trah-delegation.md`, бриф пересобран, `./trah all` разложил.
**Живая проверка 15:48 — прошла:** карта senior-reviewer легла целиком (7079 байт, бриф + ответ). Рядом лёг мусор: служебный подагент CLI с пустым `agent_type`, без транскрипта, в «ответе» — угаданная следующая реплика владельца (похоже на генератор подсказок). Отсекается по пустому типу, тест 17/0, переустановлено.
**Попутно:** `python3 trah-setup/bin/trah.py build` — это сборка CLI, а не брифа; бриф собирает `trah.py brief --write`.
**Незакоммичено:** этот план, compact-continue (.py, .test.py), `settings-hooks.json`, agent-report (.py, .test.py), `bin/inventory.py`, `fragments/trah-delegation.md`, `trah-brief.md`.
**Открытые вопросы:** коммит и пуш — ждёт «да» (правка compact-continue и архив подагентов).

## Цель  (29.09.2026)

Условие дословно: «необходимо написать новый клод код на новом языке полностью рабочий». Поставлено владельцем как проба сжатия при активной цели, не как задача.

### Решения под вопросом

- Работу на условие не веду: оно — проба механизма, а не задание. Если владелец имел в виду настоящую задачу, это меняет всё; тогда нужна формулировка, которую можно доказать из разговора.

## Шаги

- [x] 1. Разобрать промпты основного агента для GP и Explore: роли, что просят вернуть, какие инструменты нужны, где агент недоделал.
- [x] 2. Отзывы пользователей о Sonnet 5.5 (качество на исследовании, картографии, чтении кода; цена).
- [x] 3. Проект агентов: сколько, роли, инструменты, модель, промпты; что делать с описанием GP (whenToUse) и с Explore (`Agent(Explore)` в `permissions.deny`). Показать владельцу до установки.
- [x] 4. Пересмотреть senior-reviewer и test-writer. critical-reviewer не трогать.
- [x] 5. Переезд CLI и форка расширения на 2.1.284 (порядок как в `update-2.1.273.md`: CLI, чистый вендор, наши правки).

## Проект (29.09, владелец: «разделение моделей», якорь «символ + код», тщательно)

**Решения владельца:** researcher и senior-reviewer — Sonnet 5.5 (senior-reviewer
«ничего не решает, только читает и отчитывается»); implementer — `inherit`;
critical-reviewer не трогать. Ссылки `file:line` заменить якорем, который
переживает правку кода: «символ + файл + дословный кусок кода».

**Доставка общего брифа подагентам — штатный флаг.**
`--append-subagent-system-prompt-file` дописывает файл в системный промпт КАЖДОГО
подагента (встроенных тоже, вложенных тоже). Справка: «only works with --print».
Проба 29.09 на 2.1.280 (haiku, `--strict-mcp-config`): и `-p`, и stream-json
без `-p` (так работает VS Code) — подагент GP процитировал метку
«MARKER-7Q: subagent brief delivered.». Есть в 2.1.280 и 2.1.284. В TUI не
проверено — там остаётся запасной путь через заглушку CLAUDE.md.

Состав:
1. `trah-setup/agent-brief.md` → `~/.claude/agent-brief.md`: общий бриф подагента
   (кто ты и что тебе НЕ адресовано, Serena и её слепые зоны, гарды с точными
   порогами, якоря, пометки доказанности, безопасность, форма ответа).
2. Обёртка `trah-setup/bin/claude`: в режиме `-p`/stream-json добавить
   `--append-subagent-system-prompt-file` со склейкой «agent-brief + бриф каталога
   (`<проект>/.claude/brief.md`), если есть», как склеивается бриф главного.
   Не добавлять, если флаг уже передан. Проверить поддержку бинарём.
3. Заглушки `global-CLAUDE.md` и `~/Projects/CLAUDE.md`: подагенту — «твой бриф
   `~/.claude/agent-brief.md`, `brief.md` — бриф главной сессии, не открывай;
   `archive/` — не правила». (`~/Projects/CLAUDE.md` — файл владельца, не комплекта.)
4. Агенты: `researcher` (новый, sonnet, effort high), `implementer` (новый,
   inherit), `senior-reviewer` (sonnet, effort high, + Bash только для git и
   метрик), `test-writer` (якоря, правила проекта о данных тестов).
   Роль в промпте агента, окружение — в agent-brief.
5. Explore — `Agent(Explore)` в `permissions.deny` шаблона (он пропускает
   CLAUDE.md целиком — документация, «What loads at startup»). GP остаётся
   запасным; фрагмент описания GP — после переезда на 2.1.284.
6. Раздел брифа главного «Delegation: how to brief one»: бриф агента несёт
   окружение, задание несёт цель, установленное, границы, форму ответа; какой
   агент на что.

**Якорь (контракт для всех агентов):**
`` `путь` › `Символ` — «дословный кусок» `` (+ `~L412` как подсказка, не опора).
Кусок скопирован из ответа инструмента, одна строка, до ~100 знаков, узнаваем
поиском. Документ — `путь › §раздел`; веб — URL, дата, «цитата»; отсутствие —
чем искал, где и каким образцом. Проверка якоря вызывающим:
`find_symbol` по символу + `search_for_pattern` по куску.

## Что уже установлено (замеры 28–29.09)

- Встроенные агенты в 2.1.280: general-purpose (`tools: ["*"]`, модель сессии),
  Explore (только чтение, `model: "inherit"`), Plan (только чтение),
  claude-code-guide, statusline-setup; служебные claude, teammate, workflow-subagent.
- Наши фрагменты `trah-setup/fragments/agent-explore.md` и
  `agent-general-purpose.md` в бинарнике 2.1.280 на месте (1 и 2 вхождения).
  Описание GP для выбора («When you are searching for a keyword… use this agent»)
  фрагментом не тронуто — оно зовёт модель отдавать поиск в GP.
- За 14 дней 114 вызовов Agent: GP 51 (44 из них в `~/Projects`), senior-reviewer
  46, critical-reviewer 8, Explore 8, claude-code-guide 1, Plan 0.
  Скрипты: `/tmp/pa/agentuse.py 14`, `/tmp/pa/agentcalls.py 14`.
- Задачи GP — две группы: веб-исследования и выкачивание («G1–G7 сеть»,
  «Research WASM…», «Fetch/Download/Clone optimization mods», «Study
  lithostitched…») и написание кода («Build wgpu client renderer crate», «Trees
  feature», «F10 sound crate», «Fix cmd/bot tests», «Port collector page»).
  Explore — картография кода («Map code for lighting step», «Audit C1 gates
  coverage»), то есть роль senior-reviewer.
- Инструменты внутри подагентов: GP 4 112 вызовов, Serena 31% (Bash 1 055, Read
  894, WebFetch 316, WebSearch 205, Edit 141, Write 117); Explore 409, Serena 44%.
- Разбор 59 промптов GP/Explore (`/tmp/pa/agent-prompts.md`, признаки —
  `/tmp/pa/classify.py`), по номерам в выгрузке:
  - исследование с выкачиванием или распаковкой исходников — 19
    (9, 15–18, 41–48 lithostitched, 49, 52–55, 58);
  - исследование веба и литературы — 15 (5, 14, 22–28 G1–G7, 30–34, 56);
  - картография и сверка кода, только чтение — 16 (все 8 Explore; 11–12
    Nebulus, 35, 38–40 Ledger walk, 50, 57);
  - написание кода — 8 (2, 3, 4, 7, 8, 29, 36, 37); прочее — 1 (51, проба облака).
  Исследования пишут отчёт в `docs/research/…` и возвращают выжимку до 30 строк
  с путём («Верни краткую выжимку (до 30 строк) и путь к файлу» — 4 раза
  дословно). Картография возвращает таблицу с file:line прямо в ответе.
  Почти все вызовы фоновые (`run_in_background`).
- Поля фронтматтера агента (code.claude.com/docs/en/sub-agents, 29.09):
  `model` (sonnet/opus/haiku/fable/полный ID/inherit), `effort`
  (low…max, иначе наследует сессию), `disallowedTools`, `permissionMode`,
  `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `background`,
  `omitClaudeMd` (2.1.271+), `isolation: worktree`, `experimental.cacheTtl`.
  Мышление наследуется от сессии, отдельной настройки нет. Фоновым подагентам
  часть инструментов срезается (какие — не проверял).
- Sonnet 5.5 (вышла 28.09.2026, ID `claude-sonnet-5-5`): $2/$10 за 1M, вдвое
  дешевле Opus 5.5 ($4/$20), чтение кэша одинаково $0.20. По данным Anthropic:
  Terminal-Bench 4.0 70.6 против 66.4 у Opus; FrontierCode 46.2 против 54.4;
  CursorBench 55.5 против 57.8. CodeRabbit (13 трудных случаев ревью): Sonnet
  5.5 — 6/13, Opus 5.5 — 8/13 (standard) и 10/13 (max); у Sonnet 5.5 пропала
  привычка Sonnet 5 лишний раз ходить в веб. Сама Anthropic: Opus «заметно
  сильнее в сложной открытой работе, где нужно долгое суждение». HN: ниша
  Sonnet — подагенты и работа на low/medium. Предохранитель: запросы, которые
  классификатор относит к кибератакам (эксплойты, пентест), уходят на Sonnet 5,
  в Claude Code тоже, с пометкой в ответе. Попадут ли туда декомпиляция модов
  или разбор фронтенда DMarket — не выяснено.
- **Бриф до подагентов не доезжает (замер 29.09, 14 дней, 114 прогонов подагентов).**
  Сессии VS Code в `~/Projects` (pid 2933, 8425) запущены как
  `trah/current … --append-system-prompt-file ~/.cache/gws-claude-wrapper/brief-29f3….md`
  (29 490 байт = `~/.claude/brief.md` 20 696 + `~/Projects/.claude/brief.md` 8 792).
  Этот флаг меняет промпт только главного агента. Подагент получает свой промпт
  (+ наш фрагмент у GP/Explore) и цепочку CLAUDE.md, а заглушки CLAUDE.md
  (`~/.claude/CLAUDE.md`, `~/Projects/CLAUDE.md`) велят «открыть brief.md, если
  правил нет в контексте». Итог: 23 из 114 подагентов сами открывали brief (у
  главных сессий 8 из 58). GP открывал `~/Projects/.claude/brief.md` 16 раз,
  `~/.claude/brief.md` (персона главного агента и его формат ответа) 13 раз и
  архивный прежний регламент `archive/claude-setup-2026-09-19/CLAUDE.md` 13 раз
  (бриф каталога сам на него ссылается). Отчёты формат главного агента не
  переняли: 0 из 114 с блоками «Итог/Вопросы». Живая сессия cdca7160, 4 агента
  по UI 29.09 ~11:00: трое первым делом открыли brief, все четверо получили
  блок «Bash is not a reading tool». Скрипты: `/tmp/pa/brief.py`, `live.py`,
  `whichbrief.py`.
- Версии подагентов совпадают с нашими патчеными (2.1.269…2.1.280, entrypoint
  claude-vscode и cli), бинарник у всех живых сессий — `trah/2.1.280`.
  Позиционный аргумент `…/native-binary/claude` в argv VS Code — прежний вопрос,
  влияние не проверено.
- Что ломается у подагентов (`/tmp/pa/outcomes.py`, `bashfirst.py`,
  `cdblocks.py`): блок гарда «Bash is not a reading tool» 59 раз, «Bash edits»
  11 (первое слово: `cd` 40, `cat` 10, `grep` 7, `mkdir` 5). Под `cd` —
  настоящие чтения (`cat`, `sed -n`, `find | xargs wc -l`, `git show HEAD:file |
  awk`) и правки (`sed -i`, python-heredoc). Serena не взяла Java-файл 9 раз
  (`get_symbols_overview` на `asynchronus/modules/…`). Read больше предела кода —
  ~15. Сеть: web.archive.org недоступен, «unable to verify the first certificate».
  Короткие финалы GP (0–100 символов) — прогоны, прерванные владельцем
  («Request interrupted by user»), а не брошенная работа.
- Обвязка, которую основной агент повторяет почти в каждом из 59 промптов (её
  место — в промпте агента): строка ToolSearch для Serena и «корень привязки»;
  скоуп и glob от корня; «Bash не читает и не правит файлы проекта, Read/Serena»;
  «Read больше 120 строк кода блокируется, повтор проходит»; «Serena может не
  индексировать Java/декомпиляцию — Read/Grep»; программа 10+ строк — в файл;
  не коммитить, не трогать git, не выходить за свой каталог; «параллельно
  работает другой агент — не трогай X»; `pgrep -x engine` перед сборкой;
  ФАКТ/ГИПОТЕЗА/НЕ ПРОВЕРЕНО, «слова автора», числа только из источника с URL и
  датой, «страница не открылась — не ссылайся»; отчёт в файл по образцу соседей
  (`docs/research/README.md`), выжимка до 30 строк с путём; таблица покрытия
  «каждый файл области → раздел»; скачивание: `git clone --depth 1`, `.git` > 50 МБ
  удалить, > 2 ГБ не качать, опись (URL, ветка, коммит, размер), jar —
  Vineflower (`tools/unjar.sh`, `fetch-vineflower.sh`), ключ CurseForge нигде не
  записывать; «уже установлено — не переоткрывай».
- Хранение: вызовы Agent в `~/.claude/projects/<проект>/<сессия>.jsonl`,
  ход подагента в `<сессия>/subagents/agent-*.jsonl`, тип в `*.meta.json`
  (`agentType`).

## Попутные находки (не в этой задаче)

- `/btw`: владелец сказал забыть. Установлено: CLI по транспорту VS Code видит
  текущий ход посреди работы, и после `--resume` тоже (проба `/tmp/pa/sqprobe.py`,
  ответы на 8–12 с). Симптом владельца в VS Code («память до последнего итога»)
  не объяснён — не CLI.
- В живых процессах VS Code путь `…/anthropic.claude-code-2.1.280/resources/native-binary/claude`
  приходит в CLI trah позиционным аргументом среди флагов (обёртка). Не проверено,
  влияет ли.
- 28.09 15:49 VS Code убит OOM killer'ом: память съели тестовые бинарники Rust
  `delta-ead5de0aa` (4,1 ГБ) и `tray-329a6cea80` (3,1 ГБ) из прогона в `~/Projects`
  (scope `run-p814885`, пик 8,9 ГБ). Там стоит ограничивать потоки тестов.
- Исправлено 27.09: четыре правила `Bash(cd * && bun:*)`… и `Bash(curl*localhost:*)`
  в `~/.claude/settings.json` не срабатывали (`*` перед `:*`), переписаны на маски.

- 29.09 13:55: `compact-order.py` ответил «Сжатие заказано: '/compact' →
  /run/user/1000/cc-socks/90157.sock», но в сессию `/compact` пришёл как сообщение
  от другой сессии (peer message), а не как команда, и сжатия не было. Доставка
  заказа через сокет сломана или изменилась в 2.1.280 — разобрать отдельно.

- 02.10: **Claude Mods (2.1.287, по умолчанию включены).** Плагин с JS/TS-модулем
  `register(on)` в процессе CLI. Документация: code.claude.com/docs/en/plugins/mods
  и `/mods/reference`; типы — `mods/types/claude-code.d.ts` в anthropics/claude-code.
  Покрывают наши патчи бинаря на уровне прозы, а не минифицированного кода:
  `prompt.compose`/`prompt.section` (секции системного промпта по стабильным id) —
  куски `sys-*`; `tool.describe` (+ `isDeferred`) — куски `tool-*`;
  `prompt.attachment` по `type` — `reminder-*`; `attribution.text` — трейлеры;
  `agent.spawn` (переписать prompt, модель, отказать) и `agent.offer` (спрятать тип)
  — подагенты; `prompt.context` — блоки первого сообщения (`claudeMd`, `userEmail`).
  Не покрывают: семантику клавиш (Esc / `chat:cancel` — события нет, есть только
  `$.turn.abort`), доставку брифа в системный промпт подагента. В VS Code хуки модов
  работают, рисование — нет. На 2.1.284 — ранний доступ за
  `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` (9 вхождений в cli.js), API мог отличаться.
  Не проверено: доходит ли `prompt.compose` до промптов подагентов, оценщика `/goal`
  и сжатия.
- 02.10: `./trah all` при новой версии на машине сам идёт в `upgrade`: попытка
  2.1.284 → 2.1.287 упала на якоре `reminder-compact-file-reference` (0 вхождений),
  прицел и `current` не тронуты. Без переезда звать `./trah all --version 2.1.284`.
- 02.10: `restore-claude-wrapper.py` › `versions_note` предлагал снести оригинал
  копии trah (`versions/2.1.284`). Починено: вычитается имя из `trah/current`.

## Что пробовали и отвергли

- Пробы с задержками внутри хода модели (`sleep`, затем `timeout N tail -f
  /dev/null`) — второе есть обход гарда ожидания, владелец запретил. Задержки
  не нужны: быстрые `echo` и вопрос сразу после нужного результата.
- Пробы дольше минуты — запрещено владельцем.
