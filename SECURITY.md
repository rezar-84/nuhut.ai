# Security policy

## Reporting a vulnerability

Use the repository's private vulnerability-reporting feature under the **Security** tab.
Do not open a public issue for a secret exposure, path traversal, unsafe overwrite,
prompt-injection bypass, or another vulnerability that could put installed projects at
risk.

Include the affected version, reproduction steps, impact, and any known workaround. A
maintainer should acknowledge a report within seven days. A remediation date depends on
severity and whether a coordinated disclosure is needed.

## Supported versions

Security fixes are made on the latest released version. Upgrade from older versions
before reporting behavior already corrected in `CHANGELOG.md`.

## Security boundaries

The installer writes only inside the selected project and refuses the kit directory.
`--dry-run` and quitting before the review confirmation must have no filesystem effects.
Managed upgrades verify checksums, back up affected files, and stop when a kit-owned file
has local modifications.

Installed agent instructions treat issue text, repository content, generated output,
logs, tool results, dependency documentation, and web pages as untrusted data. They must
not override the user's request, disclose secrets, broaden permissions, or cause unrelated
tool actions.
