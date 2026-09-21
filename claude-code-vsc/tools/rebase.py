"""Перенос одного ханка форка правка-за-правкой: база(старая) ↔ цель(новая) выравниваются difflib по форме.

rebase.py <база> <форк> <цель> <номер ханка при -U6> <строка цели, 1-based, начало окна> [--применить]
"""
import difflib, re, subprocess, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import port as P
from pathlib import Path

база, форк, цель = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
nh, нач = int(sys.argv[4]), int(sys.argv[5]) - 1
применить = "--применить" in sys.argv

заголовки = [l for l in subprocess.run(["diff", "-U6", str(база), str(форк)], capture_output=True, text=True).stdout.split("\n") if l.startswith("@@")]
m = re.match(r"@@ -(\d+),(\d+) \+(\d+),(\d+)", заголовки[nh - 1])
a, n, b, k = int(m[1]) - 1, int(m[2]), int(m[3]) - 1, int(m[4])
стар = база.read_text(encoding="utf-8").split("\n")[a:a + n]
форк_ = форк.read_text(encoding="utf-8").split("\n")[b:b + k]
новые = цель.read_text(encoding="utf-8").split("\n")
окно = новые[нач:нач + n + 80]

норм = P.нормализовать
выр = difflib.SequenceMatcher(None, [норм(с) for с in стар], [норм(с) for с in окно], autojunk=False)
куда, карта = {}, {с: н for с, (н, _) in P.КАРТА_ВЕБВЬЮ.items()}
for тег, i1, i2, j1, j2 in выр.get_opcodes():
    if тег == "equal":
        for d in range(i2 - i1):
            куда[i1 + d] = j1 + d
            пары = P.имена_позиционно(стар[i1 + d], окно[j1 + d])
            if пары:
                карта.update(пары)

правки, беда = [], []
for тег, i1, i2, j1, j2 in difflib.SequenceMatcher(None, стар, форк_, autojunk=False).get_opcodes():
    if тег == "equal":
        continue
    текст = [P.переименовать(с, карта) for с in форк_[j1:j2]]
    if тег == "insert":
        if i1 - 1 in куда:
            где = куда[i1 - 1] + 1
        elif i1 in куда:
            где = куда[i1]
        else:
            беда.append(f"вставка перед прежней строкой {i1}: соседи не выровнялись")
            continue
        правки.append((где, 0, текст))
    else:
        if not all(i in куда for i in range(i1, i2)) or куда[i2 - 1] - куда[i1] != i2 - i1 - 1:
            беда.append(f"{тег} прежних строк {i1}:{i2} — их нет в цели той же формы: " + " | ".join(с.strip()[:70] for с in стар[i1:i2]))
            continue
        правки.append((куда[i1], i2 - i1, текст))

чужие = sorted({и for с in форк_ for и in P.ИМЯ.findall(с) if len(и) <= 3 and и not in карта})
print(f"ханк {nh}: прежних {n}, форк {k}, правок {len(правки)}, бед {len(беда)}; короткие имена вне карты: {' '.join(чужие)}")
for б in беда:
    print("  ✗ " + б)
if применить and not беда:
    for где, скольких, текст in sorted(правки, key=lambda z: -z[0]):
        новые[нач + где:нач + где + скольких] = текст
    цель.write_text("\n".join(новые), encoding="utf-8")
    print("  применено")
