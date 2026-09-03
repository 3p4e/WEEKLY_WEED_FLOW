// Registry of CLI coding agents the workspace can launch in a pane.
//
// Two authentication modes exist per provider:
//   key          — a credential from the vault is injected as `keyEnv` into the
//                  agent's environment (pay-per-token, bring your own key).
//   subscription — no key is injected and `keyEnv` is STRIPPED from the
//                  environment, so the CLI falls back to its own vendor login
//                  (Claude Pro/Max via `claude` login, ChatGPT Plus/Pro via
//                  `codex login`, Google account via `gemini`). The login state
//                  lives in the CLI's own config dir, i.e. it is per-host.
//   inherit      — the agent gets the server's environment unchanged.
//
// Nothing here proxies or re-sells a subscription: the vendor CLI runs as-is
// under the operator's own login, which is the only arrangement the vendors'
// consumer terms allow. Sharing one login across users or scraping a CLI to
// expose it as an API is outside what this platform will do.
import { accessSync, constants } from 'node:fs';
import { delimiter, join } from 'node:path';

export const PROVIDERS = [
  {
    id: 'claude', name: 'Claude Code', bin: 'claude', vendor: 'Anthropic',
    keyEnv: 'ANTHROPIC_API_KEY', subscription: 'Claude Pro / Max (run `claude` and follow the login prompt)',
    argv: (prompt) => (prompt ? [prompt] : []),
    install: 'npm i -g @anthropic-ai/claude-code',
  },
  {
    id: 'codex', name: 'Codex CLI', bin: 'codex', vendor: 'OpenAI',
    keyEnv: 'OPENAI_API_KEY', subscription: 'ChatGPT Plus / Pro (`codex login`)',
    argv: (prompt) => (prompt ? [prompt] : []),
    install: 'npm i -g @openai/codex',
  },
  {
    id: 'gemini', name: 'Gemini CLI', bin: 'gemini', vendor: 'Google',
    keyEnv: 'GEMINI_API_KEY', subscription: 'Google account / Code Assist (`gemini` login flow)',
    argv: (prompt) => (prompt ? ['-i', prompt] : []),
    install: 'npm i -g @google/gemini-cli',
  },
  {
    id: 'opencode', name: 'OpenCode', bin: 'opencode', vendor: 'multi (OpenRouter, Anthropic, OpenAI…)',
    keyEnv: 'OPENROUTER_API_KEY', subscription: null,
    argv: (prompt) => (prompt ? ['--prompt', prompt] : []),
    install: 'npm i -g opencode-ai',
  },
  {
    id: 'aider', name: 'Aider', bin: 'aider', vendor: 'multi',
    keyEnv: 'OPENAI_API_KEY', subscription: null,
    argv: (prompt) => (prompt ? ['--message', prompt] : []),
    install: 'python -m pip install aider-chat',
  },
  {
    id: 'shell', name: 'Shell', bin: null, vendor: null, keyEnv: null, subscription: null,
    argv: () => [], install: null,
  },
];

export function getProvider(id) {
  const p = PROVIDERS.find((x) => x.id === id);
  if (!p) throw new Error(`unknown provider ${id}`);
  return p;
}

export function which(bin, pathEnv = process.env.PATH || '') {
  if (!bin) return null;
  for (const dir of pathEnv.split(delimiter)) {
    if (!dir) continue;
    const full = join(dir, bin);
    try { accessSync(full, constants.X_OK); return full; } catch { /* next */ }
  }
  return null;
}

export function detect(shell) {
  return PROVIDERS.map((p) => {
    const path = p.bin ? which(p.bin) : shell;
    const { argv, ...rest } = p;
    return { ...rest, installed: Boolean(path), path };
  });
}

// Build the child environment for a provider + auth mode. `secret` is
// {envVar, value} from the vault (key mode only).
export function buildEnv(provider, authMode, secret, extra = {}) {
  const env = { ...process.env, ...extra, BRIDGE_SESSION: '1' };
  // Never leak the workspace's own token / master key into an agent's shell.
  delete env.BRIDGE_TOKEN; delete env.BRIDGE_MASTER_KEY;
  if (authMode === 'subscription') {
    if (provider.keyEnv) delete env[provider.keyEnv];
  } else if (authMode === 'key') {
    if (!secret) throw new Error('key mode requires a credential');
    env[secret.envVar] = secret.value;
  } else if (authMode !== 'inherit') {
    throw new Error(`unknown auth mode ${authMode}`);
  }
  return env;
}
