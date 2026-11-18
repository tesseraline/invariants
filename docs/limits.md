# Limits

Read this before relying on a green run.

- Only functions marked `dry_run=True` are called. Every other promise is reported as not checked; it never counts
  as a pass.
- The network is blocked during a check. Writes to files outside the temporary working directory are not
  prevented.
- A secret that is hashed or truncated before it leaves cannot be found by a canary search.
- No runtime checking in production; no model-based judging. Checks are code.
- `lock --update` can be run by anyone; the protection is that the change shows in review.
- Impact analysis follows imports. Dynamic imports and data files are not seen.
