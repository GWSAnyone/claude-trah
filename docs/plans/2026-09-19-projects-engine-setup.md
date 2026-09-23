# ~/Projects под `claude trah`: фокус на engine, engine-client, engine-content

Начато 19.09.2026. Задача владельца: «проработать папку для работы клод траха
`/home/kaltsit/Projects/`, фокус на `engine`, `engine-client`, `engine-content`, а не
на asynchronus-папках; изучить данные, оформить Serena и Claude для полноценного
эффекта запуска `claude trah`».

## Где я сейчас  (обновлено 2026-09-19 18:21)

**Фаза:** пункты 1–3 и 5 сделаны, работа закрыта.
- `~/Projects/.claude/brief.md` написан (атлас engine*, дизайн и журнал в asynchronus-native-rewrite,
  `~/.local/share/engine`, чего не трогать, команды). Живая проверка: `claude trah --model haiku -p`
  из `engine-content` — stderr «Серена на /home/kaltsit/Projects», модель процитировала строку брифа.
- `.serena/project.yml`: пункт 6 разрешает `engine-<slug>/`, пункт 7 помечен «только asynchronus».
  Вживую не проверено: подхватится при следующем старте Серены.
- `engine/.git/info/exclude`: `/.claude/compact-summaries/`, `/.claude/.checkpoint-*`.
  `git status` в engine-content и engine-client — 0 строк `.claude` (было 6 в engine-content).
**18:30, по слову владельца «привести к эталону»:** прежний регламент (42 948 байт) и копия
project.yml (оригинальная, до правки 18:21) — в `~/Projects/archive/claude-setup-2026-09-19/`, туда же
перенесён навык `.claude/skills/checkpoint` (журнал в docs/branches, затенял навык комплекта).
`CLAUDE.md` → указатель 1 891 байт; бриф 6 636 байт (дух §0, атлас, worktree, Serena, запреты);
`.claude/rules/asynchronus.md` (paths asynchronus*/**: unjar, docs/branches, закрытие);
`docs/10-worktrees.md` — реестр; `init-project.py --write` положил docs-layout.md и два README.
`initial_prompt` Серены переписан: правила из брифа, три пункта. Живая проверка haiku из engine-content —
бриф и указатель в контексте. Навык `/end` оставлен (только asynchronus).
**Следующее действие:** нет.
**Незакоммичено:** этот файл; правки в `~/Projects` вне git (exclude, project.yml, brief вне репозиториев).
**Открытые вопросы:** заводить ли память Серены по движку.

## Что установлено осмотром (не переоткрывать)

1. **Раскладка.** `engine/` — репозиторий `GWSAnyone/engine`, ветка `main`, эталон, агенты
   не пишут. `engine-client/` (`feat/client`) и `engine-content/` (`feat/content`) — его
   git worktree (`.git` — файл с `gitdir: …/engine/.git/worktrees/<имя>`). Rust-воркспейсы,
   `members = ["crates/*"]`, edition 2024, rust 1.98, тулчейн в `rust-toolchain.toml`.
   - `engine-content`: крейты `app, client-render, content, core-rng, diag, gen, lod, mod-api`,
     плюс `mods/{terralith,tectonic}`, `tools/packc`. Здесь идёт работа: 18 изменённых
     файлов, сводки сжатий 19.09.
   - `engine-client`: `diag, client-render`, 2 незакоммиченных изменения.
   - `engine`: только каркас `816fd1b` (крейт `diag`).
   - Все три `CLAUDE.md` одинаковы (4 188 байт) — один файл репозитория.
2. **План работы живёт не в engine**, а в
   `~/Projects/asynchronus-native-rewrite/docs/plans/2026-09-18-native-rewrite-research.md`
   (дизайн — `asynchronus-native-rewrite/docs/design/engine/`). Чекпоинт сессии в
   `engine-content/.claude/.checkpoint-gwsdesktop-48200f59` указывает туда полем `project`.
   Запуск движка: `~/.local/share/engine/run.sh` → `bin/engine`, аргументы
   `~/.local/share/engine/args`, лог `logs/latest.log`, кэш LOD `lod/`, паки `packs/`.
3. **Serena уже верно.** Обёртка `claude trah` ищет ближайший предок с
   `.serena/project.yml` (граница — дом): у `engine*` своей метки нет, значит корень —
   `~/Projects` (`projects-root`), ровно как требует регламент `~/Projects/CLAUDE.md` §2.
   В `~/Projects/.serena/project.yml` есть `rust` (последним), `**/target/**` игнорируется,
   rust-analyzer находит `Cargo.toml` в прямых подпапках корня. Гарды комплекта
   (`nudge-serena` и др.) узнают `~/Projects` по той же метке — дисциплина действует.
4. **`~/Projects/CLAUDE.md` — 42 948 байт регламента под asynchronus** (Java, jar,
   worktree `asynchronus-<slug>`, реестр веток). Claude Code грузит его в КАЖДУЮ сессию под
   `~/Projects`, включая engine. Про engine там одна строка реестра. Это владельческий
   документ — предложить, не переписывать.
5. **Проектного брифа нет.** Ни `engine*/.claude/brief.md`, ни `~/Projects/.claude/brief.md`
   — сессия `claude trah` получает только общий бриф машины.
6. **`initial_prompt` корня Serena — под asynchronus**: пункт 6 велит работать только в
   `asynchronus-<slug>/`, пункт 7 — про jar. Для engine-сессий вводит в заблуждение.
7. **`.claude/` в `engine-content` не игнорируется гитом**: чекпоинт и 5 сводок сжатий
   висят `??` рядом с кодом. `.gitignore` репозитория — только `/target`.
8. Память Serena корня (`~/Projects/.serena/memories/`) пуста.

## Что делать

1. `~/Projects/.claude/brief.md` — короткий бриф с фокусом на engine: атлас трёх worktree и
   где план/дизайн, как собирать/проверять/запускать (команды из `engine/CLAUDE.md` и
   записи выше), чего не трогать (`engine/` main, чужие worktree, `asynchronus/`). Не
   дублировать `engine/CLAUDE.md` — ссылаться. Один файл покрывает все три worktree: обёртка
   берёт ближайший `.claude/brief.md` вверх от cwd, `engine*` своего нет.
2. `~/Projects/.serena/project.yml`: `initial_prompt` пункт 6 — работать в своём worktree
   `asynchronus-<slug>/` ИЛИ `engine-<slug>/`; пункт 7 оставить как «для asynchronus». Смысл
   остального не трогать.
3. `engine/.git/info/exclude` (общий для всех worktree, без коммита): `/.claude/compact-summaries/`
   и `/.claude/.checkpoint-*`.
4. Решено не делать сейчас: переписывать `~/Projects/CLAUDE.md`; писать память Serena без
   «да» владельца; чистить реестр Serena.
5. Проверка: `cd ~/Projects/engine-content && claude trah -p …` дешёвой моделью — строка
   «claude trah: Серена на /home/kaltsit/Projects», бриф в промпте; `git status` в
   `engine-content` без `.claude/`.

## Что пробовали и отвергли

- Читать `~/Projects` оболочкой — гард `pretooluse.py` отбивает: `~/Projects` для него своё
  дерево по метке `.serena/project.yml`. Читать через `query_project projects-root` и `Read`.
