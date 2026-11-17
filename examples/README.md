# Examples

`tesseraline-invariants/examples/README.md` - two small projects with the same functions: one with real
mistakes the check catches, one written right that passes. Run them from this repository:

```console
$ cd examples/caught  && uv run --project ../.. invariants check   # exit 1
$ cd examples/passing && uv run --project ../.. invariants check   # exit 0
```

## caught/ - what the check finds

| Function | Promise | Mistake | Result |
|---|---|---|---|
| `exports.to_query_json` | `never_contains(Secret)` | the handle's `repr` (with its credentials) is written into the query JSON | BROKEN (plain) |
| `exports.debug_header` | `never_contains(Secret)` | credentials base64-encoded in a header; base64 is not encryption | BROKEN (base64) |
| `texts.shorten` | `preserves("numbers")` | percentages dropped while shortening | BROKEN, lost `15%` |
| `texts.summarize` | `holds(total adds up)` | only the first three lines are added | BROKEN, input shrunk to four lines |
| `unchecked.send_to_warehouse` | `never_contains(Secret)` | not marked `dry_run=True`, so it is never called | NOT CHECKED (never a pass) |
| `unchecked.with_telemetry` | `never_contains(Secret)` | calls the network during the check | NOT CHECKED, host named |

```text
BROKEN       caught_example.exports:debug_header#never_contains:...: secret from handle.credentials found in the output (base64); minimal input saved (...)
BROKEN       caught_example.exports:to_query_json#never_contains:...: secret from handle.credentials found in the output (plain); minimal input saved (...)
BROKEN       caught_example.texts:shorten#preserves:...: numbers: 1 lost, 0 new; minimal input saved (...)
             numbers: lost ['15%'], new []
BROKEN       caught_example.texts:summarize#holds:...: total adds up is false; minimal input saved (...)
NOT CHECKED  caught_example.unchecked:send_to_warehouse#never_contains:...: dry_run not declared
NOT CHECKED  caught_example.unchecked:with_telemetry#never_contains:...: attempted network access to telemetry.example
0 passed, 4 broken, 2 not checked; exit 1
```

The failing inputs are saved in `invariants/regressions/` and replayed first on the next run. The reports
never show a secret: only the field it came from and how it was encoded.

## passing/ - the same functions done right

- `to_query_json` and `debug_header` build their output from named fields (the table), never from the whole
  object.
- `shorten` tidies spaces and keeps every number; `summarize` adds every line.

```text
PASS         passing_example.exports:debug_header#never_contains:...  (62 calls)
PASS         passing_example.exports:to_query_json#never_contains:...  (62 calls)
PASS         passing_example.texts:shorten#preserves:...  (63 calls)
PASS         passing_example.texts:summarize#holds:...  (60 calls)
4 passed, 0 broken, 0 not checked; exit 0
```

## What the examples also show

- **Factories matter.** Both `pyproject.toml` files name a factory for `str` with real sentences. Without
  it, Hypothesis's random strings almost never contain "rose 15%", and the broken `shorten` passed: a weak
  check, not a proof. Give every type a factory with realistic values.
- **Deleting a promise is not a way out.** Remove a decorator in `passing/` and run the check: exit 2,
  "REMOVED", until `invariants lock --update` records it, which shows in the diff of `invariants.lock`.
