// На какие вендорные имена опирается наш код в форке.
//
// Разбираем файл форка целиком, находим все объявления верхнего уровня, затем
// для каждой нашей функции (имя начинается с fork) собираем идентификаторы,
// которые внутри неё не объявлены. Что осталось и при этом объявлено на верхнем
// уровне — и есть вендорная зависимость, требующая переотображения при переезде.
import { readFileSync } from "node:fs";
import * as acorn from "acorn";
import * as walk from "acorn-walk";

const файл = process.argv[2];
const код = readFileSync(файл, "utf8");
const дерево = acorn.parse(код, { ecmaVersion: "latest", sourceType: "module" });

const верх = new Set();
for (const у of дерево.body) {
  if (у.type === "FunctionDeclaration" && у.id) верх.add(у.id.name);
  if (у.type === "ClassDeclaration" && у.id) верх.add(у.id.name);
  if (у.type === "VariableDeclaration")
    for (const d of у.declarations)
      if (d.id.type === "Identifier") верх.add(d.id.name);
}

const ГЛОБАЛЬНЫЕ = new Set([
  "Math", "Date", "Set", "Map", "JSON", "Object", "Array", "String", "Number",
  "Boolean", "Promise", "console", "globalThis", "window", "document", "Intl",
  "RegExp", "Error", "undefined", "NaN", "Infinity", "navigator", "performance",
  "setTimeout", "clearTimeout", "setInterval", "clearInterval", "structuredClone",
]);

function имена(узел) {
  // объявления внутри функции: параметры, var/let/const, вложенные функции
  const объявлено = new Set();
  const собрать = (p) => {
    if (!p) return;
    if (p.type === "Identifier") объявлено.add(p.name);
    else if (p.type === "ObjectPattern") p.properties.forEach((q) => собрать(q.value ?? q.argument));
    else if (p.type === "ArrayPattern") p.elements.forEach(собрать);
    else if (p.type === "AssignmentPattern") собрать(p.left);
    else if (p.type === "RestElement") собрать(p.argument);
  };
  (узел.params ?? []).forEach(собрать);
  walk.full(узел, (у) => {
    if (у.type === "VariableDeclarator") собрать(у.id);
    if ((у.type === "FunctionDeclaration" || у.type === "ClassDeclaration") && у.id)
      объявлено.add(у.id.name);
    if (у.type === "ArrowFunctionExpression" || у.type === "FunctionExpression")
      (у.params ?? []).forEach(собрать);
    if (у.type === "CatchClause") собрать(у.param);
  });
  return объявлено;
}

const счёт = new Map();
const сироты = new Map();
let наших = 0;
for (const у of дерево.body) {
  if (у.type !== "FunctionDeclaration" || !у.id || !у.id.name.startsWith("fork")) continue;
  наших++;
  const объявлено = имена(у);
  walk.full(у, (n, _st, тип) => {
    if (n.type !== "Identifier") return;
    const и = n.name;
    if (объявлено.has(и) || ГЛОБАЛЬНЫЕ.has(и) || и.startsWith("fork")) return;
    if (!верх.has(и)) {
      // Имя свободно и НИГДЕ в файле не объявлено — в работе это ReferenceError
      // и пустой экран без единого сообщения. Ровно так выглядит недоведённое
      // переименование после переезда.
      сироты.set(и, (сироты.get(и) ?? 0) + 1);
      return;
    }
    счёт.set(и, (счёт.get(и) ?? 0) + 1);
  });
}

console.log(`наших функций верхнего уровня: ${наших}`);
console.log(`вендорных имён, на которые они опираются: ${счёт.size}\n`);
for (const [и, к] of [...счёт].sort((a, b) => b[1] - a[1]))
  console.log(`  ${и.padEnd(8)} ${к}`);
console.log(`\nСИРОТЫ (не объявлены нигде в файле): ${сироты.size}`);
for (const [и, к] of [...сироты].sort((a, b) => b[1] - a[1]))
  console.log(`  ✗ ${и.padEnd(8)} ${к}`);
