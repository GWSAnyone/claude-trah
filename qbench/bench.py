#!/usr/bin/env python3
"""qbench — стенд для замера ПРИВЫЧЕК модели при правке кода.

Не «хорош ли код» на глаз, а наблюдаемые бинарные факты из стенограммы и
из git-диффа: смотрела ли модель соседей до первой записи, переиспользовала
ли существующий helper или написала свой, куда положила код, гоняла ли
проверки проекта, добавила ли тест, прошли ли ruff и pytest после неё.

    bench.py make  <run_dir> [--brief FILE]   разложить эталон, закоммитить
    bench.py run   <run_dir> [--tag T]        прогнать claude -p, сохранить
    bench.py analyse <run_dir>                строка наблюдений (json)
    bench.py table <run_dir>...               сводная таблица

Эталон: пакет shop с utils.parse_price / fmt_money, Inventory с Item, отчёт,
pytest-тесты, ruff в pyproject. Задача: посчитать общую стоимость инвентаря.
Сеньор переиспользует parse_price, кладёт в inventory.py, читает README,
гоняет ruff+pytest, пишет тест в стиле tests/.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent
VENV = Path(os.environ.get("QBENCH_VENV", str(КОРЕНЬ / "venv")))

ЗАДАЧА = (
    "Добавь в пакет shop подсчёт общей стоимости инвентаря: сумма цена × "
    "количество по всем предметам. Цены у предметов хранятся строкой в том "
    "виде, в каком пришли из фида поставщика. Положи код туда, где ему место, "
    "и покрой тестом."
)

ФАЙЛЫ = {
"shop/__init__.py": "",
"shop/utils.py": '''"""Money helpers shared by the shop package."""
from decimal import Decimal, InvalidOperation

_CURRENCY = "$"


def parse_price(text: str) -> Decimal:
    """Turn a supplier price string like ``"$1,234.56"`` into a Decimal.

    Accepts an optional leading currency sign and thousands separators.
    Raises ValueError on anything else.
    """
    cleaned = text.strip()
    if cleaned.startswith(_CURRENCY):
        cleaned = cleaned[len(_CURRENCY):]
    cleaned = cleaned.replace(",", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"bad price: {text!r}") from exc


def fmt_money(value: Decimal) -> str:
    """Format a Decimal as ``$1,234.56``."""
    return f"{_CURRENCY}{value:,.2f}"
''',
"shop/inventory.py": '''"""Inventory: the items the shop currently holds."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Item:
    name: str
    price_text: str  # as received from the supplier feed, e.g. "$1,234.56"
    qty: int


@dataclass
class Inventory:
    items: list[Item] = field(default_factory=list)

    def add(self, item: Item) -> None:
        self.items.append(item)

    def find(self, name: str) -> Item | None:
        for item in self.items:
            if item.name == name:
                return item
        return None

    def names(self) -> list[str]:
        return [item.name for item in self.items]
''',
"shop/report.py": '''"""Human-readable reports over an Inventory."""
from shop.inventory import Inventory
from shop.utils import fmt_money, parse_price


def price_list(inv: Inventory) -> str:
    lines = []
    for item in inv.items:
        price = fmt_money(parse_price(item.price_text))
        lines.append(f"{item.name:<20} {price:>12}  x{item.qty}")
    return "\\n".join(lines)
''',
"tests/__init__.py": "",
"tests/test_utils.py": '''from decimal import Decimal

import pytest

from shop.utils import fmt_money, parse_price


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$1,234.56", Decimal("1234.56")),
        ("12.00", Decimal("12.00")),
        ("  $0.99 ", Decimal("0.99")),
    ],
)
def test_parse_price_accepts_supplier_formats(text, expected):
    assert parse_price(text) == expected


def test_parse_price_rejects_garbage():
    with pytest.raises(ValueError):
        parse_price("free")


def test_fmt_money_groups_thousands():
    assert fmt_money(Decimal("1234.5")) == "$1,234.50"
''',
"tests/test_inventory.py": '''from shop.inventory import Inventory, Item


def make_inventory() -> Inventory:
    inv = Inventory()
    inv.add(Item("widget", "$10.00", 3))
    inv.add(Item("gadget", "$1,250.50", 1))
    return inv


def test_find_returns_item_by_name():
    inv = make_inventory()
    assert inv.find("gadget").qty == 1


def test_find_missing_is_none():
    assert make_inventory().find("nothing") is None


def test_names_keeps_insertion_order():
    assert make_inventory().names() == ["widget", "gadget"]
''',
"pyproject.toml": '''[project]
name = "shop"
version = "0.1.0"
requires-python = ">=3.12"

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
''',
"README.md": '''# shop

Small inventory toolkit.

## Layout

- `shop/utils.py` — money helpers shared by everything else
- `shop/inventory.py` — `Item` and `Inventory`
- `shop/report.py` — text reports over an inventory
- `tests/` — pytest

## Checks

    venv/bin/ruff check .
    venv/bin/pytest -q
''',
".gitignore": "venv\n__pycache__/\n.pytest_cache/\n.ruff_cache/\n.claude/\n",
}

ИНСТРУМЕНТЫ_ЗАПИСИ = {
    "Write", "Edit", "MultiEdit", "NotebookEdit",
    "mcp__serena__replace_symbol_body", "mcp__serena__replace_content",
    "mcp__serena__insert_after_symbol", "mcp__serena__insert_before_symbol",
    "mcp__serena__replace_in_files", "mcp__serena__create_text_file",
}
ИНСТРУМЕНТЫ_ВЗГЛЯДА = {
    "Read", "Glob", "Grep",
    "mcp__serena__get_symbols_overview", "mcp__serena__find_symbol",
    "mcp__serena__list_dir", "mcp__serena__search_for_pattern",
    "mcp__serena__find_file", "mcp__serena__find_referencing_symbols",
    "mcp__serena__read_file",
}


def sh(cmd: list[str], cwd: Path | None = None, env: dict | None = None,
       timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                          text=True, timeout=timeout)


# ── make ────────────────────────────────────────────────────────────────────

def make(run_dir: Path, brief: Path | None) -> None:
    repo = run_dir / "repo"
    if repo.exists():
        sys.exit(f"{repo} уже есть")
    for rel, text in ФАЙЛЫ.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    (repo / "venv").symlink_to(VENV)
    if brief is not None:
        d = repo / ".claude"
        d.mkdir()
        (d / "brief.md").write_text(brief.read_text(encoding="utf-8"),
                                    encoding="utf-8")
    sh(["git", "init", "-q"], cwd=repo)
    sh(["git", "add", "-A"], cwd=repo)
    sh(["git", "-c", "user.name=bench", "-c", "user.email=b@b",
        "commit", "-q", "-m", "baseline"], cwd=repo)
    print(f"эталон: {repo}" + (f"  (+brief {brief.name})" if brief else ""))


# ── run ─────────────────────────────────────────────────────────────────────

МОДЕЛЬ = os.environ.get("QBENCH_MODEL", "claude-opus-5")
УСИЛИЕ = os.environ.get("QBENCH_EFFORT", "")  # пусто — умолчание модели


def run(run_dir: Path, tag: str) -> None:
    repo = run_dir / "repo"
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("CLAUDECODE") and not k.startswith("CLAUDE_CODE_")}
    задача = (run_dir / "task.txt").read_text(encoding="utf-8").strip() \
        if (run_dir / "task.txt").exists() else ЗАДАЧА
    cmd = ["claude", "-p", задача, "--output-format", "json", "--model", МОДЕЛЬ,
           "--dangerously-skip-permissions", "--max-turns", "80"]
    if УСИЛИЕ:
        cmd += ["--effort", УСИЛИЕ]
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=repo, env=env, capture_output=True,
                          text=True, timeout=1500)
    dt = time.time() - t0
    (run_dir / "stdout.json").write_text(proc.stdout, encoding="utf-8")
    (run_dir / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
    (run_dir / "meta.json").write_text(json.dumps(
        {"tag": tag, "wall_s": round(dt, 1), "rc": proc.returncode,
         "model": МОДЕЛЬ, "effort": УСИЛИЕ or "default"}),
        encoding="utf-8")
    print(f"{tag}: rc={proc.returncode} за {dt:.0f} с [{МОДЕЛЬ} {УСИЛИЕ or 'default'}]")


# ── analyse ─────────────────────────────────────────────────────────────────

def _result(run_dir: Path) -> dict:
    raw = (run_dir / "stdout.json").read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    if isinstance(data, list):
        for rec in reversed(data):
            if isinstance(rec, dict) and rec.get("type") == "result":
                return rec
        return {}
    return data


def _transcript(repo: Path, session_id: str) -> Path | None:
    enc = str(repo.resolve()).replace("/", "-")
    p = Path.home() / ".claude" / "projects" / enc / f"{session_id}.jsonl"
    return p if p.exists() else None


def _tool_uses(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") != "assistant":
                continue
            content = (rec.get("message") or {}).get("content") or []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    out.append({"name": block.get("name", ""),
                                "input": json.dumps(block.get("input", {}),
                                                    ensure_ascii=False)})
    return out


def _mentions(s: str, *needles: str) -> bool:
    return any(n in s for n in needles)


def analyse(run_dir: Path) -> dict:
    repo = run_dir / "repo"
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    res = _result(run_dir)
    row = {"tag": meta["tag"], "wall_s": meta["wall_s"],
           "turns": res.get("num_turns"), "cost": res.get("total_cost_usd"),
           "error": bool(res.get("is_error"))}

    tr = _transcript(repo, res.get("session_id", ""))
    uses = _tool_uses(tr) if tr else []
    row["tool_uses"] = len(uses)
    first_write = next((i for i, u in enumerate(uses)
                        if u["name"] in ИНСТРУМЕНТЫ_ЗАПИСИ), None)
    before = uses[:first_write] if first_write is not None else uses
    looks = [u for u in before if u["name"] in ИНСТРУМЕНТЫ_ВЗГЛЯДА
             or (u["name"] == "Bash" and _mentions(u["input"], "ls ", "tree", "find "))]
    row["looked_shop"] = any(_mentions(u["input"], "shop") for u in looks)
    row["looked_utils"] = any(_mentions(u["input"], "utils") for u in looks)
    row["looked_tests"] = any(_mentions(u["input"], "tests") for u in looks)
    row["looked_readme"] = any(_mentions(u["input"], "README") for u in looks)
    bash_all = [u["input"] for u in uses if u["name"] == "Bash"]
    row["ran_ruff"] = any("ruff" in b for b in bash_all)
    row["ran_pytest"] = any("pytest" in b for b in bash_all)
    row["serena_edits"] = sum(1 for u in uses if u["name"] in ИНСТРУМЕНТЫ_ЗАПИСИ
                              and u["name"].startswith("mcp__serena"))
    row["builtin_edits"] = sum(1 for u in uses if u["name"] in ИНСТРУМЕНТЫ_ЗАПИСИ
                               and not u["name"].startswith("mcp__serena"))

    diff = sh(["git", "diff", "HEAD"], cwd=repo).stdout
    status = sh(["git", "status", "--porcelain"], cwd=repo).stdout
    changed = sorted({ln[3:].strip() for ln in status.splitlines() if ln.strip()})
    row["changed"] = changed
    added = [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    # новые файлы в diff HEAD не видны — дочитать их целиком
    for f in changed:
        p = repo / f
        if p.is_file() and f not in diff:
            added += p.read_text(encoding="utf-8", errors="replace").splitlines()
    non_utils = [ln for f in changed if f != "shop/utils.py" for ln in added]
    row["reused_parse_price"] = any(re.search(r"\bparse_price\(", ln) for ln in non_utils
                                    if "import" not in ln)
    row["own_parsing"] = any(re.search(r'(replace\(["\']\$|lstrip\(["\']\$|strip\(["\']\$|re\.sub|re\.compile|\[1:\]\.replace)', ln)
                             for ln in non_utils)
    row["placement"] = [f for f in changed if f.startswith("shop/")]
    row["test_added"] = any(f.startswith("tests/") for f in changed)
    row["new_files"] = [ln[3:] for ln in status.splitlines() if ln.startswith("??")]

    ruff = sh([str(VENV / "bin/ruff"), "check", "."], cwd=repo)
    row["ruff_clean"] = ruff.returncode == 0
    row["ruff_out"] = ruff.stdout.strip().splitlines()[-1:] if ruff.returncode else []
    pt = sh([str(VENV / "bin/pytest"), "-q"], cwd=repo, timeout=120)
    row["pytest_ok"] = pt.returncode == 0
    row["pytest_tail"] = pt.stdout.strip().splitlines()[-1:]
    return row


КОЛОНКИ = ["tag", "turns", "cost", "wall_s", "looked_shop", "looked_utils",
           "looked_readme", "reused_parse_price", "own_parsing", "ran_ruff",
           "ran_pytest", "test_added", "ruff_clean", "pytest_ok", "placement"]


def table(dirs: list[Path]) -> None:
    rows = [analyse(d) for d in dirs]
    print("\t".join(КОЛОНКИ))
    for r in rows:
        print("\t".join(_cell(r.get(k)) for k in КОЛОНКИ))
    print()
    for k in КОЛОНКИ[4:-1]:
        vals = [r.get(k) for r in rows if r.get(k) is not None]
        if vals:
            print(f"{k:<20} {sum(bool(v) for v in vals)}/{len(vals)}")


def _cell(v) -> str:
    if isinstance(v, bool):
        return "✓" if v else "·"
    if isinstance(v, float):
        return f"{v:.2f}"
    if isinstance(v, list):
        return ",".join(v)
    return str(v)


def main() -> int:
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    cmd = a[0]
    if cmd == "make":
        brief = Path(a[a.index("--brief") + 1]) if "--brief" in a else None
        make(Path(a[1]), brief)
    elif cmd == "run":
        tag = a[a.index("--tag") + 1] if "--tag" in a else Path(a[1]).name
        run(Path(a[1]), tag)
    elif cmd == "analyse":
        print(json.dumps(analyse(Path(a[1])), ensure_ascii=False, indent=1))
    elif cmd == "table":
        table([Path(p) for p in a[1:]])
    else:
        sys.exit(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
