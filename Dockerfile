# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /src
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml README.md LICENSE THIRD_PARTY_NOTICES.md ./
COPY seohead ./seohead
RUN python -m pip install --upgrade pip && \
    python -m pip install ".[mcp,cluster,reports]"

FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.source="https://github.com/PavloSEO/seohead-seotools" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.title="SEOHEAD Tools"

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=builder /opt/venv /opt/venv
RUN groupadd --gid 10001 seohead && \
    useradd --uid 10001 --gid seohead --no-create-home --shell /usr/sbin/nologin seohead && \
    mkdir -p /data && chown seohead:seohead /data

USER seohead
WORKDIR /data

ENTRYPOINT ["seohead"]
CMD ["--help"]
