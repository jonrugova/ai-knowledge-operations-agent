# Security

## Safe handling

- Never commit `.env` files, passwords, API keys, session secrets, database URLs, or other credentials.
- Use environment variables or the workspace secrets manager for secrets.
- If a credential is accidentally exposed, rotate it immediately and remove it from all repository history where applicable.
- Do not upload private company knowledge, customer information, internal documents, approvals, executions, traces, or screenshots to a public demo.

## Scope and limitations

- The demo RBAC login is portfolio-stage authentication, not enterprise identity management.
- Protected actions are demo/local workflows unless explicitly connected to external systems.
- The sample knowledge file is fictional and intended only for portfolio demonstration.

Please report security issues privately rather than publishing credentials or sensitive data.