# Changelog

All notable changes to tesseraline-invariants. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/). Before 1.0 a minor version may change the public API.

## [Unreleased]

## [0.0.4] - 2026-11-18

### Added
- A parameter whose own annotation is a secret (`key: Secret[str]`, also `Secret[str] | None`) is checked
  like a secret field: `never_contains` plants a canary in it. Before, such a function was reported as not checked.
  Name patterns from `secret_fields` apply to parameter names too.

## [0.0.3] - 2026-11-18

### Added
- Documentation site, security policy, this changelog.
- CI on every push and pull request; OpenSSF Scorecard; Dependabot for GitHub Actions.
- Each release on GitHub carries the wheel and sdist with a Sigstore signature (`*.sigstore.json`).
- CI checks the locked dependencies for known vulnerabilities (pip-audit).
- A release runs only when the tag is `vX.Y.Z`, equals the package version and has its changelog section.

### Changed
- Semgrep is no longer a dependency (the `scan` extra is gone); install it as its own tool: `uv tool install semgrep`.

## [0.0.2] - 2026-11-18

### Added
- Python 3.12 and `Typing :: Typed` classifiers.

### Changed
- README: the mark at the top, badges, a Development section.
- Examples use neutral sentences for the `preserves` check.

## [0.0.1] - 2026-11-17

### Added
- `Secret`, `@invariant`, and three promises: `never_contains`, `preserves`, `holds`.
- `invariants check`, `list`, `lock --update`, `impact --since`, `check --since`, `rules`, `scan`.
- `invariants.lock`: removing or weakening a promise fails the check (exit 2).
- Canary search in plain, JSON-escaped, URL-encoded and base64 forms.
- Regressions: minimal failing inputs saved and replayed first.
- Audit record per check; network blocked while promised functions run.
- Opt-in pytest plugin (`pytest --invariants`) and Semgrep rules for unguarded exits.
- pre-commit hooks `invariants-check` and `invariants-scan`.

[Unreleased]: https://github.com/tesseraline/invariants/compare/v0.0.4...HEAD
[0.0.4]: https://github.com/tesseraline/invariants/compare/v0.0.3...v0.0.4
[0.0.3]: https://github.com/tesseraline/invariants/compare/v0.0.2...v0.0.3
[0.0.2]: https://github.com/tesseraline/invariants/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/tesseraline/invariants/releases/tag/v0.0.1
