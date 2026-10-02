#!/usr/bin/env bash
# drive-binary.sh <стенд> <N> <условие=бинарь>...
#
#   ./drive-binary.sh bench2.py 5 nofrag=/tmp/qb-without frag=/tmp/qb-with
#
# Условия различаются НЕ брифом, а БИНАРНИКОМ. Правка системного промпта живёт
# в бинаре, и подсунуть её брифом значит померить текст в другом месте промпта,
# а не то, что поедет в дело. Обёртка берёт цель из CLAUDE_WRAPPER_TARGET
# первым приоритетом, и `bench.run` эту переменную не вычищает — она не из
# семейства CLAUDE_CODE_*.
#
# Судья гоняется ШТАТНЫМ бинарём для всех условий: судить правленым значит
# судить разными глазами в разных условиях.
#
# Имена переменных латиницей: bash не принимает кириллицу в идентификаторах.
set -u
cd "$(dirname "$(readlink -f "$0")")"
suite=$1; n=$2; shift 2
conds=("$@")
jobs=${QBENCH_JOBS:-2}

for spec in "${conds[@]}"; do
  name=${spec%%=*}
  bin=${spec#*=}
  [ -x "$bin" ] || { echo "нет бинаря: $bin"; exit 1; }
  CLAUDE_WRAPPER_TARGET="$bin" BENCH="$suite" ./batch.sh "$name" "$n" \
    >"runs/$name.log" 2>&1
  echo "--- $name ---"
  tail -n 20 "runs/$name.log"
done

echo
echo "=== судья вкуса ==="
paths=()
for spec in "${conds[@]}"; do
  name=${spec%%=*}
  for d in runs/"$name"-*/; do
    [ -d "$d" ] || continue
    paths+=("${d%/}")
  done
done
# Судья — такая же сессия поверх 220-мегабайтного бандла, как и прогон, и
# параллелить его без предела значит повторить нехватку памяти, убившую пять
# одновременных сессий 12.09.2026. Потолок тот же, что у стенда.
for d in "${paths[@]}"; do
  while [ "$(jobs -rp | wc -l)" -ge "$jobs" ]; do wait -n; done
  python3 judge.py "$d" >/dev/null 2>&1 &
done
wait
python3 judge.py "${paths[@]}"
