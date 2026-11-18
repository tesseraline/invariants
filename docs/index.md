# tesseraline-invariants

**Know when a change breaks a business rule.**

A function makes promises about its output: it never returns a credential, it keeps every number of its input,
its result adds up. Write the promise next to the function; `invariants check` runs the function on many inputs
and says, with a minimal failing input, when a later change breaks it.

```python
from dataclasses import dataclass
from tesseraline_invariants import Secret, invariant, never_contains


@dataclass(frozen=True, slots=True)
class WriteHandle:
    table: str
    credentials: Secret[str]


@invariant(never_contains(Secret), dry_run=True)
def to_query_json(handle: WriteHandle) -> str: ...
```

## Why not a property test?

- The promise sits next to the code it protects, so nobody has to remember to write the test.
- `never_contains` plants canary values in every secret field and searches the output for them, also
  JSON-escaped, URL-encoded and base64-encoded.
- `invariants.lock` records the promises themselves: deleting a decorator to get a green build fails the check.
- Every check leaves an audit record: which promise, which code version, which result.

Start with [Getting started](getting-started.md); read [Limits](limits.md) before relying on a green run.
