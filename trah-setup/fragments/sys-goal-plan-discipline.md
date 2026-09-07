---
{
  "id": "sys-goal-plan-discipline",
  "route": "binary",
  "why": "штатный `/goal` при постановке цели впрыскивает ровно один абзац: подтверди, начинай работать, не спрашивай что делать. Про план там нет ни слова, про запись решений тоже. То есть автономный прогон, которого владелец хочет от `/goal`, штатно не поддержан ничем: работа идёт в разговоре, разговор сжимается, и от неё не остаётся ни следа, ни списка решений, которые владелец собирался просмотреть",
  "note": "Кусок ничего не отменяет, он ДОПИСЫВАЕТ. Их абзац остаётся дословно, наш текст читается его продолжением. Смысл: цель обязана лечь на диск раньше, чем начнётся работа, потому что впрыснутое сообщение сжатия не переживёт, а файл плана переживёт. Разделение каналов: впрыск бутстрапит, план помнит, выжимка доказывает — ни один не дублирует другой",
  "note_якорь": "Живая строка — ШАБЛОННЫЙ литерал с подстановкой условия: ``oHt=(t)=>`A session-scoped Stop hook is now active with condition: \"${t}\". Briefly acknowledge…` ``. Ни `oHt`, ни `t` в якорь не берутся: минифицированные имена меняются каждой сборкой. Якорь — самый хвост литерала. Операция именно `insert_after`, а не `replace`: проверка на обратную кавычку и `${` смотрит ТОЛЬКО наш текст, а якорь возвращается на место как был, — при `replace` в проверяемый текст попала бы кавычка из `/goal clear` в их же фразе, и сборка отбилась бы",
  "note_почему_не_системный_промпт": "Просилось положить это в системный промпт куском вида «если активна цель — делай так». Отвергнуто: рента платится в каждой сессии, а цель ставится в одной из ста. Впрыск при постановке стоит ноль, пока цель не поставлена",
  "note_проверка": "Пробой через `verify` этот кусок не проверяется: текст едет не в системный промпт и не в описание инструмента, а отдельным сообщением в момент постановки цели. Проверять руками: поставить любую цель и посмотреть в стенограмме, приехало ли наше продолжение. Урок 2.1.257 в силе — сходящийся `check` доказывает лишь, что строка есть, а не что она живая",
  "edits": [
    {
      "op": "insert_after",
      "anchor": "that's only for clearing a goal early.",
      "count": 1
    }
  ]
}
---
Before you start, put the goal on disk. This message does not survive compaction; the plan file does.

1. Open the plan this task belongs to under docs/plans/, or start one if there is none. Write into it a block "Цель" holding the condition verbatim, today's date, and an empty section "Решения под вопросом".

2. A blocking question does not stop the work. Pick the option you can defend, write the choice and the reason into the plan, and keep going. Where you are genuinely unsure, the entry goes into "Решения под вопросом" with the alternative you rejected, why you rejected it, and what would change the answer. That section is what the owner reads at the end, so write it for him.

3. End every turn by naming what is now proven toward the condition, and what proved it: the command with its output in numbers, the file and line, the measurement. The evaluator that judges this goal reads only the conversation. It cannot open the plan, cannot run anything, and an unproven claim is no evidence at all to it.

4. A compaction order outranks the goal. The goal survives compaction: the condition lives in session state, and the PreCompact hook carries the condition and the accumulated evidence into the summary. So bring the step to a close, checkpoint, compact, and continue toward the goal afterwards. The goal is never a reason to postpone compaction.

5. If the condition as worded cannot be proven from the conversation, say so in your first reply and propose a sharper wording before starting. A condition nobody can prove is a loop only the owner can stop.
