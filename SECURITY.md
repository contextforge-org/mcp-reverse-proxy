# Security Policy

## Reporting a Vulnerability

Report security issues privately through
[GitHub Security Advisories](https://github.com/contextforge-org/mcp-reverse-proxy/security/advisories/new)
on this repository. Please do not open public issues for security reports.

The MCP Reverse Proxy client handles TLS certificates and bearer tokens. If you
find a problem in credential handling (token storage, logging of secrets,
certificate validation, or TLS configuration), report it privately through a
security advisory rather than a public issue.

We aim to acknowledge reports within a few days and will coordinate disclosure
with you.

## Supported Versions

Security fixes are applied to the latest release line only. There are no
backported security patches or long-term support branches.

| Version | Supported          |
|---------|--------------------|
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Security Notes for Deployment

- Always use TLS (`wss://` for the gateway, `https://` for remote MCP servers) in production.
- Protect bearer tokens: pass them via environment variables or a config file with restrictive permissions, never on shared command lines.
- Use `--cert`, `--mcp-cert`, or `--gateway-cert` to pin CA certificates for self-signed or private-CA deployments instead of disabling verification.
- `PYTHONHTTPSVERIFY=0` disables SSL verification and must only be used in trusted development environments.
- The client spawns local MCP servers as subprocesses (stdio transport). Only bridge servers you trust.
- This project is provided as-is, on a best-effort maintenance basis. Perform your own security evaluation before production use.
