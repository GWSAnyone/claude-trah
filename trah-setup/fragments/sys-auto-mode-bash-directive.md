---
{
  "id": "sys-auto-mode-bash-directive",
  "route": "binary",
  "why": "прямой приказ читать через cat и править через sed, приезжает при включении auto/bypass и спорит со всей остальной дисциплиной. Штатного выключателя нет; чинится только здесь",
  "note": "текст собирается с переменными (${Oi} это Bash, ${Hs}/${Cl}/${Eu} — Read/Edit/Write), поэтому дословный поиск целой фразы промахивался. Якоря взяты по кускам между подстановками. В самом бинарнике фраза встречается дважды, но вторая копия лежит в области байткода bun и скрипту не видна — отсюда count 1",
  "note_хвост": "ТРЕТЬЯ ПРАВКА обязательна, и вот почему. Оригинал кончается словами `${kn} genuinely cannot do the job.` — то есть «переходи к отдельному инструменту, только когда Bash не справляется». Замена одного начала оставляла предложение «берись за оболочку, только когда Bash не справляется»: круг, в котором Bash сам себе условие. Хвост поэтому переписан отдельной правкой. В якорь третьей правки НЕ берётся `${kn}`: минифицированное имя меняется от версии к версии, и якорь с ним ломался бы каждой пересборкой. Взят кусок после подстановки, он в видимой части один (проверено байтовым счётом по 2.1.247: `Fall back to a dedicated tool only when ` — 2, из них одна в байткоде; ` genuinely cannot do the job.` — столько же)",
  "note_проверка": "ловушкой (`sink.py`) этот кусок НЕ ловится: сообщение режима подаётся живой сессии, а печатный прогон `--print` его не получает вовсе — проба 28.08.2026 показала ноль вхождений во ВСЕХ полях запроса, включая описания инструментов. Поэтому блока verify здесь нет, а проверять надо глазами в живой сессии: строка «Do your work through the Bash tool for what it is for» приезжает системным напоминанием при включённом разрешающем режиме",
  "edits": [
    {
      "op": "replace",
      "anchor": " tool wherever it can accomplish the job: read files with cat, head, or sed -n, search with grep and find, and make file changes with sed, heredocs, or short scripts, rather than using the dedicated ",
      "count": 1,
      "with": " tool for what it is for: running programs, builds, tests, git, and checking the environment. Fewer permission prompts is not a reason to read and edit through it — reading a file whole puts its entire text into the context and re-sends it on every later turn, and an in-place edit is blind, so a pattern that fired in the wrong place is exactly as silent as one that fired correctly. Keep using the dedicated "
    },
    {
      "op": "replace",
      "anchor": "Fall back to a dedicated tool only when ",
      "count": 1,
      "with": "Where a symbolic code tool is available, it beats both of those. Reach for text handling through "
    },
    {
      "op": "replace",
      "anchor": " genuinely cannot do the job.",
      "count": 1,
      "with": " only when nothing else can do the job."
    }
  ],
  "было": "auto-mode-is-not-bash-mode"
}
---
