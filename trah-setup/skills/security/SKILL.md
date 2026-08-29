---
name: security
description: |
  Run a security pass over our own code before it ships: scope it, model the
  threat in three lines, delegate the reading, triage what comes back, and prove
  each fix. Use when the owner says «проверь на безопасность», «посмотри дыры»,
  «можно это выкатывать», before opening a service to the network, when touching
  authentication, payments, uploads or anything that takes user input, and after
  a dependency bump. NOT needed for a one-line question about one function.
---

# A security pass

This is our own code, reviewed before it ships. The job is to find defects and
hand the owner a list he can act on, with a way to check each item himself.

The reading is delegated to `security-reviewer`. This skill is everything
around it: what to point it at, what to do with what it says, and how to know a
fix actually fixed.

## 1. Scope it before you start

"Проверь проект на безопасность" is not a scope, and answering it as asked
produces a shallow sweep that misses the thing that mattered. Narrow to one of:

- a **diff** (what this branch changes),
- a **surface** (the HTTP handlers, the upload path, the auth module),
- a **service** (one deployable unit and its config).

Say the scope out loud at the start and name what you are leaving out. The
owner can widen it; he cannot un-miss what was never looked at.

## 2. Three lines of threat model

Before reading code, answer three questions. They decide what counts as a
finding and what is noise.

- **What is worth taking here?** Money, credentials, someone else's data, compute.
- **Who is the attacker?** An anonymous stranger on the internet, a logged-in
  user reaching for another user's things, or someone who already has the box.
- **Where is the boundary?** The exact line where untrusted input becomes
  trusted. Most defects live within a few files of it.

A finding that no attacker in this model can reach is a note, not a finding.
Say which of the three it failed.

## 3. Delegate the reading

Call `security-reviewer` on the scope. Split by surface when the area is wide:
handlers, auth, storage and configuration are independent tracks and belong to
separate agents running at once.

Brief each one with the threat model above, the boundary, and what is already
known. An agent that does not know what is valuable reports everything at equal
weight.

## 4. Triage — this part is yours, not the agent's

The agent reports everything at every severity on purpose. That is the correct
setting for the reader and the wrong setting for the owner, so you filter.

For each finding, decide in this order:

1. **Is the path real?** Follow the data yourself from source to sink. A finding
   with no reachable path is dropped, not softened.
2. **What does it cost if exploited?** Name the concrete outcome. If you cannot
   name one, the finding is a note.
3. **How hard is it to reach?** Anonymous and remote outranks authenticated,
   which outranks local.

Then order what survives by cost times reachability, and hand the owner **the
short list first**, with the full list underneath. Three real items he will read
beat thirty he will not.

## 5. Prove each fix

A fix is not done because the code changed. For every accepted finding, produce
the check that would have caught it:

- a test that fails on the old code and passes on the new one — best;
- a request or command the owner can run himself — acceptable;
- a reading of the diff — weakest, and say so.

State which of the three you have. «Починил» without one of them is a claim, not
a result.

## 6. What not to do

- **Do not write working exploits.** A proof path and the affected line are the
  deliverable. A runnable attack script is not, even against our own code.
- **Do not fix and report in one breath.** Findings first, so the owner decides
  what gets touched. A security fix that quietly changes auth behaviour is its
  own incident.
- **Do not grade the codebase.** No letters, no scores, no «в целом безопасно».
  Findings, confidence, and what you did not look at.
- **Do not bury the boring ones.** A secret committed to the repository is dull
  and is usually the worst thing on the list.

## Where our own answers already live

Before reporting a configuration finding, check what is deliberate here:
`~/.claude/settings.json` carries the permission denies, and `trah-setup/hooks/`
carries the guards that block destructive commands. A rule that looks missing
may be enforced a layer up.
