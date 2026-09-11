# MCP Reverse Proxy

> Bridge MCP servers to remote ContextForge gateways over TLS. Supports SSE, stdio, Streamable HTTP, and WebSocket transports.

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)&nbsp;
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)&nbsp;
[![Async](https://img.shields.io/badge/async-await-green.svg)](https://docs.python.org/3/library/asyncio.html)

**MCP Reverse Proxy** is a standalone client that connects local or remote [Model Context Protocol](https://modelcontextprotocol.io) (MCP) servers to a remote gateway, such as [ContextForge](https://github.com/IBM/mcp-context-forge), over a persistent, authenticated WebSocket connection. It lets MCP servers that live behind firewalls or on private networks register with a central gateway without opening inbound ports.

## Quick Start

```bash
# Install (Python 3.11+ required)
pip install mcp-reverse-proxy

# Show all options
mcp-reverse-proxy --help

# Bridge a local stdio MCP server to a remote gateway
mcp-reverse-proxy \
  --local-stdio "uvx mcp-server-git" \
  --gateway wss://gateway.example.com/reverse-proxy \
  --token "$GATEWAY_TOKEN"
```

Remote MCP servers can be bridged over Streamable HTTP or SSE instead:

```bash
mcp-reverse-proxy \
  --local-streamable-http https://mcp-server.example.com/mcp \
  --gateway wss://gateway.example.com/reverse-proxy \
  --token "$GATEWAY_TOKEN" \
  --cert /path/to/ca-certificate.pem
```

Configuration can also come from environment variables (`REVERSE_PROXY_GATEWAY`, `REVERSE_PROXY_TOKEN`) or a JSON/YAML config file passed with `--config`.

## Container image

A multi-arch (`linux/amd64`, `linux/arm64`) UBI 10-based image is built from the root `Containerfile` and published to GitHub Container Registry:

```bash
docker pull ghcr.io/contextforge-org/mcp-reverse-proxy:latest

docker run --rm \
  -e REVERSE_PROXY_GATEWAY="wss://gateway.example.com/reverse-proxy" \
  -e REVERSE_PROXY_TOKEN="$GATEWAY_TOKEN" \
  ghcr.io/contextforge-org/mcp-reverse-proxy:latest \
  --local-stdio "uvx mcp-server-git"   # explicit transport - the inert default command only prints usage
```

| Tag | Published when |
| --- | --- |
| `latest` | every push to `main` |
| `X.Y.Z` | a `v*` release tag is pushed (immutable full-version tag; no `v` prefix, no moving aliases) |
| `sha-<commit>` | every push to `main` |

(Prerelease tags such as `v1.2.3-rc.1` publish only the full version tag, e.g. `1.2.3-rc.1` — no `X.Y`/`X` aliases.)

The image runs as non-root (UID 1001) and includes `uv`/`uvx` and `git`, so stdio MCP servers such as `uvx mcp-server-git` work out of the box. Its default command is inert (prints usage via `--help`); bridge a server by passing the full arguments, e.g. appending `--local-stdio "uvx mcp-server-git"`. Note that MCP server packages downloaded at run time (e.g. via `uvx`) are not covered by the image's signature or vulnerability scan — pin them (for example `uvx mcp-server-git==<version>`) for production use. Images are keyless-signed with cosign:

```bash
cosign verify ghcr.io/contextforge-org/mcp-reverse-proxy:latest \
  --certificate-oidc-issuer=https://token.actions.githubusercontent.com \
  --certificate-identity-regexp='^https://github\.com/contextforge-org/mcp-reverse-proxy/\.github/workflows/container\.yml@refs/(heads/main|tags/v.*)$'
```

## Features

- **Multi-transport MCP server connections**: stdio (subprocess), Streamable HTTP (HTTP/2), and SSE
- **WebSocket gateway transport**: persistent connection with TLS (`wss://`) and ping/pong keepalive
- **Two-layer health monitoring**: client-side MCP health checks (via `tools/list`) gate heartbeats, so the gateway detects outages quickly and recovers automatically
- **Automatic reconnection**: configurable retry limits and backoff delays
- **TLS certificate handling**: per-connection CA overrides, inline PEM certificates in config files, and automatic system CA fallback (`cert_utils`)
- **Flexible configuration**: CLI arguments, environment variables, or JSON/YAML config files
- **Structured JSON logging** with configurable log levels
- **Extensible transport abstraction**: new MCP server or gateway transports plug in through abstract base classes without modifying existing code

## Relationship to ContextForge

This project was extracted from [IBM/mcp-context-forge](https://github.com/IBM/mcp-context-forge), where the reverse proxy originated. ContextForge provides the gateway side of the connection: session registration, heartbeat monitoring, and reachability tracking.

A gateway-side integration package, `mcp-reverse-proxy-contextforge`, is planned for this same repository to keep the client and gateway protocol in lockstep.

## Documentation

- [docs/README.md](docs/README.md): architecture, transport abstraction, and health-check strategy
- [USER_README.md](USER_README.md): user guide with installation, TLS configuration, and troubleshooting

## Development

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Run the test suite (pytest with coverage)
pytest

# Lint and type-check
ruff check .
mypy src/
```

Code style and tool configuration (ruff line-length 120, black line-length 120, mypy, pytest) live in `pyproject.toml`.

## Contributing

Contributions are welcome. All commits must be signed off (`git commit -s`) to certify the [Developer Certificate of Origin](DCO.txt). See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

## License

Licensed under the [Apache License 2.0](LICENSE).
