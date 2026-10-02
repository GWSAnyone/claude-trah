#!/usr/bin/env bash
# drive.sh <стенд> <N> <условие[:бриф]>...
#
# Прогнать несколько условий подряд и сразу свести их одной таблицей.
# Условие без двоеточия — без брифа (база).
#
#   ./drive.sh bench3.py 5 base principles:briefs/principles.md
#
# Имена переменных латиницей: bash не принимает кириллицу в идентификаторах,
# и `bash -n` ловит это как синтаксическую ошибку в первой же строке с массивом.
set -u
cd "$(dirname "$(readlink -f "$0")")"
suite=$1; n=$2; shift 2
conds=("$@")

for spec in "${conds[@]}"; do
  name=${spec%%:*}
  brief=${spec#*:}
  if [ "$brief" = "$name" ]; then
    BENCH="$suite" ./batch.sh "$name" "$n" >"runs/$name.log" 2>&1
  else
    BENCH="$suite" ./batch.sh "$name" "$n" --brief "$brief" >"runs/$name.log" 2>&1
  fi
  echo "--- $name ---"
  tail -n 30 "runs/$name.log"
done

echo
echo "=== судья вкуса ==="
paths=()
for spec in "${conds[@]}"; do
  name=${spec%%:*}
  for d in runs/"$name"-*/; do
    [ -d "$d" ] || continue
    paths+=("${d%/}")
    python3 judge.py "${d%/}" >/dev/null 2>&1 &
  done
done
wait
python3 judge.py "${paths[@]}"
