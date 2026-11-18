# Getting started

## Install

```console
$ pip install tesseraline-invariants                 # production: Secret and @invariant, standard library only
$ pip install "tesseraline-invariants[check,scan]"   # CI and developers: invariants check, pytest plugin, scan
```

The decorator has no dependencies, so production images carry no test tooling.

## Write a promise

Mark secret fields, then state what the function promises. `dry_run=True` is your statement that the function
is safe to call when every dependency is a fake; without it the promise is listed but never called.

```python
@invariant(never_contains(Secret), dry_run=True)
def to_query_json(handle: WriteHandle) -> str:
    return json.dumps({"table": handle.table})
```

## Tell the check where to look

```toml
# pyproject.toml
[tool.invariants]
modules = ["myapp.exporters"]
strict = true
```

## Run it

```console
$ invariants check
PASS   myapp.exporters:to_query_json#never_contains:...  (62 calls)
1 passed, 0 broken, 0 not checked; exit 0
$ invariants lock --update   # record the promises; commit invariants.lock
```

A broken promise prints the field the secret came from and how it was encoded, saves the minimal failing input
and exits 1. The secret itself is never printed.

The repository's `examples/caught` and `examples/passing` show the same functions with real mistakes and done
right.
