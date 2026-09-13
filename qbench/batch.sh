#!/usr/bin/env bash
# batch.sh <условие> <N> [--brief FILE]  — N прогонов одного условия
# BENCH=bench2.py — какой стенд; QBENCH_MODEL — модель (по умолчанию claude-opus-5)
#
# QBENCH_JOBS — сколько сессий разом, по умолчанию 2. Потолок здесь не
# вымышленный: пять разом съели память на машине с 31 ГБ (12.09.2026), и
# система убила весь прогон, не дав досчитать ни одной сессии. Каждая сессия
# держит свой процесс поверх 220-мегабайтного бандла.
set -u
cond=$1; n=$2; shift 2
BENCH=${BENCH:-bench.py}
JOBS=${QBENCH_JOBS:-2}
cd "$(dirname "$(readlink -f "$0")")"
for i in $(seq 1 "$n"); do
  d="runs/${cond}-${i}"
  [ -d "$d" ] && continue
  python3 "$BENCH" make "$d" "$@" >/dev/null
done
for i in $(seq 1 "$n"); do
  d="runs/${cond}-${i}"
  [ -f "$d/meta.json" ] && continue
  while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do wait -n; done
  python3 "$BENCH" run "$d" --tag "${cond}-${i}" &
done
wait
echo "=== $cond: готово ==="
python3 "$BENCH" table runs/${cond}-*
