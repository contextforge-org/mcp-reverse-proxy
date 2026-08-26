# ----------------------------------------------------------------------------
# MCP Reverse Proxy - client/test image (multi-stage builder -> runtime).
# UBI 10 throughout: builder = ubi10/ubi-minimal + python3.12 RPMs (no full
# python-312 s2i image exists for UBI 10 - Red Hat catalog verified 404),
# runtime = ubi10/python-312-minimal. Pattern follows IBM/mcp-context-forge:
# overridable base-image ARGs, venv built in builder, copied to runtime,
# non-root user, OCI labels.
# ----------------------------------------------------------------------------

# uv is delivered by copying its static binaries out of the official image.
# PINNED BY DIGEST (supply chain): resolve the current digest of the uv 0.9
# line and replace <UV_DIGEST> below; resolved version: uv 0.9.30. Docker does
# NOT support inline comments on ARG lines - keep this note as full-line
# comments only.
#   docker buildx imagetools inspect ghcr.io/astral-sh/uv:0.9
ARG UV_IMAGE=ghcr.io/astral-sh/uv@sha256:538e0b39736e7feae937a65983e49d2ab75e1559d35041f9878b7b7e51de91e4
# Base tags: floating Red Hat tags (deliberate - CVE rebuilds flow in; see
# Scope OUT). Both MUST resolve before building; todo-1 acceptance enforces:
#   docker buildx imagetools inspect registry.access.redhat.com/ubi10/ubi-minimal:latest
#   docker buildx imagetools inspect registry.access.redhat.com/ubi10/python-312-minimal:latest
ARG PYTHON_BUILDER=registry.access.redhat.com/ubi10/ubi-minimal:latest
ARG PYTHON_RUNTIME=registry.access.redhat.com/ubi10/python-312-minimal:latest

FROM ${UV_IMAGE} AS uv

# ------------------------------------------------------------------ builder
FROM ${PYTHON_BUILDER} AS builder

# UBI 10 ships no full python-312 s2i image (see header), so the builder is
# ubi-minimal plus the Python 3.12 RPMs - the mcp-context-forge wheel-image
# pattern. Dependencies install from the COMMITTED hash-pinned lock file
# (requirements-container.txt - generated in todo 1 step (a); pure-wheel
# closure, no compilers needed. Contingency if a dep ever builds from
# source: add python3.12-devel gcc to the microdnf line.
USER root
WORKDIR /build

RUN microdnf install -y --nodocs --setopt=install_weak_deps=0 \
      python3.12 python3.12-pip \
 && microdnf clean all

COPY pyproject.toml USER_README.md LICENSE requirements-container.txt ./
COPY src/ ./src/

# Locked closure: hash-verified deps + pinned build backend (both from the
# lock file); the project wheel builds with --no-build-isolation against
# THOSE pinned build tools, then installs with --no-deps. No `pip install -U
# pip`, no loose resolution - the Python dependency closure is hash-pinned
# (the floating UBI base and RPM inputs are deliberately NOT - see Scope OUT).
RUN python3.12 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements-container.txt \
 && /opt/venv/bin/pip wheel --no-cache-dir --no-deps --no-build-isolation --wheel-dir /dist . \
 && /opt/venv/bin/pip install --no-cache-dir --no-deps /dist/*.whl \
 && /opt/venv/bin/pip check

# ------------------------------------------------------------------ runtime
FROM ${PYTHON_RUNTIME} AS runtime
# NOTE: the s2i runtime base's image config inherits EXPOSE 8080/tcp. It is
# inert metadata for this client (nothing listens); OCI/Docker has no
# UNEXPOSE directive, so it is accepted and documented, not removed.

ARG VERSION=dev
ARG REVISION=unknown

USER root

COPY --from=uv /uv /uvx /usr/local/bin/
COPY --from=builder /opt/venv /opt/venv

# git: the documented run example uses `uvx mcp-server-git`, whose GitPython
# dependency shells out to the git executable. ca-certificates for TLS.
# Writable HOME + uv cache: uvx downloads MCP server packages at run time
# and the runtime user is non-root (group-0 per UBI/OpenShift convention).
RUN microdnf install -y --nodocs --setopt=install_weak_deps=0 git ca-certificates \
 && microdnf clean all \
 && mkdir -p /home/default /tmp/uv-cache \
 && chown -R 1001:0 /home/default /tmp/uv-cache \
 && chmod -R g=u /home/default /tmp/uv-cache

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:/usr/local/bin:$PATH" \
    HOME=/home/default \
    UV_CACHE_DIR=/tmp/uv-cache \
    BASH_ENV= \
    ENV= \
    PROMPT_COMMAND= \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

LABEL name="mcp-reverse-proxy" \
      maintainer="Mihai Criveti" \
      org.opencontainers.image.title="mcp-reverse-proxy" \
      org.opencontainers.image.description="MCP Reverse Proxy - bridge MCP servers to remote ContextForge gateways over TLS (stdio, SSE, Streamable HTTP, WebSocket)" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.source="https://github.com/contextforge-org/mcp-reverse-proxy" \
      org.opencontainers.image.url="https://github.com/contextforge-org/mcp-reverse-proxy" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"

USER 1001
WORKDIR /home/default

ENTRYPOINT ["mcp-reverse-proxy"]
# Default command is INERT: prints usage and exits 0 (nothing executes that
# isn't part of the signed, scanned image). Bridge a server by passing the
# full arguments explicitly, e.g. --local-stdio "uvx mcp-server-git" with
# REVERSE_PROXY_GATEWAY + REVERSE_PROXY_TOKEN (or --gateway/--token) set;
# without a gateway the client exits non-zero (cli.py:339).
# TRUST BOUNDARY: MCP server packages downloaded at run time (e.g. via uvx)
# are NOT covered by this image's SBOM, vulnerability scan, or cosign
# signature - pin them (e.g. `uvx mcp-server-git==<version>`) for production.
CMD ["--help"]
