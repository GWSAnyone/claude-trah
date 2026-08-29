#!/usr/bin/env python3
"""Разложить комплект по местам на ЭТОЙ машине.

    install-kit.py [--dry-run] [--replace-hooks] [--home КАТАЛОГ]

Без `--dry-run` пишет на диск. С ним — только показывает, что сделал бы: агенту
положено сперва показать это хозяину машины, а потом уже ставить.

ЧТО ЭТОТ СКРИПТ ДЕЛАЕТ, А ЧТО НЕТ
=================================

Делает механическое: копирует общие файлы, ставит куски брифа без личных,
собирает из них бриф, вписывает проводку хуков в настройки.

НЕ делает того, где надо думать: не сочиняет описание этой машины (его пишет
агент со слов хозяина), не правит файлы, знающие чужие пути, не ставит Serena.
Про всё такое он ГОВОРИТ в конце — списком, а не молчанием.

ПРАВИЛА, КОТОРЫМ ОН СЛЕДУЕТ
===========================

Ничего не затирать молча: перед заменой отличающегося файла рядом кладётся
копия `<имя>.bak-<время>`. Не через git — git не знает, что из лежащего в
рабочем дереве чужое, а что своё.

Отказываться там, где не уверен. Чужая проводка хуков не заменяется без
`--replace-hooks`: у человека может быть своя, и молча стереть её значит
сломать то, чего мы не видели.

Не ставить того, что заведомо не заработает. Хуки, зовущие утилиты, которых на
машине нет (`launch`, `serena-hooks`), из проводки выбрасываются: хук,
ссылающийся в пустоту, — это событие, которое молча не срабатывает, и искать
причину будут в другом месте.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

КОМПЛЕКТ = Path(__file__).resolve().parent.parent
РЕПО = КОМПЛЕКТ.parent
ОТМЕТКА = time.strftime("%Y%m%d-%H%M%S")

# Куски ГЛОБАЛЬНОГО брифа лежат не в этом комплекте.
#
# Граница между двумя комплектами такая: `trah-setup` переносим — он ставится на
# любую машину и ничего не знает про Таусозавра; `workspace-setup` знает про
# службу, `launch` и надзирателя. Куски в `trah-setup/fragments` — области
# `trah`, они уезжают в патченую сборку `claude trah`, а не в бриф. Куски брифа
# — в `workspace-setup/fragments`, и их же копия вшита в `internal/brief/base`
# для службы (за расхождением следит `TestKitAndBaseDoNotDrift`).
#
# Когда комплект сняли без репозитория, соседа рядом нет — тогда шаг с брифом
# пропускается ВСЛУХ, а не собирает бриф из чужих кусков.
КУСКИ_БРИФА = РЕПО / "workspace-setup" / "fragments"

# ── что куда ────────────────────────────────────────────────────────────────
#
# Только УНИВЕРСАЛЬНОЕ. Файлы, знающие чужие пути, здесь намеренно отсутствуют:
# они перечислены в `ПРАВИТЬ_РУКАМИ` и попадают в доклад, а не на диск.
ОБЩЕЕ = [
    # Бриф, который реально подаётся в сессию. До 28.08.2026 его не ставил
    # НИКТО: файл лежал в `~/.claude/brief-trah.md`, положенный когда-то руками,
    # и мог сколь угодно разойтись со сборкой в репозитории — а правит он каждую
    # сессию. Теперь он часть комплекта и приезжает вместе со всем остальным.
    ("trah-brief.md", ".claude/brief.md"),
    ("global-CLAUDE.md", ".claude/CLAUDE.md"),
    ("rules/mcp-discipline.md", ".claude/rules/mcp-discipline.md"),
    ("agents/senior-reviewer.md", ".claude/agents/senior-reviewer.md"),
    # Остальные агенты, 29.08.2026. Набор подобран так, чтобы роли не
    # пересекались: senior-reviewer читает вглубь, locator — вширь,
    # security-reviewer читает враждебно, test-writer единственный пишет.
    ("agents/codebase-locator.md", ".claude/agents/codebase-locator.md"),
    ("agents/security-reviewer.md", ".claude/agents/security-reviewer.md"),
    ("agents/test-writer.md", ".claude/agents/test-writer.md"),
    ("skills/start/SKILL.md", ".claude/skills/start/SKILL.md"),
    ("serena/context-claude-code.yml", ".serena/contexts/claude-code.yml"),
    # Память Serena, общая на все экосистемы. Имя при установке МЕНЯЕТСЯ: в
    # комплекте файлы лежат плоско с приставкой `global-`, а Serena ждёт их в
    # каталоге `memories/global/`. Из-за этого их дважды забывали поставить —
    # сверка по имени файла их не находила.
    ("serena/global-memory_maintenance.md", ".serena/memories/global/memory_maintenance.md"),
    ("serena/global-serena_rules.md", ".serena/memories/global/serena_rules.md"),
    # Ставятся, ХОТЯ и требуют правки под хозяина (см. `ПРАВИТЬ_РУКАМИ`).
    #
    # Граница проведена так: копируем то, что годится после правки нескольких
    # строк, и не копируем то, что без чужой экосистемы бессмысленно целиком.
    # Стиль вывода — главный элемент комплекта, и оставить машину без него
    # ради чужой таблички каталогов значит не поставить комплект вовсе.
    ("output-styles/serena-first.md", ".claude/output-styles/serena-first.md"),
    ("skills/checkpoint/SKILL.md", ".claude/skills/checkpoint/SKILL.md"),
    ("skills/frontend-design/SKILL.md", ".claude/skills/frontend-design/SKILL.md"),
    # Навыки 29.08.2026. `browser` без MCP playwright бесполезен, и это
    # проверяется ниже через ТРЕБУЕТ_MCP: навык, обещающий инструменты, которых
    # в сессии нет, хуже отсутствующего — он уводит по ложному следу.
    ("skills/browser/SKILL.md", ".claude/skills/browser/SKILL.md"),
    ("skills/security/SKILL.md", ".claude/skills/security/SKILL.md"),
    # Кран строки состояния, 29.08.2026. С 2.1.251 во вход строки состояния
    # приезжают `prompt_cache` и `rate_limits` — числа, которых хукам взять
    # больше неоткуда. Кран садится ПЕРЕД настоящим сборщиком строки и
    # передаёт вход дальше, поэтому сборщик остаётся вещью хозяина.
    ("statusline/cache-tap.py", ".claude/statusline/cache-tap.py"),
]

# Навык -> MCP-сервер, без которого он бессмыслен. Нет сервера — навык не
# ставится, а в докладе появляется строка о том, чего не хватает.
ТРЕБУЕТ_MCP = {
    "skills/browser/SKILL.md": "playwright",
}

# Файлы ИЗ СОСЕДНЕГО комплекта `workspace-setup`: (откуда, куда, без чего
# бессмысленно, почему).
#
# Ставятся, только если рядом есть репозиторий И на машине есть то, ради чего
# они существуют. Хук, зовущий несуществующую утилиту, — событие, которое молча
# не срабатывает, и причину будут искать в другом месте.
#
# До 27.08 их не ставил никто: `install-kit` о соседнем комплекте не знал, а
# проводка хуков в `settings-hooks.json` их уже перечисляла. На этой машине они
# оказались только потому, что их когда-то скопировали руками.
СОСЕД = [
    ("hooks/guard-session-launch.py", ".claude/hooks/guard-session-launch.py",
     "launch", "запрет поднимать сессии мимо `launch` без самого `launch` запирает машину"),
    ("hooks/guard-session-launch.test.py", ".claude/hooks/guard-session-launch.test.py",
     "launch", "проверка к нему"),
    ("hooks/guard-tausik-write.py", ".claude/hooks/guard-tausik-write.py",
     "tz", "рубеж правок надзирателя нужен только вместе с Таусозавром"),
    ("hooks/guard-tausik-write.test.py", ".claude/hooks/guard-tausik-write.test.py",
     "tz", "проверка к нему"),
    ("output-styles/tausik.md", ".claude/output-styles/tausik.md",
     "tz", "роль надзирателя нужна только вместе с Таусозавром"),
]

# Хуки ставятся все: сама проводка решает, какие из них включить.
ХУКИ_ИЗ = КОМПЛЕКТ / "hooks"

ПРАВИТЬ_РУКАМИ = {
    "output-styles/serena-first.md":
        "таблица «какой корень активировать» перечисляет чужие каталоги",
    "output-styles/tausik.md":
        "роль надзирателя и его уклады — только для того, у кого есть Таусозавр",
    "skills/checkpoint/SKILL.md":
        "примеры с чужим именем машины и чужим проектом",
    "skills/frontend-design/SKILL.md":
        "ссылки на правила и образцы чужой экосистемы",
    "serena/global-memory_maintenance.md":
        "перечисляет чужие экосистемы",
    "hooks/restore-claude-wrapper.py":
        "запасной путь к обёртке ведёт в чужой репозиторий",
}

НЕ_СТАВИТЬ = {
    "serena/prompt-system_prompt.yml": "запасной вариант, отвергнут",
    "system-prompt.md": "опыт с полной заменой системного промпта",
    "bin/build-system-prompt.sh": "то же самое, в рабочей проводке не участвует",
    "claude.fish": "образец функции fish, ставится по вкусу",
}

# Хук → утилита, без которой он бессмыслен. Нет утилиты — хука не будет.
ТРЕБУЕТ = {
    "guard-session-launch.py": "launch",
    "serena-remind-shim.py": "serena-hooks",
}


class Отчёт:
    def __init__(self, всухую: bool):
        self.всухую = всухую
        self.сделано: list[str] = []
        self.копии: list[str] = []
        self.пропущено: list[str] = []
        self.руками: list[str] = []

    def шаг(self, текст: str) -> None:
        print(("[всухую] " if self.всухую else "") + текст)


def найти(имя: str) -> str | None:
    return shutil.which(имя)


def положить(отчёт: Отчёт, откуда: Path, куда: Path, исполняемый: bool = False) -> None:
    """Скопировать, сохранив прежнее содержимое копией рядом."""
    if not откуда.exists():
        отчёт.пропущено.append(f"{откуда.name}: в комплекте нет")
        return
    новое = откуда.read_bytes()
    if куда.exists():
        if куда.read_bytes() == новое:
            отчёт.шаг(f"  = {куда}")
            return
        копия = куда.with_name(f"{куда.name}.bak-{ОТМЕТКА}")
        if not отчёт.всухую:
            shutil.copy2(куда, копия)
        отчёт.копии.append(str(копия))
    if not отчёт.всухую:
        куда.parent.mkdir(parents=True, exist_ok=True)
        куда.write_bytes(новое)
        if исполняемый:
            куда.chmod(0o755)
    отчёт.сделано.append(str(куда))
    отчёт.шаг(f"  + {куда}")


def проверить_окружение() -> dict[str, str | None]:
    # `tz` и `briefgen` — из соседнего комплекта: без них не ставится половина
    # проводки службы и не собирается бриф. Их отсутствие в этом списке стоило
    # стиля надзирателя: `есть.get("tz")` возвращал None, и файл молча выпадал.
    нужно = ["claude", "python3", "bash", "serena", "serena-hooks", "uv", "node",
             "go", "launch", "tz", "briefgen"]
    return {и: найти(и) for и in нужно}


def настроенные_mcp(дом: Path) -> set[str]:
    """Имена MCP-серверов, настроенных на этой машине.

    Смотрим `~/.claude.json`: `claude mcp add` кладёт их именно туда, а не в
    `settings.json`. Файла нет или он не разбирается — считаем, что серверов
    нет: пропустить навык честнее, чем поставить обещание, которое не сбудется.
    """
    путь = дом / ".claude.json"
    if not путь.exists():
        return set()
    try:
        d = json.loads(путь.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    имена = set(d.get("mcpServers") or {})
    for тело in (d.get("projects") or {}).values():
        имена |= set((тело or {}).get("mcpServers") or {})
    return имена


def поставить_общее(отчёт: Отчёт, дом: Path, есть: dict) -> None:
    отчёт.шаг("Общие файлы:")
    серверы = настроенные_mcp(дом)
    for откуда, куда in ОБЩЕЕ:
        нужен = ТРЕБУЕТ_MCP.get(откуда)
        if нужен and нужен not in серверы:
            отчёт.пропущено.append(
                f"{откуда}: нет MCP-сервера «{нужен}» — навык обещал бы инструменты, "
                f"которых в сессии не будет. Поставить: claude mcp add {нужен} …")
            continue
        положить(отчёт, КОМПЛЕКТ / откуда, дом / куда)

    if КУСКИ_БРИФА.parent.is_dir():
        отчёт.шаг("Из соседнего комплекта workspace-setup:")
        for откуда, куда, нужна, почему in СОСЕД:
            if есть.get(нужна):
                положить(отчёт, РЕПО / "workspace-setup" / откуда, дом / куда,
                         исполняемый=откуда.endswith(".py"))
            else:
                отчёт.пропущено.append(f"workspace-setup/{откуда}: {почему} (нет «{нужна}»)")
    else:
        отчёт.пропущено.append(
            "workspace-setup рядом нет — хуки службы и стиль надзирателя не ставлю")

    отчёт.шаг("Хуки:")
    for файл in sorted(ХУКИ_ИЗ.glob("*.py")):
        положить(отчёт, файл, дом / ".claude/hooks" / файл.name, исполняемый=True)

    # Стиль вывода включается отдельным файлом. Поставить сам стиль и не
    # включить его — самая обидная половина работы: файл лежит, а сессия его не
    # видит, и понять это можно только заметив, что агент ведёт себя обычно.
    включить_стиль(отчёт, дом)


def включить_стиль(отчёт: Отчёт, дом: Path) -> None:
    путь = дом / ".claude/settings.local.json"
    было = {}
    if путь.exists():
        try:
            было = json.loads(путь.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            отчёт.пропущено.append(f"settings.local.json не разбирается ({e}) — стиль не включён")
            return
    if было.get("outputStyle") and было["outputStyle"] != "Serena first":
        отчёт.руками.append(
            f"в settings.local.json уже выбран стиль «{было['outputStyle']}» — не трогаю; "
            "включить наш: \"outputStyle\": \"Serena first\"")
        return
    стало = dict(было)
    стало["outputStyle"] = "Serena first"
    if стало == было:
        отчёт.шаг(f"  = {путь}")
        return
    if not отчёт.всухую:
        путь.parent.mkdir(parents=True, exist_ok=True)
        путь.write_text(json.dumps(стало, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    отчёт.сделано.append(str(путь))
    отчёт.шаг(f"  + {путь} (стиль вывода включён)")


ШАПКА = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


def прочитать_куски(каталог: Path) -> list[dict]:
    """Куски с заголовком-JSON между `---`; тело — всё, что после.

    YAML не берём намеренно: pyyaml в системе нет, а свой разбор YAML — источник
    тихих ошибок ровно там, где ошибка означает промах куска мимо брифа.
    """
    куски = []
    for путь in sorted(каталог.glob("*.md")):
        if путь.name == "README.md":
            continue
        m = ШАПКА.match(путь.read_text(encoding="utf-8"))
        if not m:
            raise SystemExit(f"{путь.name}: нет заголовка между --- и ---")
        try:
            шапка = json.loads(m.group(1))
        except json.JSONDecodeError as e:
            raise SystemExit(f"{путь.name}: заголовок не разбирается как JSON — {e}")
        шапка["файл"] = путь.name
        шапка["тело"] = m.group(2).strip("\n")
        куски.append(шапка)
    return куски


def подпись(тело: str) -> str:
    """Как кусок называется в списке: заголовок раздела без решёток."""
    первая = тело.splitlines()[0] if тело else ""
    return первая.lstrip("#").strip()


def собрать_сборщиком(отчёт: Отчёт, куски: Path) -> str | None:
    """Текст брифа от Go-сборщика: `briefgen` из PATH или `go run` из репозитория.

    Не собрали — не молчим. Бриф, не доехавший до машины, выглядит ровно как
    поставленный: файлы на месте, сессия поднимается, правил нет.
    """
    попытки: list[list[str]] = []
    если_в_пути = найти("briefgen")
    if если_в_пути:
        попытки.append([если_в_пути])
    if (РЕПО / "cmd" / "briefgen").is_dir() and найти("go"):
        попытки.append(["go", "run", "./cmd/briefgen"])

    # Сборщик читает куски из `~/.claude/fragments`, но при `--home` они легли в
    # другое место. Говорим ему явно, иначе бриф соберётся из чужого каталога.
    окружение = {**os.environ, "TAUSIK_FRAGMENTS": str(куски)}
    for команда in попытки:
        try:
            г = subprocess.run(команда, cwd=РЕПО, env=окружение, timeout=300,
                               capture_output=True, text=True)
        except (OSError, subprocess.TimeoutExpired) as e:
            отчёт.пропущено.append(f"{' '.join(команда)}: {e}")
            continue
        if г.returncode == 0 and г.stdout.strip():
            return г.stdout
        отчёт.пропущено.append(
            f"{' '.join(команда)}: код {г.returncode} {(г.stderr or '').strip()[:200]}")

    отчёт.руками.append(
        "БРИФ НЕ СОБРАН: нет ни `briefgen` в PATH, ни Go рядом с репозиторием. "
        "Собрать: go build -o ~/.local/bin/briefgen ./cmd/briefgen && briefgen --write")
    return None


def поставить_бриф(отчёт: Отчёт, дом: Path) -> None:
    """Куски глобального брифа на машину и собранный из них `~/.claude/brief.md`.

    СОБИРАЕТ НЕ ЭТОТ СКРИПТ. Текст брифа даёт `briefgen` — тот же Go-сборщик,
    которым пользуется служба. Своего сборщика здесь нет НАМЕРЕННО: два
    сборщика одного текста расходятся молча, и узнаётся об этом по странному
    поведению сессии через месяц. Ровно это и случилось с прежней редакцией —
    она звала питоновский `trah.собрать_бриф("global")`, а после разделения
    комплектов глобальных кусков в `trah-setup` не осталось, и установка падала
    словами «кусков брифа для области global нет».

    Пишем файл сами, а не `briefgen --write`: здесь есть `--dry-run` и
    `--home`, и всё, что ложится на диск, должно проходить через одни правила —
    с копией прежнего рядом.
    """
    if not КУСКИ_БРИФА.is_dir():
        отчёт.пропущено.append(
            f"куски брифа: нет {КУСКИ_БРИФА} — комплект сняли без репозитория")
        return

    куски = [к for к in прочитать_куски(КУСКИ_БРИФА)
             if к.get("route") == "brief" and к.get("scope") != "trah"
             and not к.get("personal")]
    куски.sort(key=lambda к: (к.get("scope") != "global", к.get("scope", ""),
                              к.get("order", 0), к["id"]))
    личных = len([к for к in прочитать_куски(КУСКИ_БРИФА) if к.get("personal")])
    отчёт.шаг(f"Куски брифа: ставлю {len(куски)}, личных пропускаю {личных}")

    указатель = []
    for к in куски:
        м = {
            "id": к["id"],
            "scope": к.get("scope", ""),
            "kind": к.get("kind", "section"),
            "order": к.get("order", 0),
            "label": к.get("label") or подпись(к["тело"]),
            "why": к.get("why", ""),
            "bytes": len(к["тело"].encode("utf-8")),
        }
        if к.get("where"):
            м["where"] = к["where"]
        if к.get("computed"):
            м["computed"] = True
        указатель.append(м)

    цель = дом / ".claude/fragments"
    файл_указателя = цель / "index.json"
    # Убираем только то, что клали САМИ: имена из прежнего указателя, которых в
    # новом нет. Чистить каталог по списку «нужных» нельзя — там же лежит
    # `computed/` со счётом машины, который собирает служба, и чужие куски,
    # положенные руками. Снести их значило бы оставить сессию без фактов о
    # машине, и молча.
    прежние: set[str] = set()
    if файл_указателя.exists():
        try:
            прежние = {м["id"] + ".md"
                       for м in json.loads(файл_указателя.read_text(encoding="utf-8"))}
        except (json.JSONDecodeError, TypeError, KeyError):
            прежние = set()
    лишние = sorted(прежние - {к["id"] + ".md" for к in куски})

    if not отчёт.всухую:
        цель.mkdir(parents=True, exist_ok=True)
        for имя in лишние:
            (цель / имя).unlink(missing_ok=True)
        for к in куски:
            shutil.copyfile(КУСКИ_БРИФА / к["файл"], цель / (к["id"] + ".md"))
        файл_указателя.write_text(
            json.dumps(указатель, ensure_ascii=False, indent=2), encoding="utf-8")
    отчёт.сделано.append(str(цель))
    отчёт.шаг(f"  + {цель}"
              + (f" (убрано отменённых: {len(лишние)})" if лишние else ""))

    текст = собрать_сборщиком(отчёт, цель)
    if текст is None:
        return

    без_обёртки(отчёт, дом, текст)
    # `brief-zavr.md`, а не `brief.md`: с 28.08.2026 в сессии подаётся бриф
    # режима (он приезжает из `ОБЩЕЕ` как `trah-brief.md` → `.claude/brief.md`),
    # а эта редакция законсервирована рядом. Причина — в `trah-setup/bin/claude`,
    # у ветки `TRAH_MODE=1`: две редакции одной дисциплины разошлись и обе
    # уезжали в один системный промпт.
    бриф = дом / ".claude/brief-zavr.md"
    if бриф.exists() and бриф.read_text(encoding="utf-8") == текст:
        отчёт.шаг(f"  = {бриф}")
        return
    if бриф.exists():
        копия = бриф.with_name(f"brief.md.bak-{ОТМЕТКА}")
        if not отчёт.всухую:
            shutil.copy2(бриф, копия)
        отчёт.копии.append(str(копия))
    if not отчёт.всухую:
        бриф.parent.mkdir(parents=True, exist_ok=True)
        бриф.write_text(текст, encoding="utf-8")
    отчёт.сделано.append(str(бриф))
    отчёт.шаг(f"  + {бриф} ({len(текст)} байт, без личных кусков)")


def без_обёртки(отчёт: Отчёт, дом: Path, текст: str) -> None:
    """Запасная дорога для правил там, где обёртки быть не может.

    Правила подаёт системным промптом обёртка `~/.local/bin/claude` — скрипт
    bash. Под Windows её нет и не будет без переписывания, а значит `brief.md`
    там просто лежит: никто его не читает.

    Поэтому под Windows бриф кладётся в `~/.claude/CLAUDE.md` — этот файл CLI
    читает сам, на любой ОС. Дорога дороже (файл перечитывается, а не лежит в
    кэшируемом префиксе), но правила ДОХОДЯТ, а это важнее цены. Молча оставить
    машину без правил — худший из возможных исходов: всё выглядит поставленным.
    """
    if os.name != "nt":
        return
    цель = дом / ".claude/CLAUDE.md"
    шапка = ("<!-- Бриф положен сюда, а не подан системным промптом: под Windows\n"
             "     обёртки ~/.local/bin/claude нет. Дороже, но правила доходят. -->\n\n")
    новое = шапка + текст
    if цель.exists() and цель.read_text(encoding="utf-8") != новое:
        копия = цель.with_name(f"CLAUDE.md.bak-{ОТМЕТКА}")
        if not отчёт.всухую:
            shutil.copy2(цель, копия)
        отчёт.копии.append(str(копия))
    if not отчёт.всухую:
        цель.write_text(новое, encoding="utf-8")
    отчёт.сделано.append(str(цель))
    отчёт.шаг(f"  + {цель} (Windows: бриф едет через CLAUDE.md, обёртки нет)")


def проводка(отчёт: Отчёт, дом: Path, есть: dict, заменять: bool) -> None:
    """Вписать хуки и запреты в настройки, не тронув остальное."""
    # `@PY@` — тем же интерпретатором, каким запущен установщик.
    #
    # В шаблоне стоял `python3`, и это молчаливая поломка на Windows: там его
    # нет, есть `python` и `py`. Хук с несуществующей командой не кричит —
    # событие просто не срабатывает, и машина остаётся без гардов, не сказав
    # об этом ни слова. `sys.executable` — единственный путь, про который точно
    # известно, что он работает: им нас только что и запустили.
    шаблон = json.loads((КОМПЛЕКТ / "settings-hooks.json").read_text(encoding="utf-8")
                        .replace("@HOME@", str(дом))
                        .replace("@PY@", sys.executable))
    хуки = выбросить_ненужные(отчёт, шаблон["hooks"], есть)

    путь = дом / ".claude/settings.json"
    было = {}
    if путь.exists():
        try:
            было = json.loads(путь.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            отчёт.пропущено.append(f"settings.json не разбирается ({e}) — проводку не трогаю")
            return

    if было.get("hooks") and было["hooks"] != хуки and not заменять:
        # Говорим, ЧЕМ она отличается. «Не трогаю» без этого — приглашение
        # гадать: расхождение может быть в одном событии, а может в половине
        # проводки, и решение хозяина от этого разное.
        отчёт.руками.append(
            "в settings.json своя проводка хуков — не трогаю ("
            + разница_проводки(было["hooks"], хуки)
            + "). Посмотреть глазами и, если менять, повторить с --replace-hooks")
        return

    стало = dict(было)
    стало["hooks"] = хуки
    запреты = list(было.get("permissions", {}).get("deny", []))
    for з in шаблон["permissions"]["deny"]:
        if з not in запреты:
            запреты.append(з)
    права = dict(было.get("permissions", {}))
    права["deny"] = запреты
    стало["permissions"] = права

    # Переменные окружения ДОПИСЫВАЮТСЯ, чужие не трогаются. Это ограничители
    # подагентов: после 29.08.2026, когда делегирование перестало быть
    # запрещённым, отсутствие потолка стало настоящим риском — руководство
    # Anthropic по Opus 5 прямо предупреждает, что эта модель делегирует
    # охотнее прежних и на мелких задачах множит цену.
    #
    # Значение глубины выверено ЗАПУСКОМ, а не догадкой: `min:1` в схеме
    # допускал оба отсчёта, и `1` могло означать «вложенности нет» либо
    # «делегирования нет вовсе». Прогон 29.08 при 1, 2 и 3 показал, что
    # главная сессия зовёт подагента при любом, то есть считается вложенность
    # подагентов. Единица запрещает агенту звать агента и больше ничего.
    наши_env = шаблон.get("env") or {}
    if наши_env:
        env = dict(было.get("env") or {})
        for ключ, значение in наши_env.items():
            env.setdefault(ключ, значение)
        стало["env"] = env

    if стало == было:
        отчёт.шаг(f"  = {путь}")
        return
    if путь.exists():
        копия = путь.with_name(f"settings.json.bak-{ОТМЕТКА}")
        if not отчёт.всухую:
            shutil.copy2(путь, копия)
        отчёт.копии.append(str(копия))
    if not отчёт.всухую:
        путь.parent.mkdir(parents=True, exist_ok=True)
        путь.write_text(json.dumps(стало, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    отчёт.сделано.append(str(путь))
    отчёт.шаг(f"  + {путь} (проводка хуков и запреты)")


def разница_проводки(живая: dict, наша: dict) -> str:
    """Чем живая проводка отличается от нашей — коротко, событиями и командами."""
    def команды(проводка: dict) -> dict[str, set[str]]:
        вышло: dict[str, set[str]] = {}
        for событие, записи in проводка.items():
            для_события = вышло.setdefault(событие, set())
            for запись in записи:
                for х in запись.get("hooks", []):
                    # Сравниваем по ИМЕНАМ, а не по строке команды целиком: в ней
                    # абсолютные пути и путь к интерпретатору, и разойтись они
                    # могут, не меняя ни одного хука.
                    имена = [Path(с).name for с in х.get("command", "").split()]
                    для_события.add(" ".join(
                        и for и in имена if not и.startswith("python")))
        return вышло

    ж, н = команды(живая), команды(наша)
    только_живые = sorted(set(ж) - set(н))
    только_наши = sorted(set(н) - set(ж))
    разные = sorted(с for с in set(ж) & set(н) if ж[с] != н[с])
    части = []
    if только_наши:
        части.append("в живой нет событий: " + ", ".join(только_наши))
    if только_живые:
        части.append("в нашей нет событий: " + ", ".join(только_живые))
    if разные:
        части.append("разный состав хуков: " + ", ".join(разные))
    return "; ".join(части) or "различие только в путях и порядке"


def выбросить_ненужные(отчёт: Отчёт, хуки: dict, есть: dict) -> dict:
    """Убрать хуки, зовущие то, чего на машине нет.

    Хук, ссылающийся в пустоту, — это событие, которое молча не срабатывает.
    Особенно `guard-session-launch`: он ЗАПРЕЩАЕТ поднимать сессии иначе как
    через `launch`, и без этой утилиты машина остаётся без сессий вовсе.
    """
    вышло = {}
    for событие, записи in хуки.items():
        новые_записи = []
        for запись in записи:
            оставить = []
            for х in запись.get("hooks", []):
                команда = х.get("command", "")
                нужна = next((у for имя, у in ТРЕБУЕТ.items() if имя in команда), None)
                if нужна and not есть.get(нужна):
                    отчёт.пропущено.append(
                        f"хук {команда.split('/')[-1]} не вписан: на машине нет «{нужна}»")
                    continue
                оставить.append(х)
            if оставить:
                новые_записи.append({**запись, "hooks": оставить})
        if новые_записи:
            вышло[событие] = новые_записи
    return вышло


def доклад(отчёт: Отчёт, есть: dict) -> None:
    print("\n" + "─" * 70)
    print("ОКРУЖЕНИЕ")
    for имя, путь in есть.items():
        print(f"  {'есть ' if путь else 'НЕТ  '} {имя}")
    if not есть["serena"]:
        print("\n  ⚠ Serena не найдена. Без неё не работает половина комплекта:")
        print("    uv tool install --from git+https://github.com/oraios/serena serena-agent")
        print("    claude mcp add serena -s user -- ~/.local/bin/serena start-mcp-server "
              "--context claude-code")

    print(f"\nПОСТАВЛЕНО: {len(отчёт.сделано)}")
    if отчёт.копии:
        print(f"\nКОПИИ ПРЕЖНИХ ФАЙЛОВ ({len(отчёт.копии)}):")
        for к in отчёт.копии:
            print(f"  {к}")
    if отчёт.пропущено:
        print(f"\nПРОПУЩЕНО ({len(отчёт.пропущено)}):")
        for п in отчёт.пропущено:
            print(f"  {п}")

    print("\nОСТАЛОСЬ СДЕЛАТЬ РУКАМИ — этого скрипт не умеет:")
    for п in отчёт.руками:
        print(f"  • {п}")
    print("  • Завести кусок брифа про ЭТУ машину: ОС, оболочки, чем собирают,")
    print("    где каталоги проектов. Личные куски прежнего хозяина не поставлены.")
    for файл, чем in ПРАВИТЬ_РУКАМИ.items():
        print(f"  • {файл} — {чем}")
    print("  • Обёртка bin/claude → ~/.local/bin/claude (см. INSTALL.md, раздел «Обёртка»)")

    print("\nПРОВЕРИТЬ:")
    print("  python3 ~/.claude/hooks/guard-destructive.test.py   # провалов: 0")
    print("  python3 trah-setup/bin/check-brief-delivery.py     # бриф доезжает")
    print("─" * 70)
    if отчёт.всухую:
        print("Это был показ. Ничего не записано. Повторить без --dry-run.")


def main() -> int:
    р = argparse.ArgumentParser(description="разложить комплект по местам")
    р.add_argument("--dry-run", action="store_true", help="только показать")
    р.add_argument("--replace-hooks", action="store_true",
                   help="заменить чужую проводку хуков своей")
    р.add_argument("--home", default=str(Path.home()), help="куда ставить")
    а = р.parse_args()

    дом = Path(а.home)
    отчёт = Отчёт(а.dry_run)
    есть = проверить_окружение()

    if not есть["python3"]:
        print("python3 не найден — на нём держатся все хуки", file=sys.stderr)
        return 1

    поставить_общее(отчёт, дом, есть)
    поставить_бриф(отчёт, дом)
    проводка(отчёт, дом, есть, а.replace_hooks)
    доклад(отчёт, есть)
    return 0


if __name__ == "__main__":
    sys.exit(main())
