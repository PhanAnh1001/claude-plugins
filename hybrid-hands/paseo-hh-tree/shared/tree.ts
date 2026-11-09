import { defineRpc } from "@getpaseo/plugin";
import { z } from "zod";

export const UUID_RE =
  /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;

// Per-row cost from `hh-ps --json`: USD estimate and share of the weekly plan
// limit in percent. Codex rows add `usd_estimated` and account GPT samples;
// older hh-ps builds omit all of them.
const usageSchema = z
  .object({
    account_plan: z.string().optional(),
    account_5h_pct: z.number().nullable().optional(),
    account_week_pct: z.number().nullable().optional(),
    usd: z.number().nullable().optional(),
    usd_estimated: z.boolean().optional(),
    week_pct: z.number().nullable().optional(),
    week_pct_estimated: z.boolean().optional(),
    week_pct_source: z.string().optional(),
    gpt_5h_pct: z.number().nullable().optional(),
    gpt_week_pct: z.number().nullable().optional(),
  })
  .passthrough()
  .nullable()
  .optional();

// Top-of-panel limit rows from `hh-ps --json` (Claude/Go weekly, GPT 5h + weekly).
const limitSchema = z
  .object({
    plan: z.string(),
    window: z.string(),
    this_machine_pct: z.number().nullable(),
    other_pct: z.number().nullable(),
    total_pct: z.number().nullable(),
    resets_at: z.string().nullable(),
    source: z.string(),
    estimated: z.boolean().optional(),
  })
  .passthrough();

const handRunSchema = z
  .object({
    effort: z.string().optional(),
    exit_code: z.number().nullable().optional(),
    exit: z.number().nullable().optional(),
    description: z.string().optional(),
    run_id: z.string(),
    label: z.string(),
    backend: z.string(),
    model: z.string(),
    status: z.string(),
    state: z.string(),
    tokens: z
      .object({
        input: z.number(),
        cached_input: z.number(),
        output: z.number(),
      })
      .passthrough(),
    started_at: z.string().nullable(),
    ended_at: z.string().nullable(),
    duration_seconds: z.number().nullable(),
    parent_session: z.string().nullable(),
    pid: z.number().nullable(),
    child_pid: z.number().nullable(),
    usage: usageSchema,
  })
  .passthrough();

const subagentSchema = z
  .object({
    provider: z.string().optional(),
    parent_session: z.string().nullable().optional(),
    model: z.string().optional(),
    effort: z.string().optional(),
    exit_code: z.number().nullable().optional(),
    exit: z.number().nullable().optional(),
    started_at: z.string().nullable().optional(),
    ended_at: z.string().nullable().optional(),
    agent_id: z.string(),
    agent_type: z.string(),
    description: z.string(),
    status: z.string(),
    context_tokens: z.number().nullable(),
    duration_seconds: z.number().nullable(),
    usage: usageSchema,
  })
  .passthrough();

const sessionSchema = z
  .object({
    model: z.string().optional(),
    effort: z.string().optional(),
    exit_code: z.number().nullable().optional(),
    exit: z.number().nullable().optional(),
    duration_seconds: z.number().nullable().optional(),
    ended_at: z.string().nullable().optional(),
    description: z.string().optional(),
    ai_title: z.string().nullable().optional(),
    session_id: z.string(),
    name: z.string(),
    parent_session: z.string().nullable().optional(),
    side_name: z.string().nullable().optional(),
    provider: z.string().optional(),
    status: z.string(),
    cwd: z.string(),
    context_tokens: z.number().nullable(),
    started_at: z.string().nullable(),
    last_activity: z.string().nullable(),
    is_main: z.boolean(),
    live: z.boolean(),
    project_slug: z.string(),
    transcript_path: z.string().nullable(),
    token_cap: z.number().nullable(),
    token_ratio: z.number().nullable(),
    subagents: z.array(subagentSchema),
    hand_runs: z.array(handRunSchema),
    usage: usageSchema,
  })
  .passthrough();

export const claudeCalibrationSchema = z.object({
  source: z.string(),
  account_source: z.string(),
  account_5h_pct: z.number().nullable(),
  account_week_pct: z.number().nullable(),
  usd_per_pct: z.number().nullable(),
  usd: z.number().nullable(),
  tokens: z.object({
    input: z.number(), output: z.number(), cache_read: z.number(),
    cache_write_5m: z.number(), cache_write_1h: z.number(),
  }).passthrough().nullable(),
  sampled_at: z.number().nullable(),
  resets_at: z.number().nullable(),
  precision: z.string(),
  status: z.string(),
}).passthrough();

export const treeSchema = z
  .object({
    schema: z.number(),
    generated_at: z.string(),
    since_seconds: z.number(),
    cwd: z.string(),
    all_projects: z.boolean(),
    main_session_id: z.string().nullable(),
    claude_calibration: claudeCalibrationSchema.optional(),
    limits: z.array(limitSchema).optional(),
    machine_usage: z.array(z.object({
      plan: z.enum(["Claude", "GPT"]), window: z.literal("tuần"),
      usd: z.number().nullable(), source: z.string(),
    })).optional(),
    sessions: z.array(sessionSchema),
    orphan_runs: z.array(handRunSchema),
    totals: z
      .object({
        live_sessions: z.number(),
        running_subagents: z.number(),
        running_hand_runs: z.number(),
      })
      .passthrough(),
  })
  .passthrough();

const treeOutput = z.union([
  z.object({ ok: z.literal(true), tree: treeSchema }),
  z.object({ ok: z.literal(false), error: z.string() }),
]);

export const treeRpc = defineRpc({
  name: "hh-tree.get",
  input: z.object({
    agentId: z.string().regex(UUID_RE).optional(),
    all: z.boolean().optional(),
  }),
  output: treeOutput,
});

export type TreeData = z.infer<typeof treeSchema>;
export type TreeSession = z.infer<typeof sessionSchema>;
export type TreeSubagent = z.infer<typeof subagentSchema>;
export type TreeUsage = z.infer<typeof usageSchema>;
export type TreeLimit = z.infer<typeof limitSchema>;
export type TreeHandRun = z.infer<typeof handRunSchema>;
export type TreeResult = z.infer<typeof treeOutput>;

export type ClaudeCalibration = z.infer<typeof claudeCalibrationSchema>;
