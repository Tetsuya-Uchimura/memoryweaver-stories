FROM node:22-bookworm-slim AS cli
ARG CODEX_VERSION=0.166.0
ARG CLAUDE_VERSION=2.1.309
RUN npm install -g @openai/codex@${CODEX_VERSION} @anthropic-ai/claude-code@${CLAUDE_VERSION}
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates libatomic1 libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
COPY --from=cli /usr/local/bin/node /usr/local/bin/node
COPY --from=cli /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/@openai/codex/bin/codex.js /usr/local/bin/codex && ln -s /usr/local/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe /usr/local/bin/claude
WORKDIR /workspace
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked pip install --timeout 60 -r requirements.txt && useradd -m -u 1000 weaver && mkdir /data && chown weaver:weaver /data
COPY app app
COPY agents agents
COPY samples samples
COPY scripts scripts
USER weaver
ENV PYTHONUNBUFFERED=1 DATA_DIR=/data HOME=/home/weaver CODEX_HOME=/home/weaver/.codex
CMD ["python", "-m", "agents.worker"]
