---
{
  "id": "sys-auto-mode-bash-directive",
  "route": "mod",
  "mod": {"event": "prompt.attachment", "type": "auto_mode"},
  "note_мод": "02.10.2026, переезд на мод (2.1.287). Найдено вживую: сессия на 2.1.284 С ПАТЧЕМ получила в bypass штатный текст «You can do much of your work through the Bash tool when it is the simpler route…». В 2.1.28x у вложения `auto_mode` два варианта приказа: строгий `h` («wherever it can accomplish the job», его правил патч) и мягкий `S` («when it is the simpler route»), выбор — `e.bashFirstSteer===\"relaxed\"`, то есть решает сервер. Патч правил только строгий, сверка находила его якоря и считала кусок доставленным, а приезжал мягкий. Теперь обе редакции заменяются целиком в отрисованном виде (имена инструментов — Bash, Read, Edit, Write), в том же вложении, где их отдаёт CLI. Ловушкой не проверяется (вложение режима в `--print` не приходит): «событие не пришло» в сверке — ожидаемо",
  "why": "прямой приказ читать через cat и править через sed, приезжает при включении auto/bypass и спорит со всей остальной дисциплиной. Штатного выключателя нет; чинится только здесь",
  "note": "текст собирается с переменными (${Oi} это Bash, ${Hs}/${Cl}/${Eu} — Read/Edit/Write), поэтому дословный поиск целой фразы промахивался. Якоря взяты по кускам между подстановками. В самом бинарнике фраза встречается дважды, но вторая копия лежит в области байткода bun и скрипту не видна — отсюда count 1",
  "note_хвост": "ТРЕТЬЯ ПРАВКА обязательна, и вот почему. Оригинал кончается словами `${kn} genuinely cannot do the job.` — то есть «переходи к отдельному инструменту, только когда Bash не справляется». Замена одного начала оставляла предложение «берись за оболочку, только когда Bash не справляется»: круг, в котором Bash сам себе условие. Хвост поэтому переписан отдельной правкой. В якорь третьей правки НЕ берётся `${kn}`: минифицированное имя меняется от версии к версии, и якорь с ним ломался бы каждой пересборкой. Взят кусок после подстановки, он в видимой части один (проверено байтовым счётом по 2.1.247: `Fall back to a dedicated tool only when ` — 2, из них одна в байткоде; ` genuinely cannot do the job.` — столько же)",
  "note_проверка": "ловушкой (`sink.py`) этот кусок НЕ ловится: сообщение режима подаётся живой сессии, а печатный прогон `--print` его не получает вовсе — проба 28.08.2026 показала ноль вхождений во ВСЕХ полях запроса, включая описания инструментов. Поэтому блока verify здесь нет, а проверять надо глазами в живой сессии: строка «Do your work through the Bash tool for what it is for» приезжает системным напоминанием при включённом разрешающем режиме",
  "edits": [
    {
      "op": "replace",
      "anchor": "Do your work through the Bash tool wherever it can accomplish the job: read files with cat, head, or sed -n, search with grep and find, and make file changes with sed, heredocs, or short scripts, rather than using the dedicated Read, Edit, or Write tools. Fall back to a dedicated tool only when Bash genuinely cannot do the job.",
      "with": "Do your work through the Bash tool for what it is for: running programs, builds, tests, git, and checking the environment. Fewer permission prompts is not a reason to read and edit through it: reading a file whole puts its entire text into the context and re-sends it on every later turn, and an in-place edit is blind, so a pattern that fired in the wrong place is exactly as silent as one that fired correctly. Keep using the dedicated Read, Edit, or Write tools. Where a symbolic code tool is available, it beats both of those. Reach for text handling through Bash only when nothing else can do the job."
    },
    {
      "op": "replace",
      "anchor": "You can do much of your work through the Bash tool when it is the simpler route: read files with cat, head, or sed -n, search with grep and find, and make small, mechanical file changes with sed, heredocs, or short scripts instead of the dedicated Read, Edit, or Write tools. The choice is yours: prefer Edit or Write when a shell edit would be fragile, such as exact or multi-line replacements, or sed/awk flags that differ between GNU and BSD/macOS.",
      "with": "Do your work through the Bash tool for what it is for: running programs, builds, tests, git, and checking the environment. Fewer permission prompts is not a reason to read and edit through it: reading a file whole puts its entire text into the context and re-sends it on every later turn, and an in-place edit is blind, so a pattern that fired in the wrong place is exactly as silent as one that fired correctly. Keep using the dedicated Read, Edit, or Write tools. Where a symbolic code tool is available, it beats both of those. Reach for text handling through Bash only when nothing else can do the job."
    }
  ],
  "было": "auto-mode-is-not-bash-mode"
}
---
