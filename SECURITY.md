# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.1.x   | ✅ Prime release   |
| 1.0.x   | ✅ Security fixes only |

## Reporting a Vulnerability

If you discover a security vulnerability within Playwright-Omni, please report it via:

1. **Private GitHub Security Advisories** (preferred)
   - Navigate to the repository → Security → "Report a vulnerability"
   - https://github.com/liang030502-prog/playwright-omni/security/advisories

2. **Email** (alternative)
   - Send directly to the maintainer at `liang030502@gmail.com`

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact assessment
- Suggested remediation (if any)

**Response timeline**: We aim to acknowledge within 48 hours and provide a status update within 7 days.

## Security Best Practices

When using Playwright-Omni:

- **Never** hardcode API keys in source files — use environment variables
- **Review** `api_config.py` and ensure `.env` files are excluded from version control
- **Run** `python scripts/preflight_check.py` before each session to validate environment integrity
- **Restrict** browser permissions to the minimum required for your automation tasks
