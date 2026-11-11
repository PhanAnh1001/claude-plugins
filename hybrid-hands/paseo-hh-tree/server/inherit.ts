/**
 * Keep provider/model/effort/account when the Paseo app clears or starts a new chat.
 *
 * The app creates a fresh agent without `env`, so Claude falls back to the default
 * account (~/.claude). This pure module picks the newest agent in the same workspace
 * (by cwd: the create hook carries no workspaceId) and copies only the account selector
 * variables. Other env is never copied, so secrets in launchEnv stay put.
 */

/** Env keys that select an account; nothing else is inherited. */
export const ACCOUNT_ENV_KEYS = ["CLAUDE_CONFIG_DIR", "CODEX_HOME"] as const;

export interface SourceAgent {
  provider: string;
  cwd: string;
  model?: string;
  thinkingOptionId?: string;
  launchEnv?: Record<string, string>;
  internal?: boolean;
  /** Epoch ms of updatedAt, else createdAt; 0 when unknown. */
  timestamp: number;
}

export interface CreateRequest {
  config: { provider: string; cwd: string; model?: string; thinkingOptionId?: string; internal?: boolean };
  env?: Record<string, string>;
}

/** `claude`, `claude-v2` -> claude; `codex`, `codex-hand` -> codex; others keep their id. */
export function providerFamily(provider: string): string {
  if (/^claude(-v\d+)?$/.test(provider)) return "claude";
  if (provider === "codex" || provider === "codex-hand") return "codex";
  return provider;
}

function hasAccountEnv(env: Record<string, string> | undefined): boolean {
  return ACCOUNT_ENV_KEYS.some(key => Boolean(env?.[key]));
}

/** Newest non-internal agent in the same cwd and provider family; ties keep input order. */
export function pickSource(agents: readonly SourceAgent[], cwd: string, family: string): SourceAgent | null {
  let best: SourceAgent | null = null;
  for (const agent of agents) {
    if (agent.internal || agent.cwd !== cwd || providerFamily(agent.provider) !== family) continue;
    if (!best || agent.timestamp > best.timestamp) best = agent;
  }
  return best;
}

/**
 * Returns the request to use. Unchanged when it is internal, already names an account,
 * or has no same-family source (another family means the user picked a provider).
 */
export function inheritFromSource<T extends CreateRequest>(request: T, agents: readonly SourceAgent[]): T {
  const { config } = request;
  if (config.internal || hasAccountEnv(request.env)) return request;
  const source = pickSource(agents, config.cwd, providerFamily(config.provider));
  if (!source) return request;
  const accountEnv: Record<string, string> = {};
  for (const key of ACCOUNT_ENV_KEYS) {
    const value = source.launchEnv?.[key];
    if (value) accountEnv[key] = value;
  }
  return {
    ...request,
    config: {
      ...config,
      provider: source.provider,
      model: source.model ?? config.model,
      thinkingOptionId: source.thinkingOptionId ?? config.thinkingOptionId,
    },
    env: Object.keys(accountEnv).length ? { ...request.env, ...accountEnv } : request.env,
  };
}
