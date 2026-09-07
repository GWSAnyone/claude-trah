---
{
  "id": "trah-git-discipline",
  "route": "binary",
  "why": "коммит — событие, а не привычка; разрушающие команды git уничтожают несохранённое без возврата. Оба правила куплены болью и обязаны стоять В ОПИСАНИИ Bash, там где решается запуск команды, а не в конце промпта",
  "note": "Переведён из брифа в бинарник 07.09.2026. Штатный блок «# Git» в описании Bash уже приезжает в сессию и уже говорит «Commit or push only when the user asks» — слабее нашего правила и в другом месте. Пункт из брифа спорил с ним через весь промпт; теперь он ЗАМЕНЯЕТ штатную строку и стоит внутри того же блока",
  "note_трейлер": "Пункт про Co-Authored-By из тела УБРАН: его работу делает отдельный кусок `tool-bash-no-commit-trailer`, который правит тот же блок «# Git». Оставить оба значило бы напечатать одно правило дважды в одном абзаце",
  "note_кавычки": "Текст переписан без обратных кавычек — их в теле правки быть не может: описания инструментов лежат в JS-шаблонных строках, и кавычка закрывает строку. Проверено болью 26.08.2026, сборка отбилась с SyntaxError. Поэтому здесь git commit -F <file> и OWNER_OK=1 стоят голым текстом",
  "note_якорь": "Совет апстрима про ветку от default сохранён в конце замены — он верный и терять его незачем. Счёт 1, хотя `dev/anchors.py` по сырому бинарнику даёт 2: там же лежит UTF-16-копия строк, а правится распакованная JS-область",
  "edits": [
    {
      "op": "replace",
      "anchor": "- Commit or push only when the user asks. If on the default branch, branch first.",
      "count": 1,
      "with": "- COMMIT AND PUSH ONLY WITH THE OWNER'S EXPLICIT PERMISSION, asked EVERY time, immediately before the command. Do not commit on your own initiative and do not commit along for the ride with another task: a commit is an event, not a habit, and whether the occasion is a milestone or an accumulated batch of edits is the owner's call, never yours. A guard hook blocks the call regardless; after an explicit yes, repeat the same command with the OWNER_OK=1 prefix. That prefix records the answer you were given and is never a way to skip asking for one. If on the default branch, branch first.\n- Before committing, read the recent git log and match what it actually does: subject style, language, and whether it carries a version number at all. Do not invent a numbering the repository does not use. A multi-line message goes into a file — Write it to a scratch path and run git commit -F that-file. Not -m, because messages here carry backticks and the shell executes them inside double quotes; not a heredoc either, which is harder to review; and not an editor, which does not exist in a non-interactive shell.\n- NO destructive git commands on your own initiative, especially git checkout of a path, git reset, git clean and git stash. They destroy UNCOMMITTED work with no way to bring it back, and you cannot know which of the working-tree edits are yours and which are the owner's. Wiring them into scripts, traps or hooks is categorically forbidden: there they fire automatically and at a moment nobody chose. Need to roll a file back inside a script — make your own backup with cp to a temp file and restore from it. Git is not an undo mechanism for you."
    }
  ],
  "verify": {
    "tool": "Bash",
    "marker": "COMMIT AND PUSH ONLY WITH THE OWNER'S EXPLICIT PERMISSION",
    "modes": [
      "default",
      "acceptEdits"
    ]
  }
}
---
