---
{
  "id": "trah-serena-intro",
  "route": "brief",
  "scope": "trah",
  "kind": "section",
  "order": 100,
  "why": "заголовок раздела и главная мысль: символьный слой — основной способ работы с кодом, а не украшение",
  "note": "Приказ «активируй проект» убран 29.08.2026. Инструмента нет вовсе: `trah-setup/serena/context-claude-code.yml`, `single_project: true` — сервер поднимается обёрткой с `--project` и второго проекта не берёт. Живая проверка в тот день: `ToolSearch` на `mcp__serena__activate_project` вернул «No matching deferred tools found», а имя молча выпало из списка — сессия заплатила ходом. Тем же днём тот же приказ убран из хука `serena-session-start.py`; это был второй его источник. Предупреждение «не активируй домашний каталог» ушло следом: активировать нечем, а корень выбирает обёртка, и дом она отвергает сама",
  "covered_by": []
}
---
# Serena and sequential-thinking — the working rules

Serena is a symbolic layer over the code: it understands **symbols** — functions,
classes, methods, their bodies and their references — where the built-in tools
understand **lines and bytes**. That difference is the whole point, and it is why
the rules below are not a style preference but the working method.

Set the expectation at the right level: in a session working on this project,
nearly every tool call that concerns code is a Serena call. The built-in file
tools are the exception you can name a reason for, not the backbone.

The first action of a session, before reading any file and before any search:
pull Serena's tools in. They are deferred — until you request the schemas, Serena
does not exist for you, and your hand reaches for `grep` by itself.

There is nothing to activate afterwards. The launcher binds the server to one
project at startup, and this build takes no second one — `activate_project` is
not in the tool list at all. Paths are given relative to that root; if they do
not resolve, the session was started from the wrong directory, and the cure is
to start one there, not to switch trees from inside.
