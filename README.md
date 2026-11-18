<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/tesseraline/invariants/production/assets/mark-dark.png">
    <img src="https://raw.githubusercontent.com/tesseraline/invariants/production/assets/mark-light.png" alt="tesseraline" width="220">
  </picture>
</p>

<p align="center">
  <a href="https://pypi.org/project/tesseraline-invariants/"><img alt="PyPI version" src="https://img.shields.io/pypi/v/tesseraline-invariants?label=PyPI&style=flat-square&labelColor=f2efe9&color=1b1b1b"></a>
  <a href="https://github.com/tesseraline/invariants/blob/production/LICENSE.md"><img alt="License: PolyForm Noncommercial 1.0.0" src="https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-1b1b1b?style=flat-square&labelColor=f2efe9&color=1b1b1b"></a>
  <img alt="Python 3.12+" src="https://img.shields.io/badge/python-3.12%2B-1b1b1b?style=flat-square&labelColor=f2efe9&color=1b1b1b">
  <img alt="Typed" src="https://img.shields.io/badge/typing-py.typed-1b1b1b?style=flat-square&labelColor=f2efe9&color=1b1b1b">
</p>

# tesseraline-invariants

**Know when a change breaks a business rule.**

```console
$ pip install tesseraline-invariants
```

A function makes promises about its output: it never returns a credential, it keeps every number of its input, its
result adds up. Write the promise next to the function; `invariants check` runs the function on many inputs and
says, with a minimal failing input, when a later change breaks it.

```python
from dataclasses import dataclass
from tesseraline_invariants import Secret, invariant, never_contains, preserves, holds


@dataclass(frozen=True, slots=True)
class WriteHandle:
    table: str
    credentials: Secret[str]


@invariant(never_contains(Secret), dry_run=True)
def to_query_json(handle: WriteHandle) -> str: ...


@invariant(preserves("numbers", "dates"), dry_run=True)
def restyle(text: str) -> str: ...


@invariant(holds(lambda inp, out: out.total == sum(inp.items)), dry_run=True)
def summarize(order: Order) -> Summary: ...
```

```console
$ invariants check      # 0 all promises hold, 1 a promise broke, 2 a promise was removed, 3 configuration error
$ invariants list       # every promise, where it lives, whether it can be checked
$ invariants lock --update   # record the current promises in invariants.lock (review the diff)
```

```console
$ invariants impact --since main          # which promises a change may affect (from imports; never "safe")
$ invariants check --since main           # check only those; the lock is still compared with every promise
$ pytest --invariants                     # the same check as test items (opt-in)
$ semgrep --metrics=off --disable-version-check --config "$(invariants rules)" src/   # point at exits that bypass promises
```

## Install

```console
$ pip install tesseraline-invariants                 # production: Secret and @invariant, standard library only
$ pip install "tesseraline-invariants[check,scan]"   # CI and developers: invariants check, pytest plugin, scan
```

Block a commit and a push while a promise is broken or an exit is unguarded, in `.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/tesseraline/invariants
  rev: v0.0.1
  hooks:
    - id: invariants-check   # promises hold (strict)
    - id: invariants-scan    # the Semgrep rules for unguarded exits
```

Install the hooks for both moments: `pre-commit install --hook-type pre-commit --hook-type pre-push`.

## Why not a property test?

- The promise sits next to the code it protects, so nobody has to remember to write the test.
- `never_contains` plants canary values in every secret field and searches the output for them, also JSON-escaped,
  URL-encoded and base64-encoded.
- `invariants.lock` records the promises themselves: deleting a decorator to get a green build fails the check.
- Every check leaves an audit record: which promise, which code version, which result.

## What it does not do (read this first)

- It calls only functions whose author wrote `dry_run=True`, meaning "safe to run when every dependency is a fake".
  Every other promise is reported as not checked; it never counts as a pass.
- The network is blocked during a check. Writes to files outside the temporary working directory are **not**
  prevented in v0.1.
- A secret that is hashed or truncated before it leaves cannot be found by a canary search.
- No runtime checking in production in v0.1; no model-based judging, ever: checks are code.
- `lock --update` can be run by anyone; the protection is that the change shows in review.

## Inputs: give your types factories

A check calls each `dry_run=True` function with saved regressions first, then values from your factories,
then values Hypothesis builds from the types. Random values rarely look like real data: a `preserves`
promise on text needs real sentences to mean anything. Name a factory per type in settings (below); the
`examples/` folder shows the difference.

## Settings

`pyproject.toml`:

```toml
[tool.invariants]
modules = ["myapp.exporters", "myapp.reports"]   # imported to collect promises
strict = true                                     # "not checked" fails the run
secret_types = ["myapp.auth:Token"]               # your own secret types ("module:Class")
secret_fields = ["*password*", "api_key"]         # by name: heuristic, opt-in

[tool.invariants.factories]
"myapp.models:WriteHandle" = "myapp.examples.data:example_handles"
"builtins:str" = "myapp.examples.data:example_sentences"

[tool.invariants.fakes]
"myapp.ports:Mailer" = "myapp.examples.fakes:FakeMailer"   # Protocol-typed dependencies
```

Examples of code the check catches and of the same code done right: `examples/README.md`.

## Licence

PolyForm Noncommercial 1.0.0 (`LICENSE.md`). Personal and other noncommercial use is free. Use by a company, or
any use with a commercial purpose, needs a separate commercial licence: contact Tesseraline through
<https://github.com/tesseraline>.

Required Notice: Copyright 2026 Tesseraline (https://github.com/tesseraline)

No permission is given to use this code or its documentation to train or evaluate machine learning or AI models,
for any purpose; text and data mining for that purpose is reserved (Article 4(3), Directive (EU) 2019/790). See
`LICENSE.md`.

