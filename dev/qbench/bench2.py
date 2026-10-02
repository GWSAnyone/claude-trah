#!/usr/bin/env python3
"""qbench v2 — стенд с конвенциями, которые видны только из кода.

Репозиторий: пакет shop с реестром форматов отчёта (@register), своей
иерархией ошибок (ShopError → FeedError → PricingError), структурным логгером
(get_logger(__name__).info("event", **fields)), фикстурами в tests/conftest.py,
CHANGELOG с правилом «строка на каждое видимое изменение». README называет
часть конвенций, но рецепт добавления формата лежит ТОЛЬКО в докстринге
shop/reports/__init__.py — это проверка, читает ли модель соседей.

Задача: добавить формат json. Сеньор: новый модуль shop/reports/json_.py с
@register("json"), импорт в __init__, item.unit_price()/line_total()/inv.total()
вместо своего парсинга, логгер как у соседей, тест через фикстуру inventory,
строка в CHANGELOG, cli.py не тронут (choices берутся из реестра).

    bench2.py make <run_dir> [--brief FILE]
    bench2.py run  <run_dir> [--tag T]
    bench2.py analyse <run_dir>
    bench2.py table <run_dir>...
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench  # noqa: E402

ЗАДАЧА = (
    "Добавь формат отчёта json: `shop report --format json FEED` должен "
    "печатать массив объектов с полями name, unit_price (число), qty, total. "
    "Покрой тестами."
)

ФАЙЛЫ = {
"shop/__init__.py": "",
"shop/errors.py": '''"""Exception hierarchy.

Everything the package raises on purpose derives from ShopError, so the CLI
boundary catches one type and never a bare Exception.
"""


class ShopError(Exception):
    """Base for everything shop raises on purpose."""


class FeedError(ShopError):
    """The supplier feed handed us something we cannot use."""


class PricingError(FeedError):
    """A price string from the feed did not parse."""

    def __init__(self, item_name: str, raw: str) -> None:
        super().__init__(f"{item_name}: bad price {raw!r}")
        self.item_name = item_name
        self.raw = raw
''',
"shop/log.py": '''"""Structured logging.

Call ``get_logger(__name__)`` at module top. Log events as short snake_case
names with keyword fields — ``log.info("report_rendered", format="csv")`` —
never as formatted sentences, so the lines stay machine-readable.
"""
import json
import logging
import sys

_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger("shop")
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    _configured = True


class EventLogger:
    def __init__(self, name: str) -> None:
        _configure()
        self._log = logging.getLogger(name)

    def info(self, event: str, **fields: object) -> None:
        self._log.info(json.dumps({"event": event, **fields}, default=str))

    def warning(self, event: str, **fields: object) -> None:
        self._log.warning(json.dumps({"event": event, **fields}, default=str))


def get_logger(name: str) -> EventLogger:
    return EventLogger(name)
''',
"shop/utils.py": bench.ФАЙЛЫ["shop/utils.py"],
"shop/inventory.py": '''"""Inventory: the items the shop currently holds."""
from dataclasses import dataclass, field
from decimal import Decimal

from shop.errors import PricingError
from shop.utils import parse_price


@dataclass(frozen=True)
class Item:
    name: str
    price_text: str  # as received from the supplier feed, e.g. "$1,234.56"
    qty: int

    def unit_price(self) -> Decimal:
        try:
            return parse_price(self.price_text)
        except ValueError as exc:
            raise PricingError(self.name, self.price_text) from exc

    def line_total(self) -> Decimal:
        return self.unit_price() * self.qty


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

    def total(self) -> Decimal:
        return sum((item.line_total() for item in self.items), Decimal(0))
''',
"shop/feed.py": '''"""Supplier feed: one ``name;price;qty`` per line."""
from pathlib import Path

from shop.errors import FeedError
from shop.inventory import Inventory, Item
from shop.log import get_logger

log = get_logger(__name__)


def load_feed(path: str | Path) -> Inventory:
    inv = Inventory()
    text = Path(path).read_text(encoding="utf-8")
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(";")
        if len(parts) != 3:
            raise FeedError(f"{path}:{lineno}: expected name;price;qty, got {raw!r}")
        name, price, qty = (p.strip() for p in parts)
        try:
            inv.add(Item(name, price, int(qty)))
        except ValueError as exc:
            raise FeedError(f"{path}:{lineno}: bad quantity {qty!r}") from exc
    log.info("feed_loaded", path=str(path), items=len(inv.items))
    return inv
''',
"shop/reports/__init__.py": '''"""Report formats.

A format is a function ``Inventory -> str`` registered under a name.

Adding a format: create ``shop/reports/<name>.py``, decorate the function
with ``@register("<name>")`` and add the module to the import line at the
bottom of this file so the decorator runs. The CLI builds its ``--format``
choices from the registry, so nothing else needs touching.
"""
from collections.abc import Callable

from shop.inventory import Inventory

Renderer = Callable[[Inventory], str]
_REGISTRY: dict[str, Renderer] = {}


def register(name: str) -> Callable[[Renderer], Renderer]:
    def deco(fn: Renderer) -> Renderer:
        if name in _REGISTRY:
            raise ValueError(f"report format {name!r} registered twice")
        _REGISTRY[name] = fn
        return fn

    return deco


def formats() -> list[str]:
    return sorted(_REGISTRY)


def render(name: str, inv: Inventory) -> str:
    return _REGISTRY[name](inv)


# Built-in formats. Importing runs their @register; order is irrelevant.
from shop.reports import csv_, text  # noqa: E402,F401
''',
"shop/reports/text.py": '''"""Aligned text table — the default for a terminal."""
from shop.inventory import Inventory
from shop.log import get_logger
from shop.reports import register
from shop.utils import fmt_money

log = get_logger(__name__)


@register("text")
def render_text(inv: Inventory) -> str:
    lines = [f"{'item':<20} {'unit':>12} {'qty':>5} {'total':>12}"]
    for item in inv.items:
        lines.append(
            f"{item.name:<20} {fmt_money(item.unit_price()):>12} "
            f"{item.qty:>5} {fmt_money(item.line_total()):>12}"
        )
    lines.append(f"{'':<20} {'':>12} {'':>5} {fmt_money(inv.total()):>12}")
    log.info("report_rendered", format="text", items=len(inv.items))
    return "\\n".join(lines)
''',
"shop/reports/csv_.py": '''"""CSV with a header row; prices as plain decimals, no currency sign."""
import csv
import io

from shop.inventory import Inventory
from shop.log import get_logger
from shop.reports import register

log = get_logger(__name__)


@register("csv")
def render_csv(inv: Inventory) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\\n")
    writer.writerow(["name", "unit_price", "qty", "total"])
    for item in inv.items:
        writer.writerow([item.name, item.unit_price(), item.qty, item.line_total()])
    log.info("report_rendered", format="csv", items=len(inv.items))
    return buf.getvalue().rstrip("\\n")
''',
"shop/cli.py": '''"""Command line: ``shop report [--format NAME] FEED``."""
import argparse
import sys

from shop.errors import ShopError
from shop.feed import load_feed
from shop.log import get_logger
from shop.reports import formats, render

log = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="shop")
    sub = p.add_subparsers(dest="cmd", required=True)
    rep = sub.add_parser("report", help="render the inventory")
    rep.add_argument("feed", help="supplier feed, one 'name;price;qty' per line")
    rep.add_argument("--format", choices=formats(), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inv = load_feed(args.feed)
        sys.stdout.write(render(args.format, inv) + "\\n")
    except ShopError as exc:
        log.warning("command_failed", cmd=args.cmd, error=str(exc))
        sys.stderr.write(f"shop: {exc}\\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
"tests/__init__.py": "",
"tests/conftest.py": '''from pathlib import Path

import pytest

from shop.inventory import Inventory, Item


@pytest.fixture
def inventory() -> Inventory:
    inv = Inventory()
    inv.add(Item("widget", "$10.00", 3))
    inv.add(Item("gadget", "$1,250.50", 1))
    inv.add(Item("gizmo", "0.99", 10))
    return inv


@pytest.fixture
def bad_inventory() -> Inventory:
    inv = Inventory()
    inv.add(Item("widget", "$10.00", 3))
    inv.add(Item("mystery", "call us", 1))
    return inv


@pytest.fixture
def feed_file(tmp_path: Path) -> Path:
    p = tmp_path / "feed.txt"
    p.write_text("widget;$10.00;3\\ngadget;$1,250.50;1\\n# comment\\ngizmo;0.99;10\\n",
                 encoding="utf-8")
    return p
''',
"tests/test_utils.py": bench.ФАЙЛЫ["tests/test_utils.py"],
"tests/test_inventory.py": '''from decimal import Decimal

import pytest

from shop.errors import PricingError


def test_find_returns_item_by_name(inventory):
    assert inventory.find("gadget").qty == 1


def test_find_missing_is_none(inventory):
    assert inventory.find("nothing") is None


def test_line_total_multiplies(inventory):
    assert inventory.find("widget").line_total() == Decimal("30.00")


def test_total_sums_all_lines(inventory):
    assert inventory.total() == Decimal("1290.40")


def test_bad_price_is_a_pricing_error(bad_inventory):
    with pytest.raises(PricingError) as info:
        bad_inventory.total()
    assert info.value.item_name == "mystery"
''',
"tests/test_reports.py": '''import pytest

from shop.errors import PricingError
from shop.reports import formats, render


def test_registry_lists_builtin_formats():
    assert formats() == ["csv", "text"]


def test_text_has_header_rows_and_total(inventory):
    out = render("text", inventory).splitlines()
    assert out[0].split() == ["item", "unit", "qty", "total"]
    assert len(out) == 1 + 3 + 1
    assert out[-1].strip() == "$1,290.40"


def test_csv_has_header_and_plain_decimals(inventory):
    out = render("csv", inventory).splitlines()
    assert out[0] == "name,unit_price,qty,total"
    assert out[1] == "widget,10.00,3,30.00"


@pytest.mark.parametrize("name", ["text", "csv"])
def test_bad_price_propagates_as_pricing_error(name, bad_inventory):
    with pytest.raises(PricingError):
        render(name, bad_inventory)
''',
"tests/test_cli.py": '''from shop.cli import main


def test_report_default_is_text(feed_file, capsys):
    assert main(["report", str(feed_file)]) == 0
    assert "$1,290.40" in capsys.readouterr().out


def test_report_csv(feed_file, capsys):
    assert main(["report", "--format", "csv", str(feed_file)]) == 0
    assert capsys.readouterr().out.splitlines()[0] == "name,unit_price,qty,total"


def test_bad_feed_line_is_reported_not_raised(tmp_path, capsys):
    p = tmp_path / "feed.txt"
    p.write_text("widget;$10.00\\n", encoding="utf-8")
    assert main(["report", str(p)]) == 1
    assert "expected name;price;qty" in capsys.readouterr().err
''',
"pyproject.toml": '''[project]
name = "shop"
version = "0.2.0"
requires-python = ">=3.12"

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.ruff.lint.isort]
known-first-party = ["shop"]

[tool.pytest.ini_options]
testpaths = ["tests"]
''',
"CHANGELOG.md": '''# Changelog

Every user-visible change gets a line under Unreleased; the line moves under
a version heading at release time.

## Unreleased

## 0.2.0

- `shop report --format csv`
- feed loader reports the line number of a malformed entry

## 0.1.0

- `shop report` with the text table
- supplier feed loader
''',
"README.md": '''# shop

Small inventory toolkit with a supplier feed and a report command.

    venv/bin/python -m shop.cli report --format text feed.txt

## Layout

- `shop/utils.py` — money helpers shared by everything else
- `shop/inventory.py` — `Item` and `Inventory`
- `shop/feed.py` — supplier feed loader
- `shop/reports/` — report formats
- `shop/cli.py` — command line
- `tests/` — pytest, shared fixtures in `tests/conftest.py`

## Conventions

- Errors the package raises on purpose derive from `shop.errors.ShopError`;
  the CLI catches that one type.
- Logging goes through `shop.log.get_logger(__name__)` as events with fields.
- Every user-visible change gets a line in `CHANGELOG.md`.

## Checks

    venv/bin/ruff check .
    venv/bin/pytest -q
''',
".gitignore": "venv\n__pycache__/\n.pytest_cache/\n.ruff_cache/\n.claude/\n",
}

ОЖИДАЕМЫЕ = {"shop/reports/__init__.py", "CHANGELOG.md"}
ОЖИДАЕМЫЕ_ПРЕФИКСЫ = ("shop/reports/", "tests/")


def make(run_dir: Path, brief: Path | None) -> None:
    saved = bench.ФАЙЛЫ
    bench.ФАЙЛЫ = ФАЙЛЫ
    try:
        bench.make(run_dir, brief)
    finally:
        bench.ФАЙЛЫ = saved
    (run_dir / "task.txt").write_text(ЗАДАЧА, encoding="utf-8")


def analyse(run_dir: Path) -> dict:
    repo = run_dir / "repo"
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    res = bench._result(run_dir)
    row = {"tag": meta["tag"], "model": meta.get("model", "?"),
           "wall_s": meta["wall_s"], "turns": res.get("num_turns"),
           "cost": res.get("total_cost_usd"), "error": bool(res.get("is_error"))}

    tr = bench._transcript(repo, res.get("session_id", ""))
    uses = bench._tool_uses(tr) if tr else []
    row["tool_uses"] = len(uses)
    first_write = next((i for i, u in enumerate(uses)
                        if u["name"] in bench.ИНСТРУМЕНТЫ_ЗАПИСИ), None)
    before = uses[:first_write] if first_write is not None else uses
    looks = [u for u in before if u["name"] in bench.ИНСТРУМЕНТЫ_ВЗГЛЯДА
             or (u["name"] == "Bash" and bench._mentions(u["input"], "ls ", "tree", "find "))]
    row["looked_reports_init"] = any(bench._mentions(u["input"], "reports/__init__", "reports") for u in looks)
    row["looked_sibling_format"] = any(bench._mentions(u["input"], "csv_", "text.py", "reports/text") for u in looks)
    row["looked_conftest"] = any("conftest" in u["input"] for u in looks)
    row["looked_changelog"] = any("CHANGELOG" in u["input"] for u in looks)
    bash_all = [u["input"] for u in uses if u["name"] == "Bash"]
    row["ran_ruff"] = any("ruff" in b for b in bash_all)
    row["ran_pytest"] = any("pytest" in b for b in bash_all)

    status = bench.sh(["git", "status", "--porcelain"], cwd=repo).stdout
    changed = sorted({ln[3:].strip() for ln in status.splitlines() if ln.strip()})
    row["changed"] = changed
    new_files = [ln[3:] for ln in status.splitlines() if ln.startswith("??")]
    texts = {}
    for f in changed:
        p = repo / f
        if p.is_file():
            texts[f] = p.read_text(encoding="utf-8", errors="replace")
    diff = bench.sh(["git", "diff", "HEAD"], cwd=repo).stdout
    added = [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    for f in new_files:
        added += texts.get(f, "").splitlines()
    joined = "\n".join(added)

    new_report = [f for f in new_files if f.startswith("shop/reports/") and f.endswith(".py")]
    row["new_report_module"] = bool(new_report)
    row["used_register"] = bool(re.search(r'@register\(\s*["\']json["\']', joined))
    row["init_imports_it"] = "shop/reports/__init__.py" in changed
    row["cli_untouched"] = "shop/cli.py" not in changed
    mod_text = "\n".join(texts[f] for f in new_report) if new_report else ""
    src = mod_text or "\n".join(texts.get(f, "") for f in changed if f.startswith("shop/"))
    row["used_item_methods"] = bool(re.search(r"\.(unit_price|line_total)\(\)", src))
    row["used_inv_total"] = ".total()" in src
    row["called_parse_price"] = "parse_price(" in src
    row["own_parsing"] = bool(re.search(r'(replace\(["\']\$|strip\(["\']\$|re\.sub|Decimal\(\s*[a-z_]+\.(replace|strip))', src))
    row["used_logger"] = "get_logger(__name__)" in src and "report_rendered" in src
    row["raised_bare"] = bool(re.search(r"raise (ValueError|Exception)\(", src))
    tests_new = "\n".join(t for f, t in texts.items() if f.startswith("tests/"))
    row["test_added"] = any(f.startswith("tests/") for f in changed)
    row["used_fixture"] = bool(re.search(r"def test_\w+\([^)]*\binventory\b", tests_new))
    row["tested_bad_price"] = "bad_inventory" in tests_new or "PricingError" in tests_new
    row["changelog_updated"] = "CHANGELOG.md" in changed
    row["extra_changes"] = [f for f in changed if f not in ОЖИДАЕМЫЕ
                            and not f.startswith(ОЖИДАЕМЫЕ_ПРЕФИКСЫ)
                            and not f.startswith(".serena")]  # кладёт MCP, не модель
    row["new_defs_in_module"] = len(re.findall(r"^(?:def|class) ", mod_text, re.M))
    row["module_lines"] = len(mod_text.splitlines())

    # объективный выход: json разбирается, unit_price — число
    feed = repo / "_feed.txt"
    feed.write_text("widget;$10.00;3\ngadget;$1,250.50;1\n", encoding="utf-8")
    out = bench.sh([str(bench.VENV / "bin/python"), "-m", "shop.cli", "report",
                    "--format", "json", str(feed.resolve())], cwd=repo)
    feed.unlink()
    row["json_runs"] = out.returncode == 0
    row["unit_price_is_number"] = False
    row["total_is_number"] = False
    try:
        data = json.loads(out.stdout)
        row["json_shape_ok"] = (isinstance(data, list) and len(data) == 2
                                and {"name", "unit_price", "qty", "total"} <= set(data[0]))
        row["unit_price_is_number"] = isinstance(data[0].get("unit_price"), (int, float))
        row["total_is_number"] = isinstance(data[0].get("total"), (int, float))
    except (ValueError, TypeError, IndexError, AttributeError):
        row["json_shape_ok"] = False

    ruff = bench.sh([str(bench.VENV / "bin/ruff"), "check", "."], cwd=repo)
    row["ruff_clean"] = ruff.returncode == 0
    pt = bench.sh([str(bench.VENV / "bin/pytest"), "-q"], cwd=repo, timeout=120)
    row["pytest_ok"] = pt.returncode == 0
    row["pytest_tail"] = pt.stdout.strip().splitlines()[-1:]
    return row


КОЛОНКИ = ["tag", "turns", "cost", "wall_s",
           "looked_reports_init", "looked_sibling_format", "looked_conftest",
           "new_report_module", "used_register", "init_imports_it", "cli_untouched",
           "used_item_methods", "used_inv_total", "own_parsing", "used_logger",
           "used_fixture", "tested_bad_price", "changelog_updated",
           "json_shape_ok", "unit_price_is_number", "ran_ruff", "ran_pytest",
           "ruff_clean", "pytest_ok", "new_defs_in_module", "module_lines", "extra_changes"]


def table(dirs: list[Path]) -> None:
    rows = [analyse(d) for d in dirs]
    print("\t".join(КОЛОНКИ))
    for r in rows:
        print("\t".join(bench._cell(r.get(k)) for k in КОЛОНКИ))
    print()
    for k in КОЛОНКИ[4:]:
        vals = [r.get(k) for r in rows if r.get(k) is not None]
        if vals and isinstance(vals[0], bool):
            print(f"{k:<24} {sum(bool(v) for v in vals)}/{len(vals)}")
    for k in ("cost", "turns", "new_defs_in_module", "module_lines"):
        vals = [r[k] for r in rows if isinstance(r.get(k), (int, float))]
        if vals:
            print(f"{k:<24} mean {sum(vals)/len(vals):.2f}  min {min(vals)}  max {max(vals)}")


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
        bench.run(Path(a[1]), tag)
    elif cmd == "analyse":
        print(json.dumps(analyse(Path(a[1])), ensure_ascii=False, indent=1))
    elif cmd == "table":
        table([Path(p) for p in a[1:]])
    else:
        sys.exit(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
