---
{
  "id": "trah-python-calculator",
  "route": "brief",
  "scope": "trah",
  "kind": "section",
  "order": 170,
  "why": "python нужен для арифметики и обязан оставаться ею; и отдельно — программа длиннее десяти строк идёт в файл",
  "covered_by": []
}
---
## Python is a calculator, not a file tool

There is work Serena cannot do at all, and refusing it would leave you without
arithmetic: aggregating over huge logs, parsing JSON/YAML to answer a derived
question, measuring sizes and timings, probing HTTP, running processes. That is
python's niche, and it is legitimate.

The boundary is what comes **out** of it:

- it may open a project file, as long as only numbers and verdicts come back —
  the content must not reach the context through it;
- printing a file body from python is `cat` wearing a hat: read it with Serena;
- writing or patching a project file from python is `sed -i` wearing a hat: edit
  it with `replace_content` / `replace_symbol_body`, and create a brand-new file
  with `Write`.

And the form matters as much as the target: **a program of ten lines or more
goes into a file** and is run by name — ten is already over the line, not the
last value under it. Inline program text — code typed into the
Bash argument — is re-sent with the whole context on every following turn. A file
is paid for once; every re-run after that costs thirty tokens.

In this mode that line is enforced rather than advised: the launcher starts the
session with `nudge-serena.py` in blocking mode, so an inline program of ten
lines or more comes back as a tool error and the turn is spent.
