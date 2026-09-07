#!/usr/bin/env python3
"""Тесты гарда деструктивных команд."""
import json
import os
import subprocess
import tempfile
import sys

# путь берём от самого теста — файл работает и в комплекте, и после установки
HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard-destructive.py")

BLOCK = True
PASS = False

CASES = [
    # --- должно блокироваться: реальный запуск ---
    ("git checkout -- build-mods.sh", BLOCK),
    ("git checkout .", BLOCK),
    ("git reset --hard origin/main", BLOCK),
    ("git clean -fd", BLOCK),
    ("git restore internal/api/server.go", BLOCK),
    ("git restore --worktree --staged x.go", BLOCK),
    ("git stash", BLOCK),
    ("git stash pop", BLOCK),
    ("git branch -D feature/x", BLOCK),
    ("cd /tmp && rm -rf ~", BLOCK),
    ("rm -rf ~/", BLOCK),
    ("rm -rf /", BLOCK),
    ("rm -rf $HOME", BLOCK),
    ("rm -rf .git", BLOCK),
    ("rm -rf .git/objects", BLOCK),
    ("rm .git/config", BLOCK),
    # .git/hooks истории не содержит: удаление уведомлялки историю не трогает,
    # а запрет мешал убрать хук по прямому распоряжению владельца (19.08.2026).
    ("rm .git/hooks/post-commit", PASS),
    ("rm -f .git/hooks/post-commit", PASS),
    ("rm .git/hooks/tausozavr-notify", PASS),
    # pre-commit — рубеж сборки и тестов, снятие = сессия отключает надзор.
    ("rm .git/hooks/pre-commit", BLOCK),
    ("rm -f DmTrading/.git/hooks/pre-commit", BLOCK),
    # каталог хуков целиком и по маске уносит рубеж вместе с уведомлялками
    ("rm -rf .git/hooks", BLOCK),
    ("rm -rf .git/hooks/", BLOCK),
    ("rm -rf .git/hooks/*", BLOCK),

    # --- подпути внутри дома: обычная работа, блокировать нельзя ---
    ("rm -rf ~/.claude/skills.new", PASS),
    ("rm -rf ~/.cache/go-build", PASS),
    ("rm -rf $HOME/tmp/scratch", PASS),
    ("rm -rf /tmp/claude-test", PASS),
    ("rm -rf /root/SyncedProjects/x/build", PASS),
    ("sudo -A git reset --hard", BLOCK),
    ("go build ./... && git reset --hard", BLOCK),

    # --- спуск внутрь оболочки (проверено фактом 15.08.2026: без него
    #     эти пять команд проходили сквозь гард) ---
    ("bash -c 'git reset --hard'", BLOCK),
    ("sh -c \"git stash\"", BLOCK),
    ("env bash -c 'git checkout -- x.go'", BLOCK),
    ("timeout 5 bash -c 'git clean -fd'", BLOCK),
    ("timeout 30s bash -c 'git stash'", BLOCK),
    ("nice -n 10 bash -c 'git reset --hard'", BLOCK),
    ("ionice -c2 -n7 bash -c 'git stash'", BLOCK),
    ("sudo -u root bash -c 'git checkout -- x'", BLOCK),
    ("env FOO=1 bash -c 'git stash'", BLOCK),
    ("bash -lc 'git branch -D main'", BLOCK),
    ("zsh -c 'git clean -fd'", BLOCK),
    # вложенность в два уровня
    ("bash -c \"sh -c 'git reset --hard'\"", BLOCK),

    # --- оболочка сама по себе не повод блокировать ---
    ("bash -c 'ls -la'", PASS),
    ("bash -c 'go build ./...'", PASS),
    ("timeout 5 ls", PASS),
    ("nice bash -c 'echo привет'", PASS),
    # упоминание, а не запуск
    ("echo bash -c git", PASS),
    ("grep -r 'bash -c git stash' docs/", PASS),

    # --- должно проходить: безопасные варианты тех же команд ---
    ("git checkout -b feature/new", PASS),
    ("git checkout main", PASS),
    ("git restore --staged internal/api/server.go", PASS),
    ("git stash list", PASS),
    ("git stash show -p", PASS),
    ("git reset --soft HEAD~1", PASS),
    ("git status", PASS),
    ("git diff HEAD", PASS),
    ("git log --oneline -5", PASS),
    ("git add internal/api/server.go", PASS),
    ("git branch -d merged-feature", PASS),

    # --- должно проходить: рабочие команды экосистемы ---
    ("cd DmTrading && go build ./cmd/bot && go vet ./...", PASS),
    ("rm -rf build/core", PASS),
    ("rm /tmp/x.json", PASS),
    ("bash tools/build-mod.sh core", PASS),
    # 01.09.2026: было PASS. `pkill -f "exe/bot"` уложил всех ботов экосистемы,
    # и владелец запретил pkill целиком — безопасной формы у него нет, число
    # совпадений видно только после убийства. Штатная остановка вместо него.
    ('ssh -i "$KEY" "$VPS" "pkill -x csgomarket-bot"', BLOCK),
    ('pkill -f "exe/bot"', BLOCK),
    ("pkill bot", BLOCK),
    ("killall bot", BLOCK),
    ("kill -9 12345", BLOCK),
    ("kill -s SIGKILL 12345", BLOCK),
    ("kill $(pgrep -f bot)", BLOCK),
    ("pgrep -a bot", PASS),
    ("kill 12345", PASS),
    ("systemctl --user stop buyorderbot", PASS),

    # --- ключевое: УПОМИНАНИЕ команды, а не запуск ---
    ("grep -rn 'git reset --hard' docs/", PASS),
    ("echo 'никогда не делай git checkout -- файл'", PASS),
    ("rg --files-with-matches 'git stash' .", PASS),
    ("python3 -c \"print('git clean -fd')\"", PASS),

    # --- разрешение владельца ---
    ('git commit -m "feat: скоринг"', BLOCK),
    ('OWNER_OK=1 git commit -m "feat: скоринг"', PASS),
    ("git push origin main", BLOCK),
    ("OWNER_OK=1 git push origin main", PASS),

    # --- глобальные флаги git до подкоманды (проверено фактом 19.08.2026:
    #     шесть коммитов через `-C` прошли молча, седьмой в корне встал) ---
    ("git -C DmTrading commit -m x", BLOCK),
    ('OWNER_OK=1 git -C DmTrading commit -m "feat: x"', PASS),
    ("git -C DmTrading push origin main", BLOCK),
    ("git --git-dir=DmTrading/.git --work-tree=DmTrading commit -m x", BLOCK),
    ("git -c user.name=x commit -m y", BLOCK),
    ("git --no-pager -C DmTrading commit -m z", BLOCK),
    ("git -C DmTrading push --force origin main", BLOCK),
    ("git -C DmTrading stash", BLOCK),
    ("git -C DmTrading reset --hard", BLOCK),
    # безопасные подкоманды через -C остаются безопасными
    ("git -C DmTrading status", PASS),
    ("git -C DmTrading log --oneline -5", PASS),
    ("git -C DmTrading add internal/api/server.go", PASS),

    # --- ДЫРЫ, НАЙДЕННЫЕ 29.08.2026 ------------------------------------------
    # Все проверены запуском ДО правки: каждая проходила мимо гарда.
    # Находки agent security-reviewer и плагина claude-security, подтверждены
    # прогоном `/tmp/cc-research/guard-bypass.py` — 13 предсказаний из 13.

    # Служебное слово оболочки перед командой сбивало закрепление на начало.
    ("if true; then git reset --hard; fi", BLOCK),
    ("for f in a b; do git checkout -- $f; done", BLOCK),
    ("while read f; do git clean -fd; done", BLOCK),
    ("if [ -f x ]; then git stash; fi", BLOCK),

    # ANSI-C-кавычки: shlex отдаёт payload как `$git reset --hard`.
    ("bash -c $'git reset --hard'", BLOCK),

    # Обёртки, запускающие чужую команду.
    ("find . -name '*.go' -exec git checkout -- {} +", BLOCK),
    ("echo . | xargs git reset --hard", BLOCK),
    ("xargs git reset --hard", BLOCK),
    ("git submodule foreach 'git reset --hard'", BLOCK),

    # Конвейер в оболочку и строка-здесь.
    ("echo 'git reset --hard' | bash", BLOCK),
    ("bash <<< 'git reset --hard'", BLOCK),

    # `git checkout` с ссылкой перед дефисами и с силой.
    ("git checkout HEAD -- src/x.py", BLOCK),
    ("git checkout HEAD~1 -- .", BLOCK),
    ("git checkout -f master", BLOCK),
    ("git checkout --force develop", BLOCK),
    ("git checkout-index -f -a", BLOCK),
    # Смена ветки и создание ветки правки не трогают — должны проходить.
    ("git checkout -b feature/new", PASS),
    ("git checkout master", PASS),
    ("git checkout develop", PASS),

    # `git rm` силой уносит файл вместе с правками.
    ("git rm -rf .", BLOCK),
    ("git rm -f internal/api/server.go", BLOCK),
    ("git rm --force x.go", BLOCK),
    # Без силы git откажется сам — блокировать нечего.
    ("git rm --cached x.go", PASS),

    # `rm` с раздельными и длинными флагами.
    ("rm -r -f /", BLOCK),
    ("rm -f -r ~", BLOCK),
    ("rm --recursive --force ~", BLOCK),
    ("rm -rf \"/\"", BLOCK),
    ("rm -r -f $HOME", BLOCK),
    # Подпути внутри дома остаются законными и при раздельных флагах.
    ("rm -r -f ~/.cache/go-build", PASS),
    ("rm --recursive --force /tmp/scratch", PASS),

    # Уничтожение файлов мимо `rm`.
    ("find . -name '*.go' -delete", BLOCK),
    ("truncate -s 0 internal/api/server.go", BLOCK),
    ("python3 -c \"import shutil; shutil.rmtree('.')\"", BLOCK),
    ("perl -e 'unlink glob \"*.go\"'", BLOCK),
    ("node -e \"require('fs')\" && python3 -c 'shutil.rmtree(\"x\")'", BLOCK),
    # Чтение про эти же вызовы — не удаление, и блокировать его нельзя.
    ("grep -rn shutil.rmtree .", PASS),
    ("rg 'unlink glob' tools/", PASS),
    ("cat notes.md", PASS),
    # Обычный find без -delete не трогаем.
    ("find . -name '*.go' -type f", PASS),
    ("truncate -s 100 x.bin", PASS),

    # Метасимвол ВНУТРИ кавычек не должен разваливать разбор. Найдено
    # 29.08.2026 прогоном, уже ПОСЛЕ первой правки гарда: наивный разрез рвал
    # `bash -c 'git reset --hard "x|y"'` пополам, у обоих кусков кавычка
    # оставалась непарной, shlex спотыкался, и спуска внутрь оболочки не было.
    ("bash -c 'git reset --hard \"x|y\"'", BLOCK),
    ("bash -c 'git clean -fd \"a|b\"'", BLOCK),
    ("bash -c 'git stash; echo a|b'", BLOCK),
    ("git reset --hard 'a|b'", BLOCK),
    ("git checkout -- 'a|b'", BLOCK),
    ("rm -rf '/'", BLOCK),
    ("git commit -m 'a|b'", BLOCK),
    ("git commit -m 'fix (parser)'", BLOCK),
    # Законная работа с теми же символами проходить обязана.
    ("go test ./... 2>&1 | tail -5", PASS),
    ("grep -rn 'a|b' trah-setup/", PASS),
    ("echo 'git reset --hard' >> notes.md", PASS),

    # Маркер согласия должен стоять в позиции команды, а не где угодно.
    ('git commit -m "OWNER_OK=1"', BLOCK),
    ("echo OWNER_OK=1 && git commit -m x", BLOCK),
    ('git commit -m "фикс OWNER_OK=1 в тексте"', BLOCK),
]


def run(cmd: str, transcript_path: str = "") -> bool:
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}}
    if transcript_path:
        payload["transcript_path"] = transcript_path
    proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    return proc.returncode == 2


def transcript_with(text: str, padding_bytes: int = 0) -> str:
    """Транскрипт с сообщением владельца и, если просили, хвостом после него.

    `padding_bytes` дописывает после сообщения записи агента, отодвигая его от
    конца файла. Ради этого параметр и существует: до 29.08.2026 гард читал
    последние 64 КиБ и, не найдя владельца там, считал согласие ДАННЫМ. Замер
    по 968 живым стенограммам: в 13% из них последнее сообщение владельца
    лежало дальше, а в одной — в 773 КиБ от конца. То есть проверка молча
    выключалась ровно в длинных сессиях.
    """
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user", "message": {"content": text}}) + "\n")
        written = 0
        i = 0
        while written < padding_bytes:
            line = json.dumps({
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": f"шаг {i} " + "x" * 200}]},
            }) + "\n"
            f.write(line)
            written += len(line.encode("utf-8"))
            i += 1
    return path


# Маркер в команде пишет сам агент, поэтому он показывает намерение, но не
# доказывает разрешение. Второе условие — согласие в последнем сообщении
# владельца; без него агент разрешал бы себе сам.
CONSENT_CASES = [
    ("OWNER_OK=1 git commit -m x", "да, коммить", PASS),
    ("OWNER_OK=1 git commit -m x", "ок, давай", PASS),
    ("OWNER_OK=1 git push origin main", "закоммить и запушь", PASS),
    ("OWNER_OK=1 git commit -m x", "посмотри что в плане", BLOCK),
    ("OWNER_OK=1 git commit -m x", "нет, не коммить пока", BLOCK),
    ("OWNER_OK=1 git commit -m x", "стоп", BLOCK),
    # Без маркера блокируется даже при согласии: маркер остаётся признаком
    # осознанного действия, а не формальностью.
    ("git commit -m x", "да, коммить", BLOCK),
    # Безопасные команды проверка согласия не трогает вовсе.
    ("git status", "посмотри что в плане", PASS),

    # Решает ПОСЛЕДНЕЕ совпадение. Живой случай 19.08.2026: «дорезать не надо»
    # относилось к роли в таблице проектов, а блокировало коммит в другом
    # репозитории — одно случайное «не надо» гасило сессии все коммиты.
    ("OWNER_OK=1 git commit -m x",
     "дорезать не надо — это роль. коммить asynchronus", PASS),
    ("OWNER_OK=1 git commit -m x", "коммить, хотя нет, не надо", BLOCK),
    ("OWNER_OK=1 git commit -m x", "не надо коммить", BLOCK),

    # Словарь согласия: владелец сказал «можно можно», гард не засчитал.
    ("OWNER_OK=1 git commit -m x", "можно можно", PASS),
    ("OWNER_OK=1 git commit -m x", "разрешаю", PASS),
    ("OWNER_OK=1 git commit -m x", "согласен", PASS),
    ("OWNER_OK=1 git commit -m x", "approve", PASS),

    # Согласие требуется и для коммита через -C, как для обычного.
    ("git -C DmTrading commit -m x", "да, коммить", BLOCK),
    ("OWNER_OK=1 git -C DmTrading commit -m x", "да, коммить", PASS),
    ("OWNER_OK=1 git -C DmTrading commit -m x", "посмотри что в плане", BLOCK),
]


def main() -> int:
    failed = 0
    for cmd, want in CASES:
        got = run(cmd)
        ok = got == want
        failed += not ok
        mark = "✓" if ok else "✗"
        state = "БЛОК" if got else "ok  "
        print(f"{mark} {state}  {cmd[:64]}")

    print("\n--- согласие владельца из его последнего сообщения ---")
    for cmd, said, want in CONSENT_CASES:
        path = transcript_with(said)
        try:
            got = run(cmd, path)
        finally:
            os.unlink(path)
        ok = got == want
        failed += not ok
        mark = "✓" if ok else "✗"
        state = "БЛОК" if got else "ok  "
        print(f"{mark} {state}  {cmd[:34]:36} ← «{said}»")

    # --- САМОЕ ВАЖНОЕ: согласие не теряется в длинной сессии ---------------
    #
    # Гард читает хвост транскрипта. Пока окно было одно и фиксированное
    # (64 КиБ), сообщение владельца в длинной сессии оказывалось за ним, а
    # пустой результат трактовался как согласие. Здесь сообщение намеренно
    # отодвигается всё дальше, и на каждой дистанции проверяются ОБА исхода:
    # согласие засчитано, отказ засчитан. Если окно снова станет
    # фиксированным, второй столбец провалится.
    print("\n--- согласие на расстоянии от конца транскрипта ---")
    for padding in (0, 200 * 1024, 1024 * 1024, 3 * 1024 * 1024):
        for said, want, why in (
            ("да, коммить", PASS, "согласие"),
            ("посмотри что в плане", BLOCK, "согласия нет"),
        ):
            path = transcript_with(said, padding_bytes=padding)
            try:
                got = run("OWNER_OK=1 git commit -m x", path)
            finally:
                os.unlink(path)
            ok = got == want
            failed += not ok
            mark = "✓" if ok else "✗"
            state = "БЛОК" if got else "ok  "
            print(f"{mark} {state}  хвост {padding // 1024:>5} КиБ   {why}")

    total = len(CASES) + len(CONSENT_CASES) + 8
    print(f"\nвсего: {total}   провалов: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
