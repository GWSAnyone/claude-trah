#!/usr/bin/env bash
# Кандидаты в дубли кода: dedup.sh <Target>... | --focus FILE... | --version
# Подробности — dedup.py рядом. Зависимости uv ставит в свой кэш при первом
# запуске (treepeat через uvx тянет ещё 19 МБ грамматик); дальше прогон — секунды.
exec uv run -q --with tree-sitter-language-pack --with scikit-learn "$(dirname "$(readlink -f "$0")")/dedup.py" "$@"
