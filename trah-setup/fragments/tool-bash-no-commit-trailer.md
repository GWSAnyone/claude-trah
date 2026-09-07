---
{
  "id": "tool-bash-no-commit-trailer",
  "route": "binary",
  "why": "прямой конфликт с главным правилом владельца, стоящий в точке решения. Описание `Bash` в блоке `# Git` велит: «End git commit messages with: Co-Authored-By: Claude … / Claude-Session: …». Бриф это запрещает словами «NEVER add Co-Authored-By … Commits are authored by me only», но запрет живёт в другом месте промпта, а приказ — ровно там, где сочиняется сообщение коммита",
  "note": "Найдено 29.08.2026 сверкой с корпусом форка tweakcc — и обнаружилось, что КОРПУС НЕПОЛОН: `catalogue.py --grep` по `prompts-2.1.247.json` не нашёл ни `End git commit messages with`, ни `Co-Authored-By`, тогда как в самом бинарнике обе строки есть (по 2 вхождения, из них одна копия в области байткода). Опись форка — хорошая карта, но источник истины остаётся бинарь",
  "note_якорь": "Исходник: `a=[o?`- End git commit messages with:\\n${o}`:null, s?`- End PR bodies with:\\n${s}`:null]`. Напрашивалось хирургическое `o` → `null`, чтобы строка не появлялась вовсе, — не сделано по двум причинам. Первая: в замену пришлось бы вписать обратную кавычку, а её сборка отвергает (шаблонная строка закроется, копия не запустится). Вторая и главная: минифицированное имя `o` меняется от версии к версии, и такой якорь ломался бы каждой пересборкой. Взят текстовый якорь — он переживает переименования",
  "note_pr": "Хвост PR (`End PR bodies with:` → `Generated with Claude Code`) НЕ трогаем: правило владельца сказано про авторство коммитов, про тело PR он не говорил ничего. Спросить дешевле, чем угадать",
  "note_два_пути": "Счёт поднят с 1 до 2 при переезде на 2.1.251: описание Bash разъехалось на ДВА пути — `bash_full` (функция `hcr`) и `bash_lean` (`ycr`), и приказ про подпись лежит в каждом. Пропатчить один значит оставить второй живым, а какой из них уедет — решает сборка описания, не мы. Обе копии одинаковой формы (`- End git commit messages with:\\n${переменная}`), поэтому одной замены с count 2 достаточно",
  "note_три_пути": "Счёт поднят с 2 до 3 при переезде на 2.1.257: к `bash_full` и `bash_lean` добавился третий путь — сборщик подписи `yHn`, который выдаёт блок «Attribution for git commits and pull requests you create from here on (this replaces any earlier…)». Форма та же (`- End git commit messages with:\\n${переменная}`), поэтому одной замены с count 3 достаточно. ВНИМАНИЕ на будущее: в этом третьем пути хвост PR назван ИНАЧЕ — `- End pull request descriptions with:` вместо `- End PR bodies with:`, и наш кусок `tool-bash-no-pr-trailer` его не видит. На переезд это не влияет (его якорь сошёлся), но приказ про подпись PR в новом пути остаётся непатченым",
  "edits": [
    {
      "op": "replace",
      "anchor": "- End git commit messages with:",
      "count": 3,
      "with": "- Never end a git commit message with a trailer. Commits here are authored by the user alone: no Co-Authored-By line, no session link, no generated-by note belongs in one. The harness default that follows is shown only so that you recognise it and leave it out:"
    }
  ],
  "verify": {
    "tool": "Bash",
    "marker": "Never end a git commit message with a trailer",
    "modes": [
      "default"
    ]
  }
}
---
