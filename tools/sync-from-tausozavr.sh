#!/usr/bin/env bash
# Перенести живой комплект из рабочего репозитория сюда.
#
# Комплект живёт и правится в `tausozavr/trah-setup`. Здесь лежит его КОПИЯ для
# передачи наружу: сам по себе этот репозиторий не источник истины, и править
# файлы комплекта прямо здесь — значит развести две редакции. Правки вносятся
# там, сюда они переносятся этим скриптом.
#
# Обратного направления скрипт не имеет намеренно.
#
#   ./tools/sync-from-tausozavr.sh              # перенести
#   ./tools/sync-from-tausozavr.sh --dry-run    # показать, что изменилось бы
#
# Имена переменных здесь латиницей: bash не принимает не-ASCII в именах.
set -euo pipefail

SOURCE="${TRAH_SOURCE:-$HOME/Ledevia/tausozavr/trah-setup}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

if [[ ! -d "$SOURCE" ]]; then
  echo "нет источника: $SOURCE" >&2
  echo "укажи его через TRAH_SOURCE=/путь/к/trah-setup" >&2
  exit 1
fi

DRY=()
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY=(--dry-run)
  echo "СУХОЙ ПРОГОН — ничего не записывается"
fi

rsync -a --delete "${DRY[@]}" --itemize-changes \
  --exclude '__pycache__' --exclude '*.pyc' \
  "$SOURCE/" "$HERE/trah-setup/"

# Два гарда службы живут в соседнем каталоге, но их имена стоят в списке
# модулей диспетчера `pretooluse.py`. Без них набор проверок диспетчера падает
# на стороже «каждый модуль из списка лежит на диске».
NEIGHBOUR="$(dirname "$SOURCE")/workspace-setup/hooks"
if [[ -d "$NEIGHBOUR" ]]; then
  rsync -a --delete "${DRY[@]}" --itemize-changes \
    --exclude '__pycache__' --exclude '*.pyc' \
    "$NEIGHBOUR/" "$HERE/workspace-setup/hooks/"
fi

echo
echo "перенесено из $SOURCE"
echo "дальше: git -C \"$HERE\" diff --stat"
