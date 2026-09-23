---
{
  "id": "trah-machine",
  "route": "brief",
  "scope": "trah",
  "kind": "section",
  "order": 40,
  "personal": true,
  "why": "то, чего машина не может сказать о себе сама: где рабочие деревья, какие оболочки, какие грабли уже стоили сессий",
  "note": "Перенесено 23.09.2026 из куска `env-lotm-desktop` tausozavr. Пути сверены с диском: `D:\\Sites_job`, `D:\\Claude_mcp` (в прежнем брифе стояли дефисы, каталогов с такими именами нет)",
  "covered_by": []
}
---
## This machine — traps and habits

Windows 11. The `Bash` tool is Git Bash; the `PowerShell` tool is Windows
PowerShell 5.1 — no `&&`, no `||`, no ternary, no null-coalescing. Do not carry a
one-liner from one into the other.

- **Work trees:** `D:\` (nearly every project — `D:\tausik-ops`, `D:\tg-build`,
  `D:\wa-tg-bridge`, `D:\Sites_job\*`, `D:\Claude_mcp`, `D:\asynchronus`,
  `D:\claude-trah`), `C:\Users\lotm\Local Sites` (local WordPress sites),
  `C:\Users\lotm\.tausik-lib` (the TAUSIK library hub). The home directory itself
  is not a project.
- **A `.cmd` wrapper silently keeps only the first line of a multi-line
  argument.** For TAUSIK with a multi-line argument use `.tausik/tausik.ps1`,
  never `.tausik/tausik.cmd`. Nothing reports the truncation.
- **Never stop AmneziaVPN or its `tun2socks`.** Remote access to this machine
  (AnyDesk) rides on it: killing it ends the session you are working in.
- **A dead system proxy lives in the registry:** `ProxyServer` is
  `127.0.0.1:8080` and nothing listens there. Keep `ProxyEnable` at `0`. Turned
  on, a browser driven by Playwright or Chrome dies with
  `ERR_PROXY_CONNECTION_FAILED`, and the error names the page, not the proxy.
- **The default browser handler is custom** (`tg-yt-player`): it opens YouTube
  links in an embedded player window instead of a browser tab.
- **`bash` from Windows programs is WSL's**, not Git's: `CreateProcess` finds
  `C:\Windows\System32\bash.exe` before PATH. A script that must run under Git
  Bash is started by its full path, `C:\Program Files\Git\bin\bash.exe`.
