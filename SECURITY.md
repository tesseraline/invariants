# Security policy

## Supported versions

Only the latest release on PyPI receives security fixes.

## Reporting a vulnerability

Please report privately through GitHub: **Security → Report a vulnerability** on
<https://github.com/tesseraline/invariants>. Do not open a public issue for a vulnerability.

Include what you found, how to reproduce it and which version you used. We aim to confirm receipt within
five working days and to agree a disclosure date with you once a fix is ready.

## What counts

- A promise reported as held when the function leaks a planted secret, for an encoding the documentation says is
  searched (plain, JSON-escaped, URL-encoded, base64).
- The check reaching the network while promised functions run.
- A report, log or audit record that contains a secret value.
- Anything in the published package or release process that could be tampered with.

Known limits listed in the documentation (hashed or truncated secrets, file writes outside the temporary folder)
are not vulnerabilities.

## Releases

Releases are built and published by GitHub Actions through PyPI Trusted Publishing; each file on PyPI carries a
provenance attestation tied to this repository's `publish.yml`.
