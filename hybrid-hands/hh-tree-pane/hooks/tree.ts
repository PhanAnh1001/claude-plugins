// Pane rows mirror hh-ps: full model/effort, elapsed, end, cost and account quota.
import type { Row, Tone } from '../types'

type Usage = { account_plan?: string; account_5h_pct?: number | null; account_week_pct?: number | null; read?: number | null; cache_read?: number | null; cache_write?: number | null; out?: number | null; usd?: number | null; usd_estimated?: boolean; week_pct?: number | null; week_pct_estimated?: boolean; gpt_5h_pct?: number | null; gpt_week_pct?: number | null }
type Sub = { provider?: string; exit_code?: number | null; model?: string; effort?: string; started_at?: string | null; description?: string; agent_type?: string; status?: string; context_tokens?: number | null; duration_seconds?: number | null; ended_at?: string | null; usage?: Usage | null }
type Run = {
  exit_code?: number | null; model?: string; effort?: string; label?: string; backend?: string; status?: string; state?: string
  tokens?: { input?: number; cached_input?: number; output?: number } | null
  usage?: Usage | null
  started_at?: string | null; ended_at?: string | null; duration_seconds?: number | null
}
type Limit = {
  plan?: string; window?: string
  this_machine_pct?: number | null; other_pct?: number | null; total_pct?: number | null
  resets_at?: string | null; source?: string; estimated?: boolean
}
type Session = {
  model?: string; effort?: string; duration_seconds?: number | null; session_id: string; name?: string | null; status?: string; context_tokens?: number | null
  last_activity?: string | null; ended_at?: string | null; is_main?: boolean; live?: boolean
  side_name?: string | null; parent_session?: string | null; started_at?: string | null
  ai_title?: string | null; usage?: Usage | null
  subagents?: Sub[]; hand_runs?: Run[]
}
export type HhPs = {
  generated_at?: string
  sessions?: Session[]
  hidden_ended_sessions?: number
  orphan_runs?: Run[]
  limits?: Limit[]
  totals?: { live_sessions?: number; running_subagents?: number; running_hand_runs?: number }
}

export const LEGEND = '▶ phiên này ● sống ○ đã dừng · kết thúc local · USD ước tính · % tài khoản 5h/tuần · riêng = phần của lượt'
// Display-cell caps shared with hh-ps (constants.py): keep child rows within
// ~68 cells and session rows within ~52 so the pane beside the chat is not cut.
// The shared lead column (session name plus tree art) leaves less room for the
// child description, so it caps at 16 cells.
const NAME_MAX = 16
const DESCRIPTION_MAX = 16
const KIND_MAX = 8
const STUCK_TEXT = 'kẹt?'
const KIND_ALIASES: Record<string, string> = { 'hybrid-hands:hand': 'hand', opencode: 'oc' }
const STATUS_ALIASES: Record<string, string> = { quota_exhausted: 'quota' }
const OK_STATUSES = ['ok', 'finished', 'running']
const MARK = { here: '▶', live: '●', ended: '○', running: '▶', ok: '✓', bad: '✗' } as const
// A session marked busy with no transcript activity for this long is likely stuck.
const STALE_BUSY_SECONDS = 15 * 60
// Below this many thousands a `k` value keeps one decimal (6.4k); above it, none (46k).
const K_DECIMAL_BELOW = 10

const oneDecimal = (n: number) => n.toFixed(1).replace(/\.0$/, '')

export function short(n: number | null | undefined): string {
  if (n == null) return '?'
  if (n < 1e3) return String(n)
  const k = n / 1e3
  if (k < K_DECIMAL_BELOW) return `${oneDecimal(k)}k`
  if (Math.round(k) < 1e3) return `${Math.round(k)}k`
  return `${oneDecimal(n / 1e6)}M`
}

export function age(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return '?'
  const s = Math.max(0, Math.round(seconds))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}p`
  const h = Math.floor(m / 60)
  if (h >= 24) return `${Math.floor(h / 24)}ng`
  return `${h}g${m % 60 ? `${m % 60}p` : ''}`
}

// Cells a string takes in the pane: NFC code points minus combining marks.
export function width(text: string): number {
  return [...text.normalize('NFC')].filter(ch => !/\p{M}/u.test(ch)).length
}

function cut(text: string, max: number): string {
  const chars = [...text.normalize('NFC')]
  return chars.length > max ? `${chars.slice(0, max - 1).join('')}…` : text
}

function since(iso: string | null | undefined, now: number): number | null {
  if (!iso) return null
  const t = Date.parse(iso)
  return Number.isNaN(t) ? null : (now - t) / 1000
}

const pad2 = (n: number) => String(n).padStart(2, '0')

// Same format as hh-ps: `HH:MM`, or `dd/mm HH:MM` on another local day.
export function endedText(iso: string | null | undefined, now: number): string {
  if (!iso) return ''
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return ''
  const end = new Date(t)
  const clock = `${pad2(end.getHours())}:${pad2(end.getMinutes())}`
  const sameDay = end.toDateString() === new Date(now).toDateString()
  return sameDay ? clock : `${pad2(end.getDate())}/${pad2(end.getMonth() + 1)} ${clock}`
}

const failedExit = (r: { exit_code?: number | null }) =>
  typeof r.exit_code === 'number' && Number.isFinite(r.exit_code) && r.exit_code !== 0

function runIsLive(r: Run): boolean {
  // `state` is the registry's view checked against the process; a dead
  // process keeps `status: running` but reads `state: lost`.
  return !failedExit(r) && (r.state ? r.state === 'running' : r.status === 'running')
}

function runIsBad(r: Run): boolean {
  return failedExit(r) || r.state === 'lost' || (r.status != null && !OK_STATUSES.includes(r.status))
}

const completedText = (iso: string | null | undefined) => {
  if (!iso || Number.isNaN(Date.parse(iso))) return '?'
  const d = new Date(iso)
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`
}

const kind = (raw: string | undefined) => KIND_ALIASES[raw ?? ''] ?? raw ?? '?'
const modelEffort = (r: {model?: string; effort?: string}) => `${r.model || '?'}/${r.effort || '?'}`

// A row before alignment: `lead` is the first column (mark + name/kind), `cols`
// the rest. All tree rows share one group so later columns line up; `group`
// null means a free-text row printed as is.
type Group = 'tree'
type Draft = { lead: string; cols: Col[]; tone: Tone; indent: number; group: Group | null; bad?: string }
type Col = { text: string; right?: boolean; glue?: boolean }

const COLUMN_GAP = '  '
// The pane draws each indent level as two spaces (register.tsx).
const INDENT_CELLS = 2
const USD_MIN_VISIBLE = 0.01
// Limit share prints one decimal; a non-zero share that rounds to 0.0 reads `<0.1%`.
const PERCENT_DECIMALS = 1
const PERCENT_MIN_VISIBLE = 0.1
// Three spaces separate the plan/window label from the machine split.
const LIMIT_GAP = '   '
const UNKNOWN_PERCENT = '?'
const GPT_PLAN = 'GPT'
const GPT_5H_WINDOW = '5h'

const plain = (text: string, tone: Tone, indent: number): Draft => ({ lead: text, cols: [], tone, indent, group: null })

export const usdText = (usd: number | null | undefined, estimated = false) => {
  if (usd == null) return '-'
  const mark = estimated ? '~' : ''
  if (usd <= 0) return `${mark}$0`
  return `${mark}${usd < USD_MIN_VISIBLE ? '<$0.01' : `$${usd.toFixed(2)}`}`
}

export const percentText = (pct: number | null | undefined, estimated = false) => {
  if (pct == null || !Number.isFinite(pct)) return ''
  const mark = estimated ? '~' : ''
  if (pct > 0 && pct < PERCENT_MIN_VISIBLE / 2) return `${mark}<${PERCENT_MIN_VISIBLE}%`
  return `${mark}${Math.max(0, pct).toFixed(PERCENT_DECIMALS)}%`
}

const limitPercent = (pct: number | null | undefined, estimated = false) => (
  pct == null || !Number.isFinite(pct) ? UNKNOWN_PERCENT : percentText(pct, estimated))

/** `Go tuần   máy này 12.3% · máy khác 4.5% · tổng 16.8% · reset 14:00` */
export const limitLine = (l: Limit, now: number) => {
  const reset = endedText(l.resets_at, now)
  const mark = l.estimated === true
  const parts = l.plan === GPT_PLAN
    ? [`tổng ${limitPercent(l.total_pct, mark)}`]
    : [`máy này ${limitPercent(l.this_machine_pct, mark)}`,
      `máy khác ${limitPercent(l.other_pct, mark)}`,
      `tổng ${limitPercent(l.total_pct, mark)}`]
  if (reset) parts.push(`reset ${reset}`)
  return `${l.plan ?? '?'} ${l.window ?? '?'}${LIMIT_GAP}${parts.join(' · ')}`
}

const WEEK_WINDOW = 'tuần'

/** `GPT 5h 12.3% · tuần 4.5%`; '' when the row has no account sample. */
const gptShare = (usage: Usage | null | undefined) => {
  const five = usage?.gpt_5h_pct
  const week = usage?.gpt_week_pct
  if (five == null && week == null) return ''
  const windows: string[] = []
  if (five != null) windows.push(`${GPT_5H_WINDOW} ${limitPercent(five)}`)
  if (week != null) windows.push(`${WEEK_WINDOW} ${limitPercent(week)}`)
  return `GPT ${windows.join(' · ')}`
}

// USD then the GPT sample or weekly share, both right-aligned; same cells as hh-ps compact.py.
function usageCols(usage: Usage | null | undefined): Col[] {
  const five = usage?.account_5h_pct ?? usage?.gpt_5h_pct
  const week = usage?.account_week_pct ?? usage?.gpt_week_pct
  const own = percentText(usage?.week_pct, usage?.week_pct_estimated === true)
  const share = `${usage?.account_plan || 'TK'} 5h ${limitPercent(five)} · tuần ${limitPercent(week)}${own ? ` · riêng ${own} tuần` : ''}`
  return [{ text: usage?.usd == null ? '~$?' : usdText(usage.usd, true), right: true },
    { text: share, right: true }]

}

function childRow(mark: string, tone: Tone, k: string | undefined, what: string, bad: string,
  dur: string, end: string, usage: Usage | null | undefined, indent: number, model: string): Draft {
  const cols = [{ text: model }, { text: dur, right: true }, { text: end }, ...usageCols(usage),
    { text: cut(what, DESCRIPTION_MAX) }, { text: bad }]
  return { lead: `${mark} ${kind(k)}`, cols, tone, indent, group: 'tree' }
}

function runRow(r: Run, now: number, indent: number): Draft {
  const live = runIsLive(r)
  const lost = r.state === 'lost'
  const bad = !live && runIsBad(r)
  const dur = live ? since(r.started_at, now) : lost && !r.ended_at ? null : r.duration_seconds
  const text = lost ? 'mất' : bad ? STATUS_ALIASES[r.status ?? ''] ?? r.status ?? '' : ''
  const mark = live ? MARK.running : bad ? MARK.bad : MARK.ok
  const tone: Tone = live ? 'running' : bad ? 'bad' : 'dim'
  return childRow(mark, tone, r.backend, r.label ?? '?', text,
    age(dur), live ? 'đang chạy' : completedText(r.ended_at), r.usage, indent, modelEffort(r))
}

const nativeSub = (s: Sub) => s.agent_type === 'native-codex'
const subIsBad = (s: Sub) => failedExit(s) ||
  (nativeSub(s) && ['failed', 'error', 'errored', 'cancelled', 'canceled'].includes(s.status ?? ''))
const subIsLive = (s: Sub) => !subIsBad(s) &&
  (s.status === 'running' || (!nativeSub(s) && s.status === 'silent'))

function subRow(s: Sub, now: number, indent: number): Draft {
  const live = subIsLive(s)
  const silent = s.status === 'silent'
  const bad = subIsBad(s)
  const mark = bad ? MARK.bad : live ? MARK.running : nativeSub(s) && s.status !== 'completed' ? '?' : MARK.ok
  return childRow(mark, bad || silent ? 'bad' : live ? 'running' : 'dim', s.agent_type,
    s.description ?? '', silent ? 'im lặng' : '', age(s.duration_seconds),
    live ? 'đang chạy' : completedText(s.ended_at), s.usage, indent, modelEffort(s))
}

function isLive(s: Session): boolean {
  return s.live ?? (s.status === 'busy' || s.status === 'idle')
}

const sessionName = (s: Session) => cut(s.side_name ? `phụ:${s.side_name}` : s.name || s.session_id.slice(0, 8), NAME_MAX)

function sessionLook(s: Session, now: number, isHere: boolean) {
  const live = isLive(s)
  const quiet = since(s.last_activity, now)
  const stale = live && s.status === 'busy' && quiet != null && quiet > STALE_BUSY_SECONDS
  const mark = isHere ? MARK.here : live ? MARK.live : MARK.ended
  const tone: Tone = isHere ? 'main' : !live ? 'dim' : stale ? 'bad' : s.status === 'busy' ? 'busy' : 'idle'
  return { live, quiet, stale, mark, tone }
}

function headRow(s: Session, now: number, isHere: boolean, indent: number): Draft {
  const { live, quiet, stale, mark, tone } = sessionLook(s, now, isHere)
  const cols = [
    { text: modelEffort(s) },
    { text: age(s.duration_seconds), right: true },
    { text: live ? 'đang chạy' : completedText(s.ended_at) },
    ...usageCols(s.usage), { text: s.status || '?' },
  ]
  return { lead: `${mark} ${sessionName(s)} (${s.side_name ? 'side' : 'root'} session)`, cols, tone, indent, group: 'tree' }

}

// A side session listed among its parent's children, in the child columns.
function sideRow(s: Session, now: number, isHere: boolean, indent: number): Draft {
  return headRow(s, now, isHere, indent)
}

const stamp = (iso: string | null | undefined) => (iso ? Date.parse(iso) : NaN)
type Item = { running: boolean; bad: boolean; end: number; rows: () => Draft[] }

// Running children first, then the newest finished or failed, then a summary.
function childRows(items: Item[], indent: number): Draft[] {
  const done = items.filter(x => !x.running).sort((a, b) => (Number.isNaN(b.end) ? -Infinity : b.end) - (Number.isNaN(a.end) ? -Infinity : a.end))
  return [...items.filter(x => x.running), ...done].flatMap(x => x.rows())
}

// One session row, then its children one level deeper; side sessions are
// children too and list their own children by the same rule.
function sessionTree(s: Session, now: number, hereId: string, indent: number,
  kids: Map<string, Session[]>, seen: Set<string>, asChild: boolean): Draft[] {
  if (seen.has(s.session_id)) return [] // defensive: a cycle in side-session state
  seen.add(s.session_id)
  const isHere = s.session_id === hereId
  const head = asChild ? sideRow(s, now, isHere, indent) : headRow(s, now, isHere, indent)
  const inner = indent + 1
  const items: Item[] = [
    ...(s.subagents ?? []).map(x => ({ running: subIsLive(x), bad: subIsBad(x),
      end: stamp(x.ended_at), rows: () => [subRow(x, now, inner)] })),
    ...(s.hand_runs ?? []).map(x => ({ running: runIsLive(x), bad: !runIsLive(x) && runIsBad(x),
      end: stamp(x.ended_at), rows: () => [runRow(x, now, inner)] })),
    ...(kids.get(s.session_id) ?? []).map(k => ({ running: isLive(k), bad: false, end: stamp(k.ended_at),
      rows: () => sessionTree(k, now, hereId, inner, kids, seen, true) })),
  ]
  return [head, ...childRows(items, inner)]
}

const padEnd = (text: string, cells: number) => text + ' '.repeat(Math.max(0, cells - width(text)))
const padStart = (text: string, cells: number) => ' '.repeat(Math.max(0, cells - width(text))) + text

// Pads the shared tree table's columns to their widest cell; the first column
// counts the indent so rows at different depths line up after it.
export function align(drafts: Draft[]): Row[] {
  const widths = new Map<Group, number[]>()
  for (const d of drafts) {
    if (!d.group) continue
    const w = widths.get(d.group) ?? []
    w[0] = Math.max(w[0] ?? 0, d.indent * INDENT_CELLS + width(d.lead))
    d.cols.forEach((c, i) => { w[i + 1] = Math.max(w[i + 1] ?? 0, width(c.text)) })
    widths.set(d.group, w)
  }
  return drafts.map(d => {
    if (!d.group) return { text: d.lead, tone: d.tone, indent: d.indent, ...(d.bad ? { bad: d.bad } : {}) }
    const w = widths.get(d.group) ?? []
    const parts = [padEnd(d.lead, (w[0] ?? 0) - d.indent * INDENT_CELLS)]
    for (let i = 1; i < w.length; i++) {
      if (!w[i]) continue
      const c = d.cols[i - 1] ?? { text: '' }
      const piece = c.right ? padStart(c.text, w[i]) : padEnd(c.text, w[i])
      if (c.glue) parts[parts.length - 1] += piece
      else parts.push(piece)
    }
    return { text: parts.join(COLUMN_GAP).trimEnd(), tone: d.tone, indent: d.indent }
  })
}

export function buildRows(data: HhPs, hereId: string): { rows: Row[]; header: string } {
  const now = data.generated_at ? Date.parse(data.generated_at) : Date.now()
  const sessions = data.sessions ?? []
  const ids = new Set(sessions.map(s => s.session_id))
  const kids = new Map<string, Session[]>()
  const roots: Session[] = []
  for (const s of sessions) {
    const parent = s.parent_session
    if (parent && parent !== s.session_id && ids.has(parent)) kids.set(parent, [...(kids.get(parent) ?? []), s])
    else roots.push(s)
  }
  const rank = (s: Session) => (s.session_id === hereId ? 0 : isLive(s) ? (s.status === 'busy' ? 1 : 2) : 3)
  roots.sort((a, b) => rank(a) - rank(b))

  const limits = (data.limits ?? []).filter(
    l => (l.plan !== GPT_PLAN || l.total_pct != null) && (l.window === WEEK_WINDOW || (l.plan === GPT_PLAN && l.window === GPT_5H_WINDOW)))
  const drafts: Draft[] = limits.length
    ? [plain('Hạn mức', 'plain', 0), ...limits.map(l => plain(limitLine(l, now), 'dim', 0))]
    : []
  drafts.push(plain('LOẠI / TÊN  MODEL/EFFORT  THỜI GIAN  KẾT THÚC (local)  USD  TÀI KHOẢN 5h / tuần', 'dim', 0))
  const seen = new Set<string>()
  for (const s of roots) drafts.push(...sessionTree(s, now, hereId, 0, kids, seen, false))
  const rows = align(drafts)
  const t = data.totals ?? {}
  const header = `${t.live_sessions ?? 0} phiên sống · ${t.running_hand_runs ?? 0} hand chạy · ${t.running_subagents ?? 0} subagent${data.hidden_ended_sessions ? ` · ẩn ${data.hidden_ended_sessions} đã kết thúc` : ''}`
  return { rows, header }
}
