#!/usr/bin/env python3
"""Переставить хук напоминания с апстрима на прокладку — одним ходом.

Зачем. В `~/.claude/settings.json` на событии PreToolUse стоит апстримовый хук
Serena: `serena-hooks remind --client=claude-code`. Он считает грепом всё, в чьём
имени есть `search_for_pattern`, — включая собственный инструмент Serena
`mcp__serena__search_for_pattern`. Тот же вызов он НЕ засчитывает символьным
(в списке несимвольных подстрок стоит «pattern»), поэтому счётчик не
сбрасывается. Три поиска по образцу подряд, без единого грепа, — и третий
получает отказ «Too many consecutive grep calls without using symbolic tools».
Отключить это у апстрима нечем: ни флага, ни настройки порогов.

Прокладка `hooks/serena-remind-shim.py` не пускает к апстриму ровно те вызовы
Serena, которые он посчитал бы грепом или чтением. Всё остальное уходит ему
нетронутым, так что очередь из `Grep` и `Read` по-прежнему ловится.

Что делает этот скрипт:

1. кладёт `serena-remind-shim.py` в `~/.claude/hooks/`;
2. заменяет в `~/.claude/settings.json` ОДНУ строку — команду этого хука;
3. перед правкой снимает СВОЮ копию настроек с отметкой времени и печатает
   команду отката. Git здесь не участвует ни в какой роли.

Правится ровно одна строка, текстом, а не переразбором JSON: остальной файл
остаётся байт в байт прежним. Результат перед записью проверяется на разбор —
битый `settings.json` оставил бы машину без всех хуков сразу.

Запуск:

    python3 trah-setup/bin/swap-remind-hook.py --dry-run   # только показать
    python3 trah-setup/bin/swap-remind-hook.py             # переставить

Повторный запуск безвреден: если хук уже переставлен, скрипт это скажет и
ничего не тронет.
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

КОМПЛЕКТ = Path(__file__).resolve().parent.parent / "trah-setup"
ОТМЕТКА = time.strftime("%Y%m%d-%H%M%S")
ПРОКЛАДКА = "serena-remind-shim.py"

# Строка вида `"command": "serena-hooks remind --client=claude-code",` —
# с любым отступом и с запятой или без неё. Меняем только значение.
_СТРОКА = re.compile(
    r'^(?P<отступ>\s*"command"\s*:\s*)"serena-hooks\s+remind[^"]*"(?P<хвост>\s*,?\s*)$',
    re.MULTILINE,
)


def найти_уже(текст: str) -> bool:
    """Стоит ли прокладка в настройках уже сейчас."""
    return ПРОКЛАДКА in текст


def main() -> int:
    р = argparse.ArgumentParser(
        description="переставить хук напоминания Serena на прокладку")
    р.add_argument("--dry-run", action="store_true", help="только показать, ничего не писать")
    р.add_argument("--home", default=None,
                   help="другой домашний каталог (для проверок)")
    дано = р.parse_args()

    дом = Path(дано.home).expanduser() if дано.home else Path.home()
    всухую = дано.dry_run
    шаг = lambda т: print(("[всухую] " if всухую else "") + т)

    источник = КОМПЛЕКТ / "hooks" / ПРОКЛАДКА
    настройки = дом / ".claude/settings.json"
    цель_хука = дом / ".claude/hooks" / ПРОКЛАДКА

    if not источник.is_file():
        print(f"нет самой прокладки: {источник}", file=sys.stderr)
        return 1
    if not настройки.is_file():
        print(f"нет настроек: {настройки}", file=sys.stderr)
        return 1

    было = настройки.read_text(encoding="utf-8")

    if найти_уже(было):
        print(f"уже переставлено: {настройки} зовёт {ПРОКЛАДКА}. Ничего не тронуто.")
        return 0

    совпадений = len(_СТРОКА.findall(было))
    if совпадений == 0:
        print(f"в {настройки} нет строки с `serena-hooks remind` — переставлять нечего.",
              file=sys.stderr)
        return 1
    if совпадений > 1:
        print(f"в {настройки} таких строк {совпадений}, а ожидалась одна. "
              "Разберитесь руками — вслепую не правлю.", file=sys.stderr)
        return 1

    новая_команда = f"{sys.executable} {цель_хука}"
    стало = _СТРОКА.sub(
        lambda м: f'{м.group("отступ")}"{новая_команда}"{м.group("хвост")}', было)

    # Проверяем ДО записи: битый settings.json оставит машину без всех хуков.
    try:
        json.loads(стало)
    except ValueError as ошибка:
        print(f"после правки JSON не разбирается ({ошибка}). Ничего не записано.",
              file=sys.stderr)
        return 1

    копия = настройки.with_name(f"settings.json.bak-{ОТМЕТКА}")
    шаг(f"копия настроек → {копия}")
    шаг(f"прокладка       → {цель_хука}")
    шаг(f"команда хука    → {новая_команда}")

    if not всухую:
        shutil.copy2(настройки, копия)
        цель_хука.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(источник, цель_хука)
        # Запись через временный файл: обрыв на полпути не оставит огрызка
        # настроек, по которому Claude Code потеряет все хуки разом.
        временный = настройки.with_name(f"settings.json.new-{ОТМЕТКА}")
        временный.write_text(стало, encoding="utf-8")
        os.replace(временный, настройки)

    if shutil.which("serena-hooks") is None:
        print("\nвнимание: `serena-hooks` не найден в PATH. Прокладка в этом случае "
              "просто молчит — вреда нет, но и напоминаний не будет.")

    if всухую:
        print("\nЭто был показ. Ничего не записано. Повторить без --dry-run.")
        return 0

    print("\nГотово. Перезапустите сессию Claude Code, чтобы настройки перечитались.")
    print(f"\nОткат — одной командой:\n\n    cp {копия} {настройки}\n")
    print(f"Файл {цель_хука} после отката просто никем не зовётся; "
          "удалять его не обязательно.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
