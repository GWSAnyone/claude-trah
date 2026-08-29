---
name: browser
description: |
  Look at a page with a real browser instead of guessing from the code: open a
  URL, read its structure, take a picture, click and type, read console errors.
  Use when the work is visual or behavioural — a layout is wrong, a page looks
  different from the intent, a button does nothing, a form does not submit, a
  style change needs checking, a bug reproduces only in a browser. Also use it
  to CHECK a frontend change before saying it is done.
  NOT needed for editing a style rule you were told to edit and not asked to verify.
---

# Looking at the page

Without a browser, a frontend claim is a guess. The code says one thing; the
rendered page is the fact. This skill is the loop that closes that gap.

Tools arrive as `mcp__playwright__*`. Like every MCP tool they are **deferred**:
pull them in with `ToolSearch` before the first call, or they do not exist for
you.

    ToolSearch("+playwright navigate snapshot screenshot click")

## The two ways to look, and why the choice matters

| | `browser_snapshot` | `browser_take_screenshot` |
|---|---|---|
| what you get | the accessibility tree, as text | a raster image |
| what it answers | what is on the page, what it says, what state it is in | what it LOOKS like |
| cost | a page of text | an image in context, and it stays there |

**Reach for the snapshot first.** Most questions — is the button there, what
does the label say, is the field disabled, did the list get five rows — are
answered by text, cheaply, and text is greppable. The picture is for questions
that are genuinely about appearance: spacing, alignment, colour, overflow,
whether the thing looks broken.

Do not take a screenshot "to be sure" after a snapshot already answered. Each
image is paid for once and then re-sent with the whole context on every later turn.

## The loop

1. **Serve it.** A dev server (`bun run dev`, `npm start`, `docker compose up`)
   or a static server on a spare port. Start it in the background and confirm it
   answers before opening a browser at it.
2. **Open it** — `browser_navigate`.
3. **Look** — snapshot for structure, screenshot when the question is visual.
4. **Read the console.** Errors are captured to the output directory; a page can
   look right and still be throwing. A visual check that ignores the console is
   half a check.
5. **Change one thing** in the code.
6. **Reload and look again.**

Two passes of change-and-look is usually where it converges. If a third pass has
not fixed it, the problem is not where you are looking, and another screenshot
will not tell you. Go back to the code.

## Interacting

`browser_click`, `browser_type`, `browser_select_option`, `browser_press_key`
drive the page. Target elements by their accessibility name from the snapshot,
not by a CSS selector you guessed — the snapshot names are what the tool
actually resolves against.

To prove a behaviour is fixed, drive the path a user drives: fill the field,
press the button, read the result. A screenshot of a form is not proof that the
form submits.

## Traps, all met on 29.08.2026 setting this up

**The browser must be named.** Playwright MCP defaults to the system Google
Chrome, which is not installed here. Our config pins `--browser chromium`, which
uses the bundled build in `~/.cache/ms-playwright`. If navigation fails with
"distribution 'chrome' is not found", that flag went missing.

**The MCP carries its own Playwright.** It may want a chromium build different
from the one installed by hand, and it downloads that build on first use. The
first navigation of a fresh install is therefore slow and looks like a hang. It
is not.

**Headless is on.** No window appears on the owner's desktop. That is deliberate:
a browser window stealing focus mid-session is worse than not seeing it.

**Output lands in `~/.claude/playwright-out`** — console logs, page dumps,
downloads. Screenshots go where you name them; name them somewhere in the
project or in `/tmp`, not into the source tree.

## Rules

1. **Never claim a frontend change works without having looked.** "Should
   render correctly" is the sentence this skill exists to delete.
2. Report what you saw, with the artifact: the path to the screenshot, or the
   quoted line from the snapshot. A visual claim with no artifact is a guess
   wearing a lab coat.
3. Console errors get reported even when the page looks fine.
4. Do not leave dev servers running. Stop what you started.
5. The browser reads the page; it does not read the code. When something looks
   wrong, the fix is found by reading the source, not by taking more pictures.
