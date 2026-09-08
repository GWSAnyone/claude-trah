#!/usr/bin/env python3
"""Проверки проектного скелета. Токенов не стоит.

Главное здесь одно: существующий файл не трогается никогда. Проектный уровень —
место, где у человека чаще всего уже что-то лежит, и затереть его `CLAUDE.md`
значит сделать ровно то, чего комплект обещает не делать.

Второе: шаблон обязан покрывать те каталоги, на которые молча рассчитывают
части комплекта. Пять из них ссылаются на `docs/plans/` и `docs/reports/`,
и до 08.09.2026 комплект не вёз про них ни строчки.
"""
import importlib.util
import sys
import tempfile
from pathlib import Path

КАТАЛОГ = Path(__file__).resolve().parent
спец = importlib.util.spec_from_file_location("init_project", КАТАЛОГ / "init-project.py")
ip = importlib.util.module_from_spec(спец)
спец.loader.exec_module(ip)

всего = 0
провалов = 0


def check(имя: str, условие: bool, подробность: str = "") -> None:
    global всего, провалов
    всего += 1
    if not условие:
        провалов += 1
        print(f"  ✗ {имя} {подробность}")


print("init-project.py")

# --- шаблон покрывает то, ради чего он есть ---------------------------------
пути = {str(п.relative_to(ip.ШАБЛОН)) for п in ip.файлы_шаблона()}
for обязательный in ("CLAUDE.md", ".claude/brief.md",
                     ".claude/rules/docs-layout.md",
                     "docs/plans/README.md", "docs/reports/README.md"):
    check(f"в шаблоне есть {обязательный}", обязательный in пути, f"={sorted(пути)}")

правило = (ip.ШАБЛОН / ".claude/rules/docs-layout.md").read_text(encoding="utf-8")
check("правило раскладки объясняет «Где я сейчас»", "Где я сейчас" in правило)
check("правило раскладки требует раздел про отвергнутое",
      "отвергли" in правило, "")
check("правило называет формат имени плана", "ГГГГ-ММ-ДД" in правило)

бриф = (ip.ШАБЛОН / ".claude/brief.md").read_text(encoding="utf-8")
check("скелет брифа не выдумывает содержание за хозяина",
      "<!--" in бриф and "Атлас" in бриф)

# --- показ ничего не пишет ---------------------------------------------------
д = Path(tempfile.mkdtemp())
итог = ip.разложить(д, писать=False)
check("показ обещает положить весь шаблон", len(итог["положено"]) == len(пути),
      f"{len(итог['положено'])} против {len(пути)}")
check("показ действительно ничего не создал", list(д.iterdir()) == [],
      f"={list(д.iterdir())}")

# --- запись кладёт и подставляет имя ----------------------------------------
д = Path(tempfile.mkdtemp(prefix="мой-проект-"))
итог = ip.разложить(д, писать=True)
check("после записи файлы на месте",
      all((д / п).is_file() for п in пути))
check("имя каталога подставлено вместо заглушки",
      д.name in (д / "CLAUDE.md").read_text(encoding="utf-8"))
check("заглушка не осталась в тексте",
      "@PROJECT@" not in (д / "CLAUDE.md").read_text(encoding="utf-8"))

# --- существующее не трогается ----------------------------------------------
своё = "# МОЙ CLAUDE.md, писал сам\n"
д2 = Path(tempfile.mkdtemp())
(д2 / "CLAUDE.md").write_text(своё, encoding="utf-8")
(д2 / "docs/plans").mkdir(parents=True)
(д2 / "docs/plans/README.md").write_text("# мои планы\n", encoding="utf-8")
итог = ip.разложить(д2, писать=True)
check("чужой CLAUDE.md уцелел дословно",
      (д2 / "CLAUDE.md").read_text(encoding="utf-8") == своё)
check("чужой README планов уцелел",
      (д2 / "docs/plans/README.md").read_text(encoding="utf-8") == "# мои планы\n")
check("оба названы как «уже есть»", set(итог["было"]) == {"CLAUDE.md",
                                                          "docs/plans/README.md"},
      f"={итог['было']}")
check("остальное при этом положено",
      (д2 / ".claude/brief.md").is_file() and (д2 / "docs/reports/README.md").is_file())

# Повтор идемпотентен: второй прогон не кладёт ничего.
итог2 = ip.разложить(д2, писать=True)
check("повторный прогон ничего не кладёт", итог2["положено"] == [],
      f"={итог2['положено']}")
check("и всё числится существующим", len(итог2["было"]) == len(пути))

print(f"  {всего - провалов}/{всего} проверок прошло")
sys.exit(1 if провалов else 0)
