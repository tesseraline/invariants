# Commands

| Command | What it does |
|---|---|
| `invariants check` | runs every promise; `--strict` makes "not checked" fail |
| `invariants check --since REF` | checks only promises a change since `REF` may affect; the lock is still compared with every promise |
| `invariants impact --since REF` | lists the promises a change may affect, from imports (never called "safe") |
| `invariants list` | every promise, where it lives, whether it can be checked |
| `invariants lock --update` | records the current promises in `invariants.lock` |
| `invariants rules` | prints the path of the Semgrep rules for unguarded exits |
| `invariants scan [paths] [--exclude PATTERN]` | runs those rules offline (no metrics, no version check) |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | every promise holds |
| 1 | a promise broke |
| 2 | a promise was removed or changed without `lock --update` |
| 3 | configuration or import error |
