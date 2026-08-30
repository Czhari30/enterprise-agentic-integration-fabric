# Security policy

## Reporting a vulnerability

Please do not open a public issue for a vulnerability. Use GitHub's private vulnerability reporting
for this repository and include affected files, reproduction steps, impact and a suggested mitigation
when possible.

## Security boundaries

This is a synthetic reference platform. Do not connect it to production APIs, identities, model
endpoints or customer data without implementing the production controls listed in the README and
completing an independent security review.

Never commit API keys, tokens, certificates, personal data or employer information. Use a secrets
manager and workload identity in deployed environments.
