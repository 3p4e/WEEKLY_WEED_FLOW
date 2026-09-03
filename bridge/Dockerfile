# Bridge — multi-agent vibe-coding workspace.
# Ships the workspace server plus the vendor CLIs it can launch. Vendor logins
# (subscription mode) live in the CLI config dirs under /home/bridge, so mount a
# volume there to keep them across container restarts.
FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends git python3 make g++ ca-certificates openssh-client \
 && rm -rf /var/lib/apt/lists/*

# CLI coding agents. Pin or drop lines to taste; Aider is Python and is left out
# of the default image to keep it small.
RUN npm install -g @anthropic-ai/claude-code @openai/codex @google/gemini-cli opencode-ai \
 && npm cache clean --force

RUN useradd -m -u 1000 -s /bin/bash bridge
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev && chown -R bridge:bridge /app
COPY --chown=bridge:bridge . .
USER bridge

ENV BRIDGE_HOST=0.0.0.0 BRIDGE_PORT=7788 BRIDGE_DATA_DIR=/data BRIDGE_PROJECTS_ROOT=/projects BRIDGE_SHELL=/bin/bash
VOLUME ["/data", "/projects", "/home/bridge"]
EXPOSE 7788
CMD ["node", "server/index.js"]
