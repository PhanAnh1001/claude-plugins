import { constants as fsConstants } from "node:fs";
import { access, stat, readdir } from "node:fs/promises";
import { homedir } from "node:os";
import { delimiter, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { execCommand } from "@getpaseo/plugin/server";

import { treeSchema, UUID_RE, type TreeResult } from "../shared/tree";

declare const __dirname: string | undefined;

export const HH_PS_NAME = "hh-ps";
export const HH_PS_RELATIVE = join("..", "plugins", "hybrid-hands", "bin", HH_PS_NAME);
export const HH_PS_TIMEOUT_MS = 15_000;
export const HH_PS_MAX_BUFFER = 4 * 1024 * 1024;
export const HH_PS_SINCE = "6h";
export const HH_PS_MISSING_ERROR =
  "Không tìm thấy hh-ps: đặt đường dẫn trong Cài đặt plugin Cây phiên";

export interface RunOptions {
  cwd?: string;
  sessionId?: string;
  all?: boolean;
}

function expandHome(raw: string): string {
  if (raw === "~") {
    return homedir();
  }
  if (raw.startsWith("~/")) {
    return join(homedir(), raw.slice(2));
  }
  return raw;
}

async function isExecutableFile(path: string): Promise<boolean> {
  try {
    const info = await stat(path);
    if (!info.isFile()) {
      return false;
    }
    await access(path, fsConstants.X_OK);
    return true;
  } catch {
    return false;
  }
}

async function findOnPath(): Promise<string | null> {
  const entries = (process.env.PATH ?? "").split(delimiter);
  for (const entry of entries) {
    if (!entry) {
      continue;
    }
    const candidate = join(entry, HH_PS_NAME);
    if (await isExecutableFile(candidate)) {
      return candidate;
    }
  }
  return null;
}

function pluginDirCandidates(): string[] {
  const dirs: string[] = [];
  try {
    dirs.push(dirname(fileURLToPath(import.meta.url)));
  } catch {
    // Not available in every host bundle.
  }
  try {
    const dir = __dirname;
    if (typeof dir === "string" && dir) {
      dirs.push(dir);
    }
  } catch {
    // ESM has no __dirname.
  }
  try {
    dirs.push(process.cwd());
  } catch {
    // process.cwd() can fail if the working directory was removed.
  }
  return dirs;
}

async function findBesidePlugin(): Promise<string | null> {
  for (const dir of pluginDirCandidates()) {
    for (const relative of [HH_PS_RELATIVE, join("..", HH_PS_RELATIVE)]) {
      const candidate = resolve(dir, relative);
      if (await isExecutableFile(candidate)) return candidate;
    }
  }
  return null;
}

async function findInstalled(): Promise<string | null> {
  const cache = join(process.env.CLAUDE_CONFIG_DIR || join(homedir(), ".claude"), "plugins", "cache");
  let markets: string[];
  try { markets = await readdir(cache); } catch { return null; }
  const candidates: { path: string; version: string }[] = [];
  for (const market of markets) {
    const plugin = join(cache, market, "hybrid-hands");
    let versions: string[];
    try { versions = await readdir(plugin); } catch { continue; }
    for (const version of versions) {
      if (!/^\d+(?:\.\d+)*$/.test(version)) continue;
      candidates.push({ path: join(plugin, version, "bin", HH_PS_NAME), version });
    }
  }
  candidates.sort((a, b) => b.version.localeCompare(a.version, undefined, { numeric: true }));
  for (const candidate of candidates) {
    if (await isExecutableFile(candidate.path)) return candidate.path;
  }
  return null;
}

/** Explicit settings, newest installed plugin, PATH, then sibling checkout. */
export async function findHhPs(configuredPath: string): Promise<string | null> {
  const raw = configuredPath.trim();
  if (raw) {
    const candidate = resolve(expandHome(raw));
    if (await isExecutableFile(candidate)) {
      return candidate;
    }
  }
  const installed = await findInstalled();
  if (installed) return installed;
  const onPath = await findOnPath();
  if (onPath) {
    return onPath;
  }
  return findBesidePlugin();
}

export function buildHhPsArgs(options: RunOptions): string[] {
  const args = ["--json", "--ended", "--full", "--since", HH_PS_SINCE];
  if (options.all) {
    args.push("--all");
  }
  if (options.cwd) {
    args.push("--cwd", options.cwd);
  }
  if (options.sessionId && UUID_RE.test(options.sessionId)) {
    args.push("--main-session", options.sessionId);
  }
  return args;
}

function parseJson(stdout: string): unknown {
  const text = stdout.trim();
  if (!text) {
    return undefined;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return undefined;
  }
}

function describeExecError(error: unknown): string {
  if (!(error instanceof Error)) {
    return "Không chạy được hh-ps";
  }
  const details = error as Error & { code?: unknown; killed?: boolean; signal?: unknown };
  if (details.killed || details.signal) {
    return "hh-ps quá thời gian chờ";
  }
  if (details.code === "ENOENT") {
    return "Không chạy được hh-ps: tệp không tồn tại";
  }
  if (typeof details.code === "number") {
    return `hh-ps kết thúc với mã ${details.code}`;
  }
  return "Không chạy được hh-ps";
}

export async function runHhPs(command: string, options: RunOptions): Promise<TreeResult> {
  try {
    const { stdout } = await execCommand(command, buildHhPsArgs(options), {
      env: process.env,
      timeout: HH_PS_TIMEOUT_MS,
      maxBuffer: HH_PS_MAX_BUFFER,
    });
    const parsed = parseJson(stdout);
    if (parsed === undefined) {
      return { ok: false, error: "hh-ps trả về JSON không hợp lệ" };
    }
    const checked = treeSchema.safeParse(parsed);
    if (!checked.success) {
      return { ok: false, error: "hh-ps trả về dữ liệu không đúng định dạng" };
    }
    return { ok: true, tree: checked.data };
  } catch (error) {
    return { ok: false, error: describeExecError(error) };
  }
}
