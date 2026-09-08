// Разбор перенесённых файлов: опечатка переименования проявится здесь, а не
// в вебвью с пустым экраном и без сообщения.
import { readFileSync } from "node:fs";
import * as acorn from "acorn";

let плохо = 0;
for (const путь of process.argv.slice(2)) {
  const код = readFileSync(путь, "utf8");
  try {
    acorn.parse(код, { ecmaVersion: "latest", sourceType: "module" });
    console.log(`  ✓ ${путь}: разобран, ${код.split("\n").length} строк`);
  } catch (е) {
    плохо++;
    const строка = код.split("\n")[(е.loc?.line ?? 1) - 1] ?? "";
    console.log(`  ✗ ${путь}: ${е.message}`);
    console.log(`      ${строка.trim().slice(0, 120)}`);
  }
}
process.exit(плохо ? 1 : 0);
