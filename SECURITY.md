# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| latest (main) | ✅ |

## Reporting a Vulnerability

**Please DO NOT open a public GitHub issue for security vulnerabilities.**

Email the maintainers privately at the address listed on the GitHub profile. You should expect a response within **48 hours**.

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce
- Any suggested mitigations (optional)

## Secret Management

This project **never** commits secrets to version control. The following practices are enforced:

### What We Do
- All credentials are stored in `.env` files that are **gitignored** at every level
- An `.env.example` template (with blank values) is committed as the developer guide
- CI/CD secrets are stored in **GitHub Actions Secrets** (not in code)
- Production secrets are managed via a secrets manager (e.g. Doppler / AWS Secrets Manager / Vault)

### For Developers
1. Copy `.env.example` → `.env` and fill in your local values
2. Run `git status` before every commit to confirm no `.env` file is staged
3. Use `git secret` or `pre-commit` hooks to add an extra safety net locally

### If a Secret Is Accidentally Committed
1. **Immediately rotate/revoke** the leaked credential in the service provider dashboard
2. Remove the secret from git history using `git filter-repo` (not `git filter-branch`)
3. Force-push the cleaned history
4. Audit access logs on the affected service

## Dependency Scanning

We recommend running `pip-audit` (Python) and `npm audit` (Node) before each release.
