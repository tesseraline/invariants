# Promises

## Marking secrets

A field counts as secret when it is marked in any of these ways:

- `Secret[str]` or `Annotated[str, Secret]`;
- Pydantic `SecretStr` and `SecretBytes`;
- your own types, listed in `secret_types` (`"module:Class"`);
- field names matching `secret_fields` patterns (a heuristic, opt-in).

A parameter counts the same way when its own annotation is marked, for example
`def entry(level: str, key: Secret[str] | None = None)`. The check then plants the canary in that parameter.

## `never_contains(Secret)`

No secret planted in the input appears in the output. The check fills every secret field with a canary value and
searches the output for it in plain text, JSON-escaped, URL-encoded and base64-encoded. It also searches what the
function logs and what each fake dependency received during the call.

## `preserves("numbers", "dates", "quotes", "links", both_ways=True)`

Every number, date, quote or link of the input is still in the output. With `both_ways=True` (the default) the
output may not add items either. Thousands separators and the word "percent" are normalised, so "15%" equals
"15 percent" and "1,000" equals "1000".

## `holds(predicate, name="")`

A predicate over the input and the output is true, called as `predicate(input, output)`. The lock entry hashes
the predicate's source, so an edit shows in review.

```python
@invariant(holds(lambda inp, out: out.total == sum(inp.items), name="total adds up"), dry_run=True)
def summarize(order: Order) -> Summary: ...
```

## Inputs

A check calls each `dry_run=True` function with saved regressions first, then values from your factories, then
values Hypothesis builds from the types. Random values rarely look like real data, so name a factory for the types
that matter (see [Configuration](configuration.md)).
