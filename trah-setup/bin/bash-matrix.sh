#!/usr/bin/env bash
# От чего зависит, какой вариант описания Bash подаётся.
#
# Вопрос: пункт «IMPORTANT: Avoid using this tool to run cat/head/sed…» есть в
# описании моей рабочей сессии, но не появляется ни в печатном прогоне, ни в
# живой сессии владельца. Гипотеза — вариант выбирается по режиму разрешений и
# наличию песочницы: в рабочей сессии у Bash есть параметр
# dangerouslyDisableSandbox, а в пробах его нет.
#
# Пробы идут в ловушку (sink.py): ответа нет, токенов не стоят.
set -u
SP=$(cd "$(dirname "$0")" && pwd)
BIN=$HOME/.local/share/claude/trah/2.1.239
PORT=8774

for MODE in default acceptEdits bypassPermissions plan; do
    OUT=$SP/bash-mode-$MODE.jsonl
    : > "$OUT"
    nohup setsid python3 "$SP/sink.py" $PORT "$OUT" >/dev/null 2>&1 </dev/null &
    sleep 1
    cd /home/kaltsit/Ledevia/SyncedProjects
    ENABLE_TOOL_SEARCH=1 ANTHROPIC_BASE_URL=http://127.0.0.1:$PORT timeout 120 "$BIN" \
        --model claude-opus-5 --permission-mode "$MODE" --print "2+2" \
        >/dev/null 2>&1 </dev/null
    pkill -f "[s]ink.py $PORT" 2>/dev/null
    sleep 1
    echo "── режим $MODE ──"
    python3 "$SP/bash-variant.py" "$OUT" | tail -n +2
done
