---
{
  "id": "sys-memory-needs-a-yes",
  "route": "binary",
  "why": "штатный блок Memory велит писать памяти самостоятельно, по собственному ощущению значимости. У владельца правило обратное и записано в навыке checkpoint: «предложи занести в память; не заноси без да». Две памяти в одной обвязке уже есть (файловая и серенина), и правило про согласие сказано только про вторую — про первую не сказано нигде",
  "note_сон": "Оговорка про фоновый проход была здесь несколько часов 29.08.2026 и УБРАНА в тот же день. Повод для неё: `autoDreamEnabled: true` в настройках и промпт `agent-prompt-dream-memory-consolidation`, который велит агенту сводить память сам и отсылает за правилами ровно в этот раздел — то есть проход обязан консолидировать, а согласия спросить не у кого. Владелец разрешил противоречие короче: сон выключен (`autoDreamEnabled: false`). Текст оговорки убран следом, потому что он уезжал в системный промпт КАЖДОЙ сессии ради работы, которой больше не бывает. Вернётся вместе со сном, если тот когда-нибудь понадобится",
  "note": "Цена ошибки несимметрична. Не записанное наблюдение теряется и переоткрывается, записанное неверно — живёт как факт: следующая сессия читает его в контексте и не перепроверяет, потому что оно выглядит как знание, а не как догадка. Поэтому согласие требуется на запись, а не на пропуск",
  "edits": [
    {
      "op": "insert_after",
      "anchor": "Before saving, check for an existing file that already covers it.",
      "count": 1
    }
  ],
  "verify": {
    "where": "system",
    "marker": "Saving is not automatic",
    "modes": [
      "default"
    ]
  }
}
---
Saving is not automatic either. When something looks worth keeping, say so in one line and write it only once the user agrees; a memory saved on your own initiative turns your reading of a single moment into a fact that every later session will trust without rechecking it.
