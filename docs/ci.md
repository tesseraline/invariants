# In CI and hooks

## pre-commit

Block a commit and a push while a promise is broken or an exit is unguarded:

```yaml
- repo: https://github.com/tesseraline/invariants
  rev: v0.0.4
  hooks:
    - id: invariants-check   # promises hold (strict)
    - id: invariants-scan    # the Semgrep rules for unguarded exits
```

```console
$ pre-commit install --hook-type pre-commit --hook-type pre-push
```

## pytest

```console
$ pytest --invariants
```

Each promise becomes a test item. The plugin imports nothing beyond pytest until the flag is given.

## Semgrep

```console
$ invariants scan src/
$ semgrep --metrics=off --disable-version-check --config "$(invariants rules)" src/
```

The rules point at exits that bypass promises: a whole object written to JSON or a log, a `repr` in output,
base64 used as if it were hiding, `SELECT *`. Mark an intended exit where it happens, with the reason:

```python
token = base64.b64encode(f"{user}:{password}".encode())  # nosemgrep: invariants-encoding-is-not-hiding - proxy auth header
```
