function claude --description 'claude: skip permission prompts; дисциплина Serena — через output style «Serena first»'
    # Системный промпт НЕ подменяем.
    #
    # Раньше здесь стоял --system-prompt "$(serena prompts print-cc-system-prompt-override)".
    # Замер показал, что это невыгодный обмен: штатный промпт — 3019 слов,
    # форк Serena — 1354, то есть терялось ~1665 слов штатных инструкций
    # (память, окружение с моделью и датой, управление контекстом, сдержанность
    # в делегировании субагентам). А устраняло это ОДНУ строку уклона: сами
    # описания инструментов весят 16 862 слова, едут отдельным параметром API
    # и подмене системного промпта неподвластны.
    #
    # Дисциплина Serena теперь живёт в ~/.claude/output-styles/serena-first.md:
    # она добавляется в КОНЕЦ системного промпта, ничего не удаляет благодаря
    # keep-coding-instructions: true, и Claude Code сам напоминает о ней
    # в течение сессии.
    #
    # Откат: вернуть строку с --system-prompt из
    # ~/.claude/backups/cleanup-20260810-193848/claude.fish.orig
    command claude --allow-dangerously-skip-permissions $argv
end
