---
name: frontend-design
description: |
  Interface design: what to show, in what order, how to keep a number from
  being read wrong, where to put friction in front of money. Use when
  you are building a new page or screen, reworking an existing one, adding a
  table/listing/action form, or when the owner says
  «сделай интерфейс», «неудобно», «непонятно», «покажи это на фронте».
  NOT needed for editing one style rule or a button's text.
---

# Interface design

Our interfaces are the instrument panels of an operator who handles money.
Not a product showcase and not a portfolio: the page has one reader, he knows
the subject better than we do and opens it in order to **make a decision and
not get it wrong**.

Hence the measure of quality. "Beautiful" is the wrong word. The right word is
**unambiguous**: the state of affairs is visible in ten seconds, and a number
cannot be understood wrong.

## What is here and what is not

| Layer | Where it lives | What is in it |
|---|---|---|
| Mechanics | `SyncedProjects/.claude/rules/frontend.md` | tokens, button classes, file layout, JS conventions. Loads itself when working with `web/` |
| **Judgement** | **this skill** | what to show, what to sacrifice, what to call it, where to put friction |
| Current defects | `docs/plans/*-frontend-refactor.md` | what exactly is broken right now and in what order it gets fixed |

The split is what keeps the skill alive. Today's list of defects goes stale as
they are fixed; the rules do not. Found a defect — its place is in the plan, and
only the lesson that follows from it lands here.

The skill is global and gets invoked in any ecosystem. Outside GWS there is no
mechanics rule — then the first thing to do is start a token dictionary and hold
to it just as strictly: everything below rests on the palette and the fonts
having been settled in advance and not being reopened on every page.

---

## Step 0 — name the page's job

In one sentence: **who** opens it, **what decision** they make, **what gets in
the way** of making it now. Until that sentence exists, there is nothing to lay
out.

> «Владелец открывает витрину продажи, чтобы выбрать, что продать сегодня.
> Мешает то, что шесть тысяч позиций лежат одной таблицей.»

From a sentence like that the structure derives itself. From
«сделать страницу позиций» nothing derives, and you get a table with every
field in a row.

**One page — one job.** If the sentence needs the conjunction «и», that is two
pages or two tabs. The sign of the violation is visible in the code: a
three-thousand-line file is usually five jobs stuck together into one.

---

## Numbers

### Four questions for every number

No answer — the number is not ready to be shown.

| Question | How we answer |
|---|---|
| **What is it about?** | A band, a marketplace, a population. A price can be about a float band, not about the item |
| **What is it in?** | The unit is baked into the **function name**, not into a comment |
| **Where from?** | A snapshot, a live request, a computation — next to the number, not in a tooltip |
| **How fresh is it?** | Age and threshold. See the freshness section |

The rule everything follows from: **if a number describes something other than
exactly the object in the row, that has to be visible in the row itself.**

### The unit goes in the function name

The reference is `DmTrading/web/v2/js/lib/fmt.js`: `fmtDollars(d)` and
`fmtCents(c)`, and at the import it is written `import { fmtCents as fmtUSD }`.
The body of the page reads the same either way, and the unit can only be
confused deliberately, on one line.

It was done that way not out of love of order: the old shared `fmtUSD` meant
dollars in one file and cents in the next, and both "worked".

### `null` is not `0`

"Cost basis unknown" and "cost basis zero" lead to opposite decisions. The
formatter has to tell them apart: `null → —`, `0 → $0.00`.

### Sign, digit grouping, alignment

- Negative money is `-$1.23`, not `$-1.23`.
- Percentages where direction matters always carry a sign: `+38.4%` / `-4.1%`.
- The number of decimal places is fixed within a column. `$1.2` next to
  `$1.23` under right alignment reads as a different order of magnitude.
- Numeric columns are monospaced, right-aligned, **and `tabular-nums`**.
  Without the last one the digits differ in width and the column jitters.
- Large amounts get their digits grouped: `$12,345.67`.

### The parameter that produced the number goes next to the number

A margin without the commission rate cannot be checked. A line like
`142 items · comm 2% · upd 14:03` is worth ten tooltips.

---

## Freshness

**Age without a threshold is useless.** A muted `snapshot 14h ago` looks exactly
like `snapshot 3m ago` — the eye does not tell them apart. The threshold has to
change the appearance: a `(stale)` label, colour dimming, a warning.

The reference is `CSGOMarketParser/web/accounts.html`: a number that outlived a
bot restart carries its relative age, past the threshold it gets `(stale)` and
fades from green to muted, and the exact time moves into `title`.

Three rules:

1. **Relative time in the cell, absolute in the tooltip.** "12s ago"
   answers "is it working", "14:03:11" answers "when exactly". Both are needed,
   but in different places.
2. **Staleness of SOMEBODY ELSE'S source goes into the global header.** A panel
   trading on a neighbouring service's prices has to shout `⚠ DM stale 14m` at
   the top, not hide it in a cell.
3. **If the backend knows the threshold — the frontend has to show it.** The
   case where the server refuses to trade on a stale quote while the panel looks
   operational is the worst one possible.

---

## Comparability and sorting

**Only comparable things go side by side.** Two numbers next to each other read
as a pair. If they are computed over different populations, you get a false
conclusion nobody ever stated: «вложено $35 410» next to «достижимо $17 452»,
where the second one covers 62% of positions, reads as «мы в минусе вдвое».

If you put up a pair — bring them to one population, or label both, or separate
them.

**A funnel beats a total.** `N bought → N sold ($X) → N waiting ($Y) → N with no
data` shows the number, and its population, and the remainder we know nothing
about. The reader cannot mistake a part for the whole.

**A qualifier appears exactly where its absence would cause a mistake.** If the
strict subset differs from the overall figure — a second line, muted. If it does
not differ — do not show it at all.

**Sorting is an assertion.** By ranking on a number the page says: "it can be
trusted enough that decisions are worth making on it". Rank only by what you
stand behind. A number that is doubtful but useful — show it, do not sort by it.

---

## Emptiness

`—` in a cell is three different facts, and the reader needs precisely his one:

- **we do not know** (did not ask, quota, refusal) → "a live request will give
  the price";
- **we know there is nothing** → "there are no orders at this float";
- **not applicable** → "outside the tracked base".

Silence of one and the same shape erases the difference between "did not look"
and "empty", and those are different decisions: the first is cured by a retry,
the second is not.

Separately distinguished are **"not started yet"** and **"the filters returned
nothing"**:

```
No accounts. Add one to start trading.        ← empty because nothing was started
No orders match the current filters.          ← empty because of the filtering
```

An empty list caused by filters has to **list the active filters and offer a
reset button**. Otherwise it reads as "the data is gone".

**Loading and emptiness are one cell with changing text, not two elements.** Two
elements with independent `display` will drift apart sooner or later, and the
screen will lie: it will show "nothing here" while the data is still in flight.

---

## Density

A flat table works up to a hundred rows. Past that you need filtering, and it is
already written in the ecosystem — the `web/v2/js/lib/` library (the reference
for completeness is `DmTrading`):

```
fmt.js      money and time; the unit in the function name
filter.js   FilterBar: search + sort + tabs + badges with COUNTERS
group.js    stacks of identical positions, expandable
modal.js    confirmations and forms
live.js     a bus over WS — updates without redrawing everything
status.js   state badges with priority and explanation
store.js    state that survives F5
```

Copy the missing modules from there instead of writing your own: sixty lines of
your own instead of `FilterBar` means no search, no counters, no filter memory,
and one more dialect on top.

Four rules for filtering:

1. **A counter on a filter is half of the navigation.** Where to look is visible
   before the click.
2. **Counters are honest — computed BEFORE the chip's own filter applies.**
   Otherwise an enabled filter shows its own number and stops being navigation.
3. **The filter matches exactly what the badge counts.** A divergence gives a
   counter of "5" and a list of two rows.
4. **Filtering survives a reload, selection does not.** A filter is the working
   environment, a selection is an intent for one run. Keep the tab in the
   address: the link can be forwarded, and F5 does not throw you back to the
   first one.

---

## Progress

**Progress per unit of work, not one spinner.** Thirteen accounts, one of them
hung: a shared spinner hides that, a row per account shows it. A unit that fell
over does not bring down the rest, and the panel shows what did arrive.

A long operation names **the phase and the time within the current phase**, not
the total: `Loading our purchases… 3s` is more informative than `27s`.

A wait costing more than a couple of seconds — state the price up front:
`loading… (the first request pulls the ladders, ~10–20s)`.

---

## Actions and money

### Plan → confirmation → outcome

1. **The plan** — what will happen, at what price, how much lands in hand. The
   same numbers as in the row.
2. **The confirmation repeats the NUMBERS, not the intent.** Not "Are you
   sure?" but "Sell for 550¢, 539¢ in hand". For a batch — the list of positions
   and **the total commitment**.
3. **The outcome** — in the same place the click happened.

In addition, all of it proven in practice:

- **The button carries the amount**: `Send $12.40` instead of `Send`. The
  confirmation starts before the modal does.
- **Buttons are named by outcome**, not "Yes/No": `Keep orders` / `Yes, cancel`.
  A slip of the mouse stops being a catastrophe.
- **The verb turns into a process and disables both buttons**: `Delist` →
  `Delisting…`. A double click on a network operation becomes impossible, and on
  a failure the modal does not close — the state is not lost.
- **A dangerous action always comes paired with a safe one**: `Dry run` /
  `Send LIVE`. A "try it" button alongside makes "do it" a deliberate choice.
- **Snapshot the fields before the `await`** — otherwise the success message
  will name the wrong account if the user managed to switch.
- **A success status fades on its own, an error one does not.** A `Sent` still
  hanging an hour later is indistinguishable from one just completed.

### A mutation has three outcomes, not two

Success, failure and **unknown**. The third has to be a separate state: it is
never retried automatically, it is resolved by reconciliation.

From this it follows:

- the interface shows a counter of unknowns and the path to resolving them:
  `Unknown outcomes: 3 — never retried automatically, resolve them with Reconcile`;
- the check is offered **only** where the outcome is unclear;
- the check's result is phrased as an instruction: `did NOT go through — safe to
  resend`, not "found: false";
- **the lock is restored from the server log, not from the tab's memory.**
  F5 is the perfect moment to send the money a second time.

### Friction is proportional to risk

The irreversible demands a confirmation with numbers. The reversible demands
nothing — do not make anyone confirm a filter.

The most common mistake is friction standing in the wrong place: deleting a row
asks, while switching live trading on takes one click. Check it like this:
**order the page's actions by the cost of a mistake and compare that with where
the questions stand.**

### Locks are named out loud

If the path to money is closed by three conditions — write exactly that: "LIVE
requires a key, a flag in the settings and live in the request itself — three
locks". The operator has to know how many doors stand between him and spent
money.

A disabled button **explains the reason in place** (`title`) instead of merely
going dim.

---

## System state

The machine's mode is visible at all times, in the header: dry run or live, taps
open or shut, data fresh or stale. Not as a pop-up notification.

**The sign of liveness is the last event and its age, not a flag.** A boolean
"enabled" lies: the rule is enabled while the scheduler stands still. The line
`Activity: $1.230 → $1.220 · 12s ago` never lies: "12s ago" — it works,
"2h ago" or "—" — something is worth checking.

An error **dims the numbers** instead of leaving them up. A stale number next to
the word "error" will be read as fresh.

---

## Words

Interface text is English, sentence case, active voice.

Name things the way the reader knows them, not the way they are built inside:
"cost basis", not "purchase_source join". Write what will happen, not what kind
of function this is. A label marks, an example shows, and nothing does two jobs
at once.

The name of an action does not change along the way: the `Sell` button → the
`Sold` toast, not `Listed`.

A failure and an empty screen are direction, not mood. A failure says **what
happened and what to do**. An empty screen invites an action.

A failure comes in two kinds, and they must not be confused: **blocking**
("Amount exceeds available balance") and **warning** ("Balance is stale —
refresh before sending"). The second is shown but does not forbid the action.

The scope of an action is named honestly: `View cleared (server buffer
untouched)`, `Balances refresh queued` — "queued", not "done".

---

## Where to spend boldness

The palette, the fonts, the corner radii, the shadows are **fixed** — that is
the ecosystem's dictionary. Boldness is spent on information architecture: what
to raise to the top, what to collapse, what to show without being asked, which
one thing this page does better than anything else.

The boilerplate answer any panel slides into is **four stat cards on top and a
flat table under them**. If that is exactly what came out, ask what it followed
from besides habit. Sometimes it really does follow; then leave it that way, but
deliberately.

A technique worth remembering: **draw instead of writing**. A basket's range as
a bar with a scale reads instantly, while `0.00–0.07` in a column reads slowly.
And **express it in multiples of the base, not only in money**: `×1.4` answers
"what does a good float cost", an absolute price does not.

---

## Process

1. Formulate the page's job (step 0).
2. Look at how a neighbouring bot solved something similar — references below.
3. Sketch the architecture **in text or ASCII**: what follows what and why.
   Cheap to throw away, expensive to lay out again.
4. Build it out of the existing bricks.
5. Go through the checklist. A divergence gets fixed before showing the owner.

## References: where to look at a working example

| Technique | Where |
|---|---|
| The unit in the formatter's name | `DmTrading/web/v2/js/lib/fmt.js` |
| Filtering with honest counters, filter memory | `DmTrading/web/v2/js/lib/filter.js` |
| State badges with priority and explanation | `DmTrading/web/v2/js/lib/status.js` |
| An edit marker that fades once the bot has seen it | `DmTrading/web/v2/js/lib/modified.js` |
| Confirmation with a list and the total commitment | `BuyOrderBot/web/v2/js/orders.js` |
| Dry run on its own button, `before → applied` | `BuyOrderBot/web/v2/js/analytics.js` |
| Preview of a run's cost before the click | `CSFParser/web/v2/js/settings.js` |
| Three outcomes, the lock from the server log, `Check` | `CSGOMarketParser/web/accounts.html` |
| Progress per account instead of a spinner | `CSGOMarketParser/web/js/relist/` |
| Liveness as "last event + age" | `CSGOMarketParser/web/js/relist/auto-relist.js` |
| A staleness threshold with colour dimming | `CSGOMarketParser/web/accounts.html` |
| Three locks named in the interface; a plan's TTL | `BuffTrah/web/index.html`, `app.js` |
| `null` ≠ `0` in money; chips for filter-out reasons | `BuffTrah/web/app.js` |
| A funnel and a strict subset under the total | `GWS_Ltd/web/analytics.js` |
| A data-freshness panel broken down by source | `GWS_Ltd/web/analytics.html` |

Line numbers are left out on purpose: they drift. Search by the technique's name.

## Checklist before handing over

- [ ] The page's job is named in one sentence without the conjunction «и»
- [ ] Every number has an answer to the four questions; doubtful ones are not sorted by
- [ ] The unit is baked into the function name; `null` differs from zero
- [ ] Numeric columns: mono, right edge, `tabular-nums`, fixed decimal places
- [ ] The age of the data has a threshold, and the threshold changes the appearance
- [ ] Neighbouring numbers are comparable or else labelled
- [ ] Every `—` explains which kind of emptiness it is; an empty filter offers a reset
- [ ] Loading and emptiness are one cell, not two elements
- [ ] A list longer than a hundred rows has filtering with counters; filtering survives F5
- [ ] A money action: plan, confirmation with numbers, three outcomes
- [ ] Friction is proportional to the cost of a mistake — verified by ordering the actions
- [ ] The mode and the locks are visible in the header; a disabled button names the reason
- [ ] Not one hardcoded colour, font or padding — tokens only
- [ ] Works from the keyboard, focus is visible, does not fall apart on a narrow screen
- [ ] Remove one element and check whether it got worse
