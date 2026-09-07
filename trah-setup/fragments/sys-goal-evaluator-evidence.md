---
{
  "id": "sys-goal-evaluator-evidence",
  "route": "either",
  "why": "оценщик цели судит СТРОГО по стенограмме: инструментов у него нет, файлы он не открывает. После сжатия стенограмма — это выжимка, а ему велено «quote evidence from the transcript». Выжимка формально пересказ, и есть прямой риск, что он её за доказательство не засчитает: тогда цель, доказанная до сжатия, становится недоказуемой навсегда и блокирует остановку до ручной отмены",
  "note": "Это не украшение, а несущая часть: без неё связка «выжимка несёт доказательства» может не сработать вовсе. Второе, что кусок делает, — называет, ЧТО считать доказательством. По умолчанию оценщик берёт любую цитату, включая заявление ассистента «сделано» без единого числа за ним",
  "note_якорь": "Системный промпт оценщика — шаблонный литерал в развилке `F ? <для Stop> : <для прочих хуков>`. Якорь — последняя фраза ветки для Stop. Ветку для остальных хуков не трогаем: там ни стенограммы, ни сжатия",
  "note_проверка": "Через `verify` не проверяется: текст едет в системный промпт ВСПОМОГАТЕЛЬНОГО вызова, а не сессии. Проверять руками: поставить цель, дать оценщику отбить её и посмотреть в стенограмме причину отказа — она приходит строкой вида `[условие]: причина`",
  "edits": [
    {
      "op": "insert_after",
      "anchor": "When in doubt, return {\"ok\": false} without \"impossible\".",
      "count": 1
    }
  ]
}
---
What counts as evidence: a command together with its output in numbers, a file path with a line number, a measurement, an edit that was applied and confirmed. An assertion that something was done, with nothing behind it, is not evidence - say so in the reason.

A compaction summary in the transcript is first-hand evidence, not hearsay. It is written by the same session under explicit instruction to carry the exact commands, numbers and file references forward. Weigh its contents as you would weigh the original messages, and do not discount it for being a summary.

Do not ask the assistant to repeat evidence it already gave earlier in the transcript, and do not treat the same evidence appearing in condensed form as weaker.
