---
{
  "id": "trah-language",
  "route": "brief",
  "scope": "trah",
  "kind": "bullet",
  "order": 20,
  "personal": true,
  "why": "язык ответа и язык размышления различаются намеренно: первый для человека, второй для экономии",
  "note_нельзя_в_бинарник": "07.09.2026 кусок перенесли в бинарник вставкой после `Technical terms and code identifiers should remain in their original form.` и в тот же день вернули. Сборка прошла, текст в копии лежит — а в живой сессии его НЕТ: блок `# Language` доезжает без вставки, от «original form.» сразу к «Maintain full orthographic». Значит правится не та строка, из которой этот блок собирается на самом деле. Искать вторую копию не стали: бриф доставляет то же самое даром и доказанно",
  "note_правило": "Вместе с `trah-identity` это второй кусок за день, который в бинарнике не сработал. Общее: обе цели лежат в НАЧАЛЕ системного промпта, где апстрим собирает текст по-своему. Правка бинарника надёжна там, где она правит ОПИСАНИЕ ИНСТРУМЕНТА или блок харнесса — это проверено пробой на четырнадцати кусках",
  "covered_by": []
}
---
- Russian for user-facing output (responses, comments, commit messages). English for all internal reasoning (thinking) to optimize token usage.
