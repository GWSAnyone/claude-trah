#!/usr/bin/env python3
"""qbench v3 — стенд на ВКУС, а не на привычки.

Отличие от v2: там задача была «добавь рядом с соседями», и её решает
аккуратность. Здесь задача-МОДИФИКАЦИЯ сквозь готовую систему из трёх
форматов отчёта, и у неё есть дешёвый неправильный ответ, который проходит
тесты: проверить признак в каждом из трёх рендереров. Сеньор кладёт правило
в ОДНО место — там, где живёт сам список предметов, — и три формата получают
его даром.

Ловушки, каждая измерима:
  * дублирование: сколько файлов под shop/ содержат предикат отсева;
  * переиспользование: есть ли готовый `fmt_count` в utils (нужен для строки
    «skipped N»), найдёт ли его модель, или напишет свой f-string;
  * свои типы ошибок: PricingError уже есть, новый класс заводить не за что;
  * идиома лога: событие с полями, а не предложение;
  * ЧУЖОЙ код: `shop/audit.py` перебирает inv.items напрямую — если правило
    положено в Inventory.items, аудит молча изменит смысл; сеньор это видит
    и либо не трогает items, либо чинит аудит осознанно;
  * минимальность: задача НЕ просит настройку, флаг или стратегию отсева.

    bench3.py make <run_dir> [--brief FILE]
    bench3.py run  <run_dir> [--tag T]
    bench3.py table <run_dir>...
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench   # noqa: E402
import bench2  # noqa: E402

ЗАДАЧА = (
    "Поставщик стал присылать в фиде снятые с продажи позиции: у них "
    "количество 0 и цена 'n/a'. Такие позиции не должны попадать ни в один "
    "отчёт и не должны учитываться в сумме, а команда должна сообщать, "
    "сколько позиций пропущено. Остальное поведение не меняй."
)

_utils = bench2.ФАЙЛЫ["shop/utils.py"].replace(
    'def fmt_money(value: Decimal) -> str:\n    """Format a Decimal as ``$1,234.56``."""\n    return f"{_CURRENCY}{value:,.2f}"\n',
    'def fmt_money(value: Decimal) -> str:\n    """Format a Decimal as ``$1,234.56``."""\n    return f"{_CURRENCY}{value:,.2f}"\n'
    '\n\ndef fmt_count(n: int, noun: str) -> str:\n'
    '    """Pluralise a count the way every user-facing line in shop does.\n\n'
    '    ``fmt_count(1, "item") == "1 item"``, ``fmt_count(3, "item") == "3 items"``.\n'
    '    """\n'
    '    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"\n')

ФАЙЛЫ = dict(bench2.ФАЙЛЫ)
ФАЙЛЫ["shop/utils.py"] = _utils
ФАЙЛЫ["shop/reports/__init__.py"] = bench2.ФАЙЛЫ["shop/reports/__init__.py"].replace(
    "from shop.reports import csv_, text  # noqa: E402,F401",
    "from shop.reports import csv_, json_, text  # noqa: E402,F401")
ФАЙЛЫ["shop/reports/json_.py"] = '''"""JSON array, one object per item; prices as plain numbers."""
import json

from shop.inventory import Inventory
from shop.log import get_logger
from shop.reports import register

log = get_logger(__name__)


@register("json")
def render_json(inv: Inventory) -> str:
    rows = [
        {
            "name": item.name,
            "unit_price": float(item.unit_price()),
            "qty": item.qty,
            "total": float(item.line_total()),
        }
        for item in inv.items
    ]
    log.info("report_rendered", format="json", items=len(rows))
    return json.dumps(rows, indent=2)
'''
ФАЙЛЫ["shop/audit.py"] = '''"""Audit helpers used by the nightly job, not by the CLI."""
from decimal import Decimal

from shop.inventory import Inventory
from shop.log import get_logger

log = get_logger(__name__)


def count_lines(inv: Inventory) -> int:
    """Every line the supplier sent us, including ones we do not sell."""
    return len(inv.items)


def heaviest_line(inv: Inventory) -> str | None:
    biggest, name = Decimal(0), None
    for item in inv.items:
        try:
            value = item.line_total()
        except Exception:  # noqa: BLE001 - audit never fails the nightly job
            log.warning("audit_skipped_line", item=item.name)
            continue
        if value > biggest:
            biggest, name = value, item.name
    return name
'''
ФАЙЛЫ["tests/conftest.py"] = bench2.ФАЙЛЫ["tests/conftest.py"].replace(
    '''@pytest.fixture
def feed_file(tmp_path: Path) -> Path:''',
    '''@pytest.fixture
def mixed_feed(tmp_path: Path) -> Path:
    """A feed as the supplier sends it now: two live items, one discontinued."""
    p = tmp_path / "mixed.txt"
    p.write_text("widget;$10.00;3\\ndusty;n/a;0\\ngadget;$1,250.50;1\\n",
                 encoding="utf-8")
    return p


@pytest.fixture
def feed_file(tmp_path: Path) -> Path:''')
ФАЙЛЫ["tests/test_reports.py"] = bench2.ФАЙЛЫ["tests/test_reports.py"].replace(
    'assert formats() == ["csv", "text"]', 'assert formats() == ["csv", "json", "text"]'
).replace('@pytest.mark.parametrize("name", ["text", "csv"])',
          '@pytest.mark.parametrize("name", ["text", "csv", "json"])')
ФАЙЛЫ["CHANGELOG.md"] = bench2.ФАЙЛЫ["CHANGELOG.md"].replace(
    "## 0.2.0\n\n- `shop report --format csv`",
    "## 0.2.0\n\n- `shop report --format json`\n- `shop report --format csv`")
ФАЙЛЫ["README.md"] = bench2.ФАЙЛЫ["README.md"].replace(
    "- `tests/` — pytest, shared fixtures in `tests/conftest.py`",
    "- `shop/audit.py` — helpers for the nightly audit job\n"
    "- `tests/` — pytest, shared fixtures in `tests/conftest.py`")

ПРЕДИКАТ = re.compile(
    r'(discontinued|is_live|n/a|["\']n/a["\']|qty\s*(==|<=|>)\s*0|qty\s*and\b)', re.I)


def make(run_dir: Path, brief: Path | None) -> None:
    saved = bench.ФАЙЛЫ
    bench.ФАЙЛЫ = ФАЙЛЫ
    try:
        bench.make(run_dir, brief)
    finally:
        bench.ФАЙЛЫ = saved
    (run_dir / "task.txt").write_text(ЗАДАЧА, encoding="utf-8")


def _run_format(repo: Path, feed: Path, fmt: str):
    out = bench.sh([str(bench.VENV / "bin/python"), "-m", "shop.cli", "report",
                    "--format", fmt, str(feed.resolve())], cwd=repo)
    return out


def analyse(run_dir: Path) -> dict:
    repo = run_dir / "repo"
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    res = bench._result(run_dir)
    row = {"tag": meta["tag"], "model": meta.get("model", "?"),
           "effort": meta.get("effort", "?"), "wall_s": meta["wall_s"],
           "turns": res.get("num_turns"), "cost": res.get("total_cost_usd")}

    tr = bench._transcript(repo, res.get("session_id", ""))
    uses = bench._tool_uses(tr) if tr else []
    first_write = next((i for i, u in enumerate(uses)
                        if u["name"] in bench.ИНСТРУМЕНТЫ_ЗАПИСИ), None)
    before = uses[:first_write] if first_write is not None else uses
    looks = [u for u in before if u["name"] in bench.ИНСТРУМЕНТЫ_ВЗГЛЯДА
             or (u["name"] == "Bash" and bench._mentions(u["input"], "ls ", "tree", "find ", "grep"))]
    row["looked_all_three"] = sum(
        any(bench._mentions(u["input"], f) for u in looks)
        for f in ("text.py", "csv_", "json_")) >= 3
    row["looked_audit"] = any("audit" in u["input"] for u in looks)
    row["looked_utils"] = any("utils" in u["input"] for u in looks)
    bash_all = [u["input"] for u in uses if u["name"] == "Bash"]
    row["ran_ruff"] = any("ruff" in b for b in bash_all)
    row["ran_pytest"] = any("pytest" in b for b in bash_all)

    status = bench.sh(["git", "status", "--porcelain"], cwd=repo).stdout
    changed = sorted({ln[3:].strip() for ln in status.splitlines()
                      if ln.strip() and ".serena" not in ln})
    row["changed"] = changed
    diff = bench.sh(["git", "diff", "HEAD", "--", "shop", "tests", "CHANGELOG.md"],
                    cwd=repo).stdout
    added = [ln[1:] for ln in diff.splitlines()
             if ln.startswith("+") and not ln.startswith("+++")]
    removed = [ln[1:] for ln in diff.splitlines()
               if ln.startswith("-") and not ln.startswith("---")]
    row["added_lines"] = len(added)
    row["removed_lines"] = len(removed)

    # ГЛАВНАЯ метрика: во скольких файлах под shop/ живёт предикат отсева
    sites = []
    for f in changed:
        if not f.startswith("shop/") or not f.endswith(".py"):
            continue
        текст = "\n".join(ln[1:] for ln in diff.splitlines()
                          if ln.startswith("+") and not ln.startswith("+++"))
        p = repo / f
        if p.is_file() and ПРЕДИКАТ.search(p.read_text(encoding="utf-8", errors="replace")):
            sites.append(f)
    row["filter_sites"] = sites
    row["filter_site_count"] = len(sites)
    row["single_place"] = len(sites) == 1
    row["renderers_touched"] = len([f for f in changed if f.startswith("shop/reports/")
                                    and f != "shop/reports/__init__.py"])

    src = "\n".join((repo / f).read_text(encoding="utf-8", errors="replace")
                    for f in changed if f.startswith("shop/") and (repo / f).is_file())
    row["used_fmt_count"] = "fmt_count(" in src
    row["own_plural"] = bool(re.search(r'["\']s["\']\s*if|item\{|\{.*\}s\b|"s" if', src))
    row["new_exception_class"] = bool(re.search(r"^class \w+\(.*Error\)", src, re.M))
    row["logged_event"] = bool(re.search(r'log\.(info|warning)\(\s*["\'][a-z_]+["\']', src))
    row["touched_audit"] = "shop/audit.py" in changed
    row["changelog_updated"] = "CHANGELOG.md" in changed
    row["added_config_knob"] = bool(re.search(r"(add_argument\(\s*[\"']--(?!format)|include_discontinued|skip_discontinued\s*[:=]\s*bool)", src))

    feed = repo / "_mixed.txt"
    feed.write_text("widget;$10.00;3\ndusty;n/a;0\ngadget;$1,250.50;1\n",
                    encoding="utf-8")
    outs = {f: _run_format(repo, feed, f) for f in ("text", "csv", "json")}
    feed.unlink()
    row["all_formats_run"] = all(o.returncode == 0 for o in outs.values())
    def _has_dusty(o):
        return "dusty" in o.stdout
    row["dusty_hidden_everywhere"] = (row["all_formats_run"]
                                      and not any(_has_dusty(o) for o in outs.values()))
    row["total_excludes"] = "$1,280.50" in outs["text"].stdout
    combined = "\n".join(o.stdout + o.stderr for o in outs.values())
    row["reports_skipped_count"] = bool(re.search(r"\b1\b[^\n]{0,20}(skip|item)", combined, re.I))

    ruff = bench.sh([str(bench.VENV / "bin/ruff"), "check", "."], cwd=repo)
    row["ruff_clean"] = ruff.returncode == 0
    pt = bench.sh([str(bench.VENV / "bin/pytest"), "-q"], cwd=repo, timeout=120)
    row["pytest_ok"] = pt.returncode == 0
    row["pytest_tail"] = pt.stdout.strip().splitlines()[-1:]
    return row


КОЛОНКИ = ["tag", "turns", "cost", "wall_s", "looked_all_three", "looked_audit",
           "filter_site_count", "single_place", "renderers_touched",
           "used_fmt_count", "new_exception_class", "added_config_knob",
           "touched_audit", "logged_event", "changelog_updated",
           "dusty_hidden_everywhere", "total_excludes", "reports_skipped_count",
           "ran_ruff", "ran_pytest", "ruff_clean", "pytest_ok",
           "added_lines", "removed_lines", "filter_sites"]


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
    for k in ("cost", "turns", "filter_site_count", "added_lines", "removed_lines"):
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
