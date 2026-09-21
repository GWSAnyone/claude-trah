"""Сверка расстановки: правки vendor_old→fork и vendor_new→port должны совпадать по форме,
включая вендорную строку-соседа перед каждой правкой. Ловит код, вставленный не туда."""
import subprocess, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import port as P


def правки(a, b):
    out = subprocess.run(["diff", "-U1", a, b], capture_output=True, text=True).stdout.split("\n")[2:]
    итог, перед, тек = [], None, None
    for l in out:
        if l.startswith("@@"):
            перед, тек = None, None
            continue
        if l.startswith((" ",)):
            if тек:
                итог.append(тек)
                тек = None
            перед = P.нормализовать(l[1:]).strip()
        elif l.startswith(("+", "-")):
            if тек is None:
                тек = {"перед": перед, "строки": []}
            тек["строки"].append(l[0] + P.нормализовать(l[1:]).strip())
    if тек:
        итог.append(тек)
    return [(т["перед"], tuple(т["строки"])) for т in итог]


стар, нов = правки(sys.argv[1], sys.argv[2]), правки(sys.argv[3], sys.argv[4])
from collections import Counter
cs, cn = Counter(стар), Counter(нов)
лишние, нет = cn - cs, cs - cn
print(f"правок: прежде {len(стар)}, теперь {len(нов)}; расходятся: нет в новом {sum(нет.values())}, лишних в новом {sum(лишние.values())}")
for (перед, строки), c in list(нет.items())[:15]:
    print("  НЕТ  после:", (перед or "")[:80], "|", строки[0][:90], f"(+{len(строки)-1})")
for (перед, строки), c in list(лишние.items())[:15]:
    print("  ЛИШН после:", (перед or "")[:80], "|", строки[0][:90], f"(+{len(строки)-1})")
