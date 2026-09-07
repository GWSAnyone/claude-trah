#!/usr/bin/env python3
"""PreToolUse-гард на деструктивные команды.

Блокирует то, что уничтожает НЕЗАКОММИЧЕННУЮ работу без возможности вернуть.
Работает независимо от режима разрешений — в том числе в auto mode.

Exit 2 = блокировка, stderr уходит модели как сообщение об ошибке.
Exit 0 = пропустить.
"""

import json
import os
import re
import shlex
import sys

# --- Жёсткий блок: уничтожает несохранённую работу, отката нет -------------

HARD_BLOCK = [
    (
        r"\bgit\s+reset\s+(--hard|--merge|--keep)\b",
        "git reset --hard wipes uncommitted edits with no way to bring them back.\n"
        "Need a rollback — make a `cp` of the working file into a temporary copy first.",
    ),
    (
        r"\bgit\s+clean\s+(-\S*f|--force)",
        "git clean -f deletes untracked files — including work not yet added.\n"
        "Look first at what exactly would go: `git clean -nd`.",
    ),
    (
        # Три формы, и до 29.08.2026 ловилась только первая. Разбор
        # security-reviewer в тот день, все три проверены запуском:
        #   `git checkout -- x.go`        — ловилась
        #   `git checkout HEAD -- x.go`   — ПРОХОДИЛА, стирает ровно то же
        #   `git checkout -f master`      — ПРОХОДИЛА, затирает правки при смене ветки
        # `git checkout -b новая` и `git checkout master` остаются законными:
        # без `-f` git сам откажется, если правки пришлось бы затереть.
        r"\bgit\s+checkout\b(?:(?=[^;\n]*\s--(?:\s|$))|\s+(?:-f|--force)\b|\s+\.(?:\s|$))",
        "git checkout -- <file> rolls the file back to HEAD and wipes the edits.\n"
        "This very command once destroyed 184 lines of unsaved work.\n"
        "A ref before the dashes (`git checkout HEAD -- x`) and `-f` do the same thing.\n"
        "Need a rollback — your own backup via `cp`; git is not an undo mechanism for an agent.",
    ),
    (
        # `git checkout-index -f -a` раскладывает индекс поверх рабочего дерева.
        r"\bgit\s+checkout-index\b[^;\n]*(?:\s-\S*f|\s--force)\b",
        "git checkout-index --force overwrites working-tree files from the index.",
    ),
    (
        # `git rm -f` и `git rm -rf .` уносят файлы вместе с несохранёнными
        # правками. Без `-f` git отказывается сам, поэтому ловим только силу.
        # Дефис обязан начинать ОТДЕЛЬНОЕ слово: до 07.09.2026 стояло
        # `[^;\n]*(?:-\S*f|…)`, и `-\S*f` находился внутри любого пути с
        # дефисом и буквой f — `git rm trah-setup/bin/bash-diff.py`
        # блокировался как силовое удаление. Проверено запуском в тот день.
        r"\bgit\s+rm\b[^;\n]*(?:\s-\S*f|\s--force)\b",
        "git rm --force deletes files together with their uncommitted edits.\n"
        "Without --force git refuses on modified files by itself; the flag switches that guard off.",
    ),
    (
        # --staged без --worktree = только снять из индекса, это безопасно
        r"\bgit\s+restore\b(?!(?=.*--staged)(?!.*--worktree))",
        "git restore <file> is the modern equivalent of checkout --; it wipes edits in the working tree.\n"
        "If the aim is only to unstage, use `git restore --staged <file>`.",
    ),
    (
        # list/show читают стек и ничего не прячут
        r"\bgit\s+stash\b(?!\s+(list|show))",
        "git stash hides uncommitted work; an agent cannot know which of the edits are yours.\n"
        "Forbidden by the owner's rule. Looking at the stack is fine: `git stash list`.",
    ),
    (
        r"\bgit\s+push\b.*(--force(?!-with-lease)|\s-f\b)",
        "A force-push rewrites published history.\n"
        "If it is genuinely needed — `--force-with-lease` at the very least, and only with the owner's permission.",
    ),
    (
        r"\bgit\s+branch\s+(-D|--delete\s+--force)",
        "Force-deleting a branch loses commits that were never merged.",
    ),
    (
        # Только САМ корень или САМ домашний каталог. Подпути внутри дома
        # (`rm -rf ~/.cache/x`) — обычная работа, блокировать их нельзя.
        r"\brm\s+(-\S*[rR]\S*f|-\S*f\S*[rR])\s+"
        r"(/|~|~/|\$HOME|\$\{HOME\}|/\*|~/\*)(\s|$|[;&|])",
        "rm -rf over the filesystem root or over the whole home directory.",
    ),
    (
        r"\brm\b.*\.git/hooks/pre-commit",
        "pre-commit is the build-and-tests gate before a commit (it stands in 14\n"
        "repositories of the ecosystem). Removing it means switching off your own\n"
        "supervision: a commit goes through without building and without passing tests.\n"
        "It is not about history — there is no history in hooks. It is that the gate\n"
        "is not removed by the one it checks. Does not build, or red tests —\n"
        "fix it, do not take the check away.",
    ),
    (
        # В `.git/hooks/` истории нет: убрать ОТДЕЛЬНУЮ уведомлялку
        # (`post-commit` и подобные) по распоряжению владельца законно, и
        # запрет на это мешал работе (19.08.2026). Поэтому исключение узкое —
        # ровно один именованный файл внутри hooks. Каталог целиком,
        # `hooks/` с косой чертой и маска (`hooks/*`) исключением НЕ
        # считаются: они уносят и `pre-commit`. Он же вынесен отдельным
        # правилом выше — чтобы отказ объяснял причину, а не историю; здесь
        # он повторён в исключении, чтобы правило было верным и в одиночку.
        r"\brm\b.*\.git(?!/hooks/(?!pre-commit)[^\s/;&|*?\[]+)(/|\s|$)",
        "Deleting .git destroys the repository's entire history.",
    ),
    (
        # `find . -name '*.go' -delete` уносит файлы без всякого `rm`.
        r"\bfind\b[^;\n]*\s-delete\b",
        "find -delete removes files it matched, uncommitted edits included.\n"
        "Look at the list first: run the same find without -delete.",
    ),
    (
        # Обнуление файла на месте: содержимое исчезает, файл остаётся.
        r"\btruncate\b[^;\n]*-s\s*0\b",
        "truncate -s 0 empties the file in place; the uncommitted content is gone.",
    ),
    # --- Массовое убийство процессов ---------------------------------------
    #
    # 01.09.2026: `pkill -f "exe/bot"` совпал со ВСЕМИ ботами экосистемы, а не
    # с одним. Шаблон ищется по всей командной строке, и общий кусок пути
    # накрыл каждого. Живые боты легли разом, поднимал владелец руками.
    #
    # Правило владельца после этого — категорическое: «ЗАПРЕТИТЬ ВСЕ ЧТО МОЖЕТ
    # УБИТЬ СЕССИИ ВОТ ТАК, НИКАКОГО ПКИЛЛА И НИЧЕГО ПОДОБНОГО, НОРМАЛЬНАЯ
    # ОСТАНОВКА ТОЛЬКО». Поэтому здесь жёсткий блок, а не согласие владельца:
    # у `pkill` нет безопасной формы, которую агент отличил бы заранее, — он
    # не знает, сколько процессов совпадёт, пока не убьёт их.
    #
    # `pgrep` не трогаем: он читает и никого не останавливает.
    (
        r"\bpkill\b",
        "pkill matches a pattern against every process and kills all of them at once.\n"
        "On 01.09.2026 `pkill -f \"exe/bot\"` matched every bot in the ecosystem, not one.\n"
        "Stop a service the normal way: through the unit or supervisor that started it,\n"
        "one named service at a time. Need to see what is running — `pgrep -a` reads and kills nothing.",
    ),
    (
        r"\bkillall\b",
        "killall stops every process with that name at once, across the whole machine.\n"
        "Stop a service the normal way, by its unit name, one at a time.",
    ),
    (
        r"\bkill\s+(-9|-KILL|-SIGKILL|-s\s*(9|KILL|SIGKILL))\b",
        "SIGKILL gives the process no chance to shut down: unflushed state and open\n"
        "orders stay as they were at the instant it died. Stop it normally and let it finish.",
    ),
    (
        r"\bxargs\b[^;\n]*\bkill\b|\bfuser\b[^;\n]*-k\b|\bsystemctl\b[^;\n]*\bkill\b",
        "A mass kill: the targets come from a pipe or from a whole cgroup.\n"
        "Stop the service normally, one unit at a time.",
    ),
]

# Правила, которые ищутся ПО ВСЕЙ СТРОКЕ, а не с начала сегмента.
#
# Спуск в произвольный интерпретатор гард не делает и делать не может: разбирать
# питон и перл внутри `-e` — отдельная задача, и решать её регэкспом нельзя.
# Поэтому ловим ровно те вызовы, у которых в однострочнике агента нет
# безобидного применения, — и требуем, чтобы перед вызовом стоял интерпретатор.
#
# Почему не в общем списке: там правила закреплены на НАЧАЛО сегмента, а здесь
# опасное слово лежит внутри аргумента. Почему не голым поиском: без якоря на
# интерпретатор под правило попал бы и `grep -r shutil.rmtree .`, то есть
# чтение вместо удаления. Длина между якорем и вызовом ограничена намеренно:
# неограниченный квантификатор на длинной строке даёт экспоненциальный откат.
HARD_BLOCK_WHOLE = [
    (
        r"\b(?:python3?|perl|ruby|node|php)\b[^\n]{0,300}?"
        r"\b(?:shutil\.rmtree|os\.removedirs|unlink\s+glob)\b",
        "A recursive tree removal from inside an interpreter one-liner.\n"
        "It bypasses every rule written for the shell, and that is exactly why it is blocked here.\n"
        "Deleting something specific — name the paths and use rm on them, so the guard can see it.",
    ),
    (
        # `kill $(pgrep -f bot)` и `kill \`pgrep …\`` — то же массовое убийство,
        # только список целей приезжает из подстановки. Здесь, а не в общем
        # списке: разбиение на сегменты уносит подстановку в отдельный сегмент,
        # и от команды остаётся голое `kill`, под правило уже не подходящее.
        r"(?:^|[;&|]\s*)kill\s+[^\n]{0,120}?(?:\$\(|`)",
        "The list of victims comes from a substitution, so you cannot know how many\n"
        "processes this kills until it has killed them.\n"
        "Name the one PID, or stop the service normally.",
    ),
]

# Пути, снос которых равен потере всего. Проверяются по ТОКЕНАМ, а не регэкспом:
# `rm -r -f /` с раздельными флагами и `rm -rf "/"` в кавычках регэксп из
# правила выше не ловил, и оба прошли живой прогон 29.08.2026.
_ROOTISH = frozenset({"", "~", "$HOME", "${HOME}", "*", "/*", "~/*", "$HOME/*"})


def _rm_wipes_root(segment: str) -> bool:
    """`rm` с рекурсией и силой, направленный в корень или в весь дом.

    Флаги считаем в любой форме: слипшиеся (`-rf`), раздельные (`-r -f`) и
    длинные (`--recursive --force`). Цель сравниваем после снятия хвостовой
    косой черты, поэтому `/`, `~/` и `$HOME/` попадают в одну корзину, а
    `~/.cache/go-build` в неё не попадает.
    """
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return False
    if not tokens or os.path.basename(tokens[0]).lower() != "rm":
        return False
    recursive = force = False
    targets = []
    for token in tokens[1:]:
        if token == "--":
            continue
        if token.startswith("--"):
            recursive = recursive or token == "--recursive"
            force = force or token == "--force"
            continue
        if token.startswith("-") and len(token) > 1:
            recursive = recursive or "r" in token or "R" in token
            force = force or "f" in token
            continue
        targets.append(token)
    if not (recursive and force):
        return False
    return any(t.rstrip("/") in _ROOTISH for t in targets)


# Проверки, которые регэкспом не выражаются. Формат тот же: (проверка, причина).
HARD_BLOCK_FUNCS = [
    (
        _rm_wipes_root,
        "rm -rf over the filesystem root or over the whole home directory.\n"
        "Separate flags (-r -f) and quotes do not make it a different command.",
    ),
]

# --- Требуют явного разрешения владельца ------------------------------------

NEEDS_OWNER = [
    (
        r"\bgit\s+commit\b",
        "A commit only with the owner's permission, asked EVERY time.",
    ),
    (
        r"\bgit\s+push\b",
        "A push only with the owner's permission.",
    ),
]

OWNER_MARKER = "OWNER_OK=1"

# Маркер в команде пишет САМ агент — он показывает намерение, но ничего не
# доказывает: агент, решивший закоммитить без спроса, поставит его себе сам.
# Поэтому вторым условием требуем согласие в ПОСЛЕДНЕМ сообщении владельца.
# Формулировки живые: заставлять человека писать спецсинтаксис ради гарда —
# способ сделать гард противным и первым кандидатом на отключение.
_CONSENT = re.compile(
    r"(?:^|\W)(?:"
    r"комми[тчь]\w*|закомми\w*|заком\w*|"
    r"пуш\w*|запуш\w*|push|commit|"
    r"да|ок|окей|ага|давай|валяй|погнали|го|"
    r"можно|разрешаю|разрешено|согласен|одобряю|"
    r"yes|ok|okay|go\s+ahead|sure|allow|allowed|approve|approved"
    r")(?:\W|$)",
    re.IGNORECASE,
)

# Отказ перебивает согласие только когда стоит ПОЗЖЕ него: «нет, не коммить»
# содержит и «нет», и «коммить». Список намеренно без «делай» и «ладно» —
# они встречаются в речи не про коммит, и словарь ими расширять опаснее.
_REFUSAL = re.compile(
    r"(?:^|\W)(?:не\s+комми\w*|не\s+пуш\w*|не\s+надо|нет|стоп|отмена|"
    r"don'?t|do\s+not|stop|cancel)(?:\W|$)",
    re.IGNORECASE,
)
# Одиночное английское `no` из списка УБРАНО 29.08.2026. В технической речи оно
# встречается постоянно и не про коммит: «no changes», «no errors», «there is no
# bug here». Каждое такое слово в последнем сообщении владельца гасило коммит,
# на который он уже согласился. Отказ по-английски остаётся выразим: `don't`,
# `do not`, `stop`, `cancel` — все они однозначны, а `нет` по-русски сохранено:
# отдельным словом оно почти всегда именно отказ.

_TRANSCRIPT_TAIL_BYTES = 64 * 1024

# Потолок обратного чтения. Стенограмма бывает на десятки мегабайт, и читать
# её целиком ради одного сообщения незачем: если владелец не писал последние
# 32 МиБ, это не рабочая сессия, а что-то другое.
_TRANSCRIPT_MAX_BYTES = 32 * 1024 * 1024

# Разделители, после которых начинается НОВАЯ команда.
_SPLIT = re.compile(r"\|\||&&|[;\n|&]|\$\(|`|\)")

# Одиночные разделители, которые режут строку вне кавычек.
_ONE_CHAR_SPLIT = frozenset(";\n|&`)")
_TWO_CHAR_SPLIT = ("||", "&&", "$(")


def _split_respecting_quotes(command: str) -> list[str]:
    """Разрез по разделителям, НЕ заглядывая внутрь кавычек.

    Регэксп `_SPLIT` про кавычки не знает и режет по ним тоже. Проверено
    запуском 29.08.2026: `bash -c 'git reset --hard "x|y"'` разваливался на
    `bash -c 'git reset --hard "x` и `y"'`, у обоих кусков кавычка непарная,
    `shlex` на них спотыкался, спуска внутрь оболочки не происходило — и
    команда проходила целиком. Тот же дефект подтверждён в соседнем хуке
    `warn-grep-root.py`, где обычный `grep -rn 'func|method' .` уходил молча.

    Незакрытая кавычка оставляет хвост одним куском: это безопаснее, чем
    резать наугад. На такой случай вызывающий добавляет ещё и наивный разрез.
    """
    части: list[str] = []
    кусок: list[str] = []
    кавычка: str | None = None
    i, n = 0, len(command)
    while i < n:
        c = command[i]
        if кавычка:
            кусок.append(c)
            if c == "\\" and кавычка == '"' and i + 1 < n:
                кусок.append(command[i + 1])
                i += 2
                continue
            if c == кавычка:
                кавычка = None
            i += 1
            continue
        if c in ("'", '"'):
            кавычка = c
            кусок.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            кусок.append(c)
            кусок.append(command[i + 1])
            i += 2
            continue
        if command[i:i + 2] in _TWO_CHAR_SPLIT:
            части.append("".join(кусок))
            кусок = []
            i += 2
            continue
        if c in _ONE_CHAR_SPLIT:
            части.append("".join(кусок))
            кусок = []
            i += 1
            continue
        кусок.append(c)
        i += 1
    части.append("".join(кусок))
    return части
_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=\S*\s+")
_PREFIX = re.compile(
    r"^(sudo(\s+-\S+)*|env|nohup|setsid|time|command|exec|nice|ionice|stdbuf|doas)\s+"
)


# Оболочки, чей аргумент `-c` — целая командная строка, а не имя файла.
# `bash -c 'git reset --hard'` приходит гарду ОДНИМ кавыченным токеном, и
# никакой разбор верхнего уровня внутрь не заглядывает. Проверено фактом
# 15.08.2026: пять деструктивных команд прошли сквозь гард через эту щель.
_SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh", "ash", "busybox"})

# Вложенность ограничена: `bash -c "sh -c '…'"` бывает, три уровня — заведомо
# больше любого настоящего вызова. Именованный предел лучше молчаливой
# рекурсии: превышение становится решением, а не переполнением стека.
_MAX_SHELL_DEPTH = 3


def _shell_payloads(segment: str):
    """Строки, которые сегмент передаёт другой оболочке через `-c` или `<<<`.

    Разбираем через shlex: `-c` ищется среди токенов, а не регэкспом по
    строке, иначе `--config` или путь со словом `-c` внутри сойдут за флаг.

    Строка-здесь (`bash <<< 'git reset --hard'`) — такая же передача команды
    оболочке, только другим синтаксисом. Разбор 29.08.2026 показал, что она
    проходила мимо: `<<<` не разделитель, а `-c` в токенах нет.
    """
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return  # незакрытая кавычка: разобрать нечем, наружный слой уже проверен
    if not tokens:
        return
    base = os.path.basename(tokens[0]).lower()
    if base not in _SHELLS:
        return
    for i, token in enumerate(tokens[1:], start=1):
        if token == "<<<":
            if i + 1 < len(tokens):
                yield tokens[i + 1]
            continue
        # `-c` бывает в связке: `-lc`, `-ec`. Длинный `--color` — не связка.
        if token.startswith("-") and not token.startswith("--") and "c" in token:
            if i + 1 < len(tokens):
                yield tokens[i + 1]
            return


# Команды, которые ЗАПУСКАЮТ другую команду, а не являются ею. Значение —
# сколько числовых аргументов команда берёт перед настоящей командой
# (`timeout 5 …`, `nice 10 …`).
_TRANSPARENT = {
    "sudo": 0, "doas": 0, "env": 0, "nohup": 0, "setsid": 0, "time": 0,
    "command": 0, "exec": 0, "stdbuf": 0,
    "timeout": 1, "nice": 1, "ionice": 1,
}

# Флаги обёрток, забирающие следующее слово как значение. Без этого списка
# `sudo -u root bash -c '…'` разбирается так, будто команда — это `root`,
# и спуск внутрь оболочки не происходит.
_FLAG_TAKES_VALUE = frozenset({
    "-u", "-g", "-p", "-C", "-r", "-t", "-U", "-h",  # sudo / doas
    "-n", "-k", "-s", "-c", "-i", "-o",              # nice / ionice / stdbuf / timeout
})


def _strip_prefixes(segment: str) -> str:
    """Сегмент без обёрток вроде `sudo`, `env FOO=1`, `nice -n 10`, `timeout 5`.

    Разбор на токенах, а не регэкспом: флаг с отдельным значением (`nice -n 10`)
    регэкспом не снимается, и `bash` перестаёт быть первым токеном — именно так
    `nice -n 10 bash -c 'git reset --hard'` проходил мимо гарда.
    """
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return segment
    if not tokens:
        return segment

    i = 0
    changed = False
    while i < len(tokens):
        base = os.path.basename(tokens[i]).lower()
        if base not in _TRANSPARENT:
            break
        numbers = _TRANSPARENT[base]
        i += 1
        changed = True
        while i < len(tokens):
            token = tokens[i]
            if token.startswith("-"):
                i += 1
                # `-n 10`, `-u root`: значение отдельным словом. Слипшуюся
                # форму (`-n10`, `-c2`) shlex отдаёт одним токеном, и она
                # уходит предыдущей веткой.
                if i < len(tokens) and token in _FLAG_TAKES_VALUE:
                    i += 1
                continue
            if _ENV_ASSIGN_TOKEN.match(token):
                i += 1
                continue
            if numbers and _NUMBER.match(token):
                i += 1
                numbers -= 1
                continue
            break
    if not changed:
        return segment
    return " ".join(shlex.quote(t) if " " in t else t for t in tokens[i:])


_NUMBER = re.compile(r"^-?\d+(\.\d+)?[smhd]?$")
_ENV_ASSIGN_TOKEN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


# Глобальные флаги git, забирающие СЛЕДУЮЩЕЕ слово как значение. Слипшаяся
# форма (`--git-dir=…`) значения не забирает и уходит общей веткой «токен
# начинается с дефиса».
_GIT_GLOBAL_WITH_VALUE = frozenset({
    "-C", "-c", "--git-dir", "--work-tree", "--namespace",
    "--exec-path", "--config-env", "--super-prefix",
})


def _git_canonical(segment: str) -> str:
    """Вызов git без глобальных флагов: `git -C sub commit -m x` → `git commit -m x`.

    Правила смотрят на подкоманду, а между `git` и подкомандой законно стоит
    сколько угодно глобальных флагов. Проверено фактом 19.08.2026: правило
    `\\bgit\\s+commit\\b` ловило `git commit` и пропускало `git -C ПОДКАТАЛОГ
    commit` — то есть не работало в большинстве случаев, потому что в
    экосистеме из пятнадцати под-репозиториев коммитят как раз через `-C`.

    Возвращает исходный сегмент, если это не git или флагов перед подкомандой
    нет: тогда правилам и показывать нечего, кроме оригинала.
    """
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return segment  # незакрытая кавычка: разобрать нечем
    if not tokens or os.path.basename(tokens[0]).lower() not in ("git", "git.exe"):
        return segment

    i = 1
    while i < len(tokens) and tokens[i].startswith("-"):
        flag = tokens[i]
        i += 1
        if flag in _GIT_GLOBAL_WITH_VALUE and i < len(tokens):
            i += 1
    if i == 1:
        return segment
    rest = [shlex.quote(t) if " " in t else t for t in tokens[i:]]
    return " ".join(["git"] + rest)


# Служебные слова оболочки, за которыми идёт КОМАНДА. Без их снятия правила,
# закреплённые на начало сегмента, не срабатывают: `_SPLIT` режет
# `if true; then git reset --hard; fi` на куски, и опасный кусок начинается со
# слова `then`, а не с `git`. Проверено запуском 29.08.2026 — проходило.
#
# Закрепление на начало не ошибка и снимать его нельзя: без него гард ловил бы
# любое УПОМИНАНИЕ команды — в heredoc, в grep-шаблоне, в тексте плана. Чинить
# надо позицию команды, а не якорь.
_KEYWORDS = frozenset({
    "then", "do", "else", "elif", "if", "while", "until", "!", "{", "(",
})

# Обёртки, отдающие остаток строки другой команде. Значение — сколько слов
# обёртка съедает сама, прежде чем начнётся команда.
_RUNNERS = {"xargs": 0, "ssh": 1}


def _wrapped_commands(segment: str):
    """Команды, которые сегмент запускает не как оболочка, а как обёртка.

    `xargs git reset --hard`, `find . -exec git reset --hard {} +`,
    `ssh host git reset --hard`, `git submodule foreach 'git reset --hard'` —
    во всех четырёх опасная команда стоит в позиции команды, только не в
    начале сегмента. Все четыре проходили мимо гарда до 29.08.2026.
    """
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return
    if not tokens:
        return
    base = os.path.basename(tokens[0]).lower()

    # find … -exec КОМАНДА … \; | +
    if base == "find":
        i = 1
        while i < len(tokens):
            if tokens[i] in ("-exec", "-execdir", "-ok", "-okdir"):
                хвост = []
                i += 1
                while i < len(tokens) and tokens[i] not in (";", "\\;", "+"):
                    хвост.append(tokens[i])
                    i += 1
                if хвост:
                    # `{}` НЕ выбрасываем: это подстановка имени файла, то есть
                    # настоящий аргумент. Без него `git checkout -- {}`
                    # вырождается в `git checkout --`, и правило, которому нужен
                    # аргумент после дефисов, перестаёт срабатывать.
                    yield " ".join(хвост)
            i += 1
        return

    # git submodule foreach 'КОМАНДА'
    if base in ("git", "git.exe") and len(tokens) >= 4 \
            and tokens[1] == "submodule" and tokens[2] == "foreach":
        for token in tokens[3:]:
            if not token.startswith("-"):
                yield token
        return

    if base not in _RUNNERS:
        return
    # Снимаем флаги обёртки и её собственные слова (у ssh это адрес хоста).
    съесть = _RUNNERS[base]
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("-"):
            i += 1
            if token in _FLAG_TAKES_VALUE and i < len(tokens):
                i += 1
            continue
        if съесть:
            съесть -= 1
            i += 1
            continue
        break
    if i < len(tokens):
        yield " ".join(tokens[i:])


def command_segments(command: str, depth: int = 0):
    """Куски строки, каждый из которых стоит в позиции команды.

    Без этого гард ловит любое УПОМИНАНИЕ опасной команды — внутри heredoc,
    grep-паттерна или текста документации, — а не её запуск.

    Спускаемся и внутрь `bash -c '…'`: полезная нагрузка оболочки — такая же
    позиция команды, просто уровнем ниже. Туда же относятся обёртки вроде
    `xargs` и `find -exec`.
    """
    # Оба разреза сразу, и это не перестраховка. Разрез с учётом кавычек
    # находит то, что наивный терял; наивный находит то, что теряет первый на
    # незакрытой кавычке. Повторы безвредны: проверить кусок дважды ничего не
    # стоит, а потерять его — стоит команды, которая прошла мимо.
    видели: set[str] = set()
    for segment in list(_split_respecting_quotes(command)) + _SPLIT.split(command):
        segment = segment.strip()
        while True:
            # Регэкспы оставлены как запасной путь: сегмент с незакрытой
            # кавычкой shlex не разбирает, и тогда снимаем что можем.
            stripped = _ENV_ASSIGN.sub("", segment)
            stripped = _strip_prefixes(stripped)
            if stripped == segment:
                # shlex не справился (незакрытая кавычка) — снимаем регэкспом
                # то, что поддаётся, вместо того чтобы пропустить сегмент.
                stripped = _PREFIX.sub("", stripped)
            # Служебное слово оболочки перед командой.
            первое, _, остаток = stripped.partition(" ")
            if первое in _KEYWORDS and остаток.strip():
                stripped = остаток.strip()
            # ANSI-C-кавычки: `bash -c $'git reset --hard'` shlex отдаёт как
            # `$git reset --hard`, и доллар сбивал закрепление на начало.
            if stripped.startswith("$") and len(stripped) > 1 and stripped[1].isalpha():
                stripped = stripped[1:]
            if stripped == segment:
                break
            segment = stripped
        if not segment or segment in видели:
            continue
        видели.add(segment)
        yield segment
        if depth < _MAX_SHELL_DEPTH:
            for payload in _shell_payloads(segment):
                yield from command_segments(payload, depth + 1)
            for wrapped in _wrapped_commands(segment):
                yield from command_segments(wrapped, depth + 1)


def _scan_for_user_message(text: str, whole_file: bool) -> str:
    """Последнее сообщение владельца в куске транскрипта, или пустая строка."""
    lines = text.splitlines()
    if lines and not whole_file:
        # Первая строка куска почти наверняка обрезана посередине.
        lines = lines[1:]
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict) or event.get("type") != "user":
            continue
        content = (event.get("message") or {}).get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [
                b["text"] for b in content
                if isinstance(b, dict) and isinstance(b.get("text"), str)
            ]
            if parts:
                return "\n".join(parts)
    return ""


def _last_user_message(transcript_path: str) -> str:
    """Текст последнего сообщения владельца из JSONL-транскрипта.

    Читаем ХВОСТ, но растущий, а не один кусок фиксированного размера.

    Так было до 29.08.2026: читались последние 64 КиБ, и если сообщения
    владельца там не оказывалось, функция возвращала пустую строку, а
    `_owner_consented` трактовал пустоту как согласие. То есть в длинной
    сессии проверка согласия молча превращалась в «разрешено» — ровно там,
    где она нужнее всего.

    Замер в тот день по 968 живым стенограммам: в 122 из них (13%) последнее
    сообщение владельца лежало ЗА окном в 64 КиБ. В сессии, где это нашли, —
    в 773 КиБ от конца.

    Поэтому окно удваивается, пока сообщение не найдётся или файл не
    кончится. Цена приемлема: функция вызывается только когда в команде
    стоит маркер, то есть на коммитах и пушах, а не на каждом вызове Bash.
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return ""
    try:
        size = os.path.getsize(transcript_path)
    except OSError:
        return ""

    window = _TRANSCRIPT_TAIL_BYTES
    while True:
        try:
            with open(transcript_path, "rb") as f:
                f.seek(max(0, size - window))
                blob = f.read()
        except OSError:
            return ""
        text = blob.decode("utf-8", errors="replace")
        found = _scan_for_user_message(text, whole_file=window >= size)
        if found:
            return found
        if window >= size or window >= _TRANSCRIPT_MAX_BYTES:
            return ""
        window = min(window * 4, size, _TRANSCRIPT_MAX_BYTES)


def _last_match(rx: re.Pattern, text: str):
    """Последнее совпадение регэкспа в тексте, или None."""
    last = None
    for m in rx.finditer(text):
        last = m
    return last


def _owner_consented(payload: dict) -> tuple[bool, str]:
    """Разрешал ли владелец коммит ПОСЛЕДНИМ своим сообщением.

    Возвращает (разрешено, пояснение). Без транскрипта проверить нечем —
    тогда доверяем маркеру: гард, который блокирует работу из-за собственной
    слепоты, отключат первым же, и защиты не останется вовсе.
    """
    text = _last_user_message(payload.get("transcript_path", ""))
    if not text:
        return True, ""

    consent = _last_match(_CONSENT, text)
    if consent is None:
        return False, "the owner's last message carries no consent to commit"

    # Решает ПОСЛЕДНЕЕ совпадение, а не сам факт отказа где-то в сообщении.
    # Проверено фактом 19.08.2026: «дорезать не надо» относилось к роли в
    # таблице проектов, а заблокировало коммит в другом репозитории. Для
    # рабочей сессии владелец — её надзиратель, и одно случайное «не надо»
    # в любом его сообщении гасило ей все коммиты.
    #
    # Перекрытие отдаём отказу: в «нет, не коммить» согласие («коммить») —
    # часть самого отказа, а не отдельное разрешение. Поэтому согласие
    # побеждает, только если начинается ПОСЛЕ конца отказа.
    refusal = _last_match(_REFUSAL, text)
    if refusal is not None and consent.start() < refusal.end():
        return False, "in the owner's last message the refusal comes after the consent"
    return True, ""


def _marker_in_command_position(command: str) -> bool:
    """Стоит ли `OWNER_OK=1` присваиванием ПЕРЕД командой, а не где попало.

    До 29.08.2026 проверялось простым вхождением в строку, и маркером
    засчитывались `git commit -m "OWNER_OK=1"` и `echo OWNER_OK=1 && git
    commit -m x`. Оба проверены запуском: проходили. Маркер должен стоять там,
    где его ставит оболочка, — в начале сегмента.
    """
    for raw in _SPLIT.split(command):
        raw = raw.strip()
        if raw == OWNER_MARKER or raw.startswith(OWNER_MARKER + " ") \
                or raw.startswith(OWNER_MARKER + "\t"):
            return True
    return False


def _pipes_into_shell(segments) -> bool:
    """Есть ли в строке голый вызов оболочки — приёмник конвейера.

    `echo 'git reset --hard' | bash` разбирается на два сегмента, и опасная
    команда лежит в первом кавыченной строкой, то есть НЕ в позиции команды.
    Увидеть её можно только по тому, что второй сегмент — оболочка без
    аргументов. Проверено запуском 29.08.2026: проходило.
    """
    for segment in segments:
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue
        if len(tokens) == 1 and os.path.basename(tokens[0]).lower() in _SHELLS:
            return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if payload.get("tool_name") not in ("Bash", "PowerShell"):
        return 0

    command = (payload.get("tool_input") or {}).get("command", "")
    if not command:
        return 0

    # Пара «как написано» → «канонический вид». Правила смотрят на второй, а в
    # сообщении показываем первый: подсказка «повтори с OWNER_OK=1» без
    # `-C ПОДКАТАЛОГ` увела бы коммит не в тот репозиторий.
    segments = [(seg, _git_canonical(seg)) for seg in command_segments(command)]

    for segment, probe in segments:
        for pattern, reason in HARD_BLOCK:
            if re.match(pattern, probe):
                sys.stderr.write(
                    f"BLOCKED (destructive to the working tree).\n\n{reason}\n\n"
                    f"Command: {segment[:200]}\n"
                    "Do not get round the guard by rewriting the command — tell the "
                    "owner and offer a safe way."
                )
                return 2
        for проверка, reason in HARD_BLOCK_FUNCS:
            if проверка(probe):
                sys.stderr.write(
                    f"BLOCKED (destructive to the working tree).\n\n{reason}\n\n"
                    f"Command: {segment[:200]}\n"
                    "Do not get round the guard by rewriting the command — tell the "
                    "owner and offer a safe way."
                )
                return 2

    for pattern, reason in HARD_BLOCK_WHOLE:
        if re.search(pattern, command):
            sys.stderr.write(
                f"BLOCKED (destructive to the working tree).\n\n{reason}\n\n"
                f"Command: {command[:200]}\n"
                "Do not get round the guard by rewriting the command — tell the "
                "owner and offer a safe way."
            )
            return 2

    # Конвейер в оболочку: опасное лежит кавыченной строкой в предыдущем
    # сегменте, и позиции команды у него нет. Тогда — и только тогда —
    # смотрим всю строку целиком, поиском, а не закреплением на начало.
    if _pipes_into_shell(seg for seg, _ in segments):
        for pattern, reason in HARD_BLOCK:
            if re.search(pattern, command):
                sys.stderr.write(
                    f"BLOCKED (destructive to the working tree).\n\n{reason}\n\n"
                    f"Command: {command[:200]}\n\n"
                    "The dangerous part is a quoted string piped into a shell, which "
                    "runs it. Rewriting it as a pipeline does not make it safe."
                )
                return 2

    has_marker = _marker_in_command_position(command)
    consented, why_not = _owner_consented(payload) if has_marker else (False, "")

    if not (has_marker and consented):
        for segment, probe in segments:
            for pattern, reason in NEEDS_OWNER:
                if re.match(pattern, probe):
                    if has_marker:
                        # Маркер стоит, а согласия нет: агент разрешил сам себе.
                        # Именно этот случай маркер в команде поймать не мог —
                        # его пишет тот же, кого он должен ограничивать.
                        sys.stderr.write(
                            f"BLOCKED: {why_not}.\n\n{reason}\n\n"
                            f"Command: {segment[:200]}\n\n"
                            f"The {OWNER_MARKER} marker shows your intent, but the "
                            f"permission is the owner's — a word in the chat. Ask and wait."
                        )
                    else:
                        sys.stderr.write(
                            f"REQUIRES THE OWNER'S PERMISSION.\n\n{reason}\n\n"
                            f"Command: {segment[:200]}\n\n"
                            f"Ask the owner. After an explicit «yes» repeat it "
                            f"with the {OWNER_MARKER} prefix:\n"
                            f"  {OWNER_MARKER} {segment[:120]}"
                        )
                    return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
