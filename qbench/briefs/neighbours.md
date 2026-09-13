# How code is added here

Before writing into a package, read the package's `__init__` and two sibling modules of the kind you are about to add. Your module must be indistinguishable from them: same imports, same logger idiom, same error types, same shape of test. If the package has a mechanism for extending itself, use it; do not bypass it with a branch elsewhere. Reuse the shared fixtures in `tests/conftest.py`. If the repository keeps a changelog, add your line.
