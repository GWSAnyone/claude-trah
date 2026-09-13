# How code is written here

Code lives where its callers are, next to the sibling that does the same kind of thing, and it reads like that sibling: same imports, same error types, same log idiom, same comment density. Before writing, read the package's `__init__` and two siblings; the mechanism the package already uses to extend itself is the one you use.

Extend before you add. A helper, type or fixture that already exists is reused, not re-implemented beside itself. A new name comes from this codebase's vocabulary, not from the type of the value.

One concern per function. An error is raised in the package's own types and handled where it can be decided, not swallowed on the way. No configuration knobs, fallbacks, or abstractions the task did not ask for — three similar lines beat a premature helper.

A comment says why, and what was measured; the code already says what. A test proves a behaviour and uses the shared fixtures; it is shaped like the neighbouring tests. If the repository keeps a changelog, the change gets its line.

Done means the project's own checks pass, and the diff is the smallest one a senior maintainer would merge without a comment.
