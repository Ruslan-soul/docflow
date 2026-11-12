# Security policy

## Supported versions

Security fixes are made on the latest state of the `main` branch. No older
release line is currently maintained.

## Reporting a vulnerability

Please do not publish exploit details in a public issue. Use GitHub's
[private vulnerability reporting](https://github.com/Ruslan-soul/docflow/security/advisories/new)
when available, or contact the repository owner through their GitHub profile.
Include the affected version, impact, and steps to reproduce. Do not attach real
customer documents or personal data; use a minimal synthetic example instead.

DocFlow is a local, single-user MVP. Do not expose its Streamlit server to an
untrusted network. Uploads are untrusted input even when the app runs locally.
