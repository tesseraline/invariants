# Configuration

All settings live in `pyproject.toml`.

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

- **factories** return realistic example values for a type.
- **fakes** stand in for dependencies typed as a `Protocol`; the check gives each call fresh fakes and searches
  what they received.
