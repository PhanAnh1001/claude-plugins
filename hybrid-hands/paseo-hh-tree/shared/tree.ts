import { defineRpc } from "@getpaseo/plugin";
import { z } from "zod";

export const UUID_RE =
  /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;

// Per-row cost from `hh-ps --json`: USD estimate and share of the weekly plan
// limit in percent. Older hh-ps builds omit it.
const usageSchema = z
  .object({
    usd: z.number().nullable().optional(),
    week_pct: z.number().nullable().optional(),
    week_pct_estimated: z.boolean().optional(),
  })
  .passthrough()
  .nullable()
  .optional();

// Top-of-panel limit rows from `hh-ps --json` (Go + Claude when cached).
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
    run_id: z.string(),
    label: z.string(),
    backend: z.string(),
    model: z.string(),
    status: z.string(),
    state: z.enum(["running", "finished", "lost"]),
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
    agent_id: z.string(),
    agent_type: z.string(),
    description: z.string(),
    status: z.enum(["running", "silent", "finished"]),
    context_tokens: z.number().nullable(),
    duration_seconds: z.number().nullable(),
    usage: usageSchema,
  })
  .passthrough();

const sessionSchema = z
  .object({
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

export const treeSchema = z
  .object({
    schema: z.number(),
    generated_at: z.string(),
    since_seconds: z.number(),
    cwd: z.string(),
    all_projects: z.boolean(),
    main_session_id: z.string().nullable(),
    limits: z.array(limitSchema).optional(),
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
