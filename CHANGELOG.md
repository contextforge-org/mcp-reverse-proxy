# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - Unreleased

### Added

- Initial import of the MCP Reverse Proxy from [IBM/mcp-context-forge](https://github.com/IBM/mcp-context-forge), extracted as part of the PR #5417 decomposition. Includes the standalone client package with multi-transport support (stdio, Streamable HTTP, SSE, WebSocket), two-layer health monitoring, TLS certificate handling, and the `mcp-reverse-proxy` console script.
