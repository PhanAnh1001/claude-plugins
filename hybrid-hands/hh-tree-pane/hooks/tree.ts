// Turns `hh-ps --json` into compact pane rows, in the same layout as the hh-ps
// text tree (lib/hh_ps/compact.py; change both together):
//   session: `<mark> <name>  <quiet | end>  <status>  <tokens>  <usd>  ctx <N>`
//   child:   `<mark> <kind>  <duration>  [<end>]  <tokens>  <usd>  <size>  <description>  [<bad status>]`
//   side session as a child: `<mark> phụ:<name>  <quiet | duration>  [<end>]  <tokens>  <usd>  ctx <N>  [<ai title>]`
// Session, side-session and child rows share one column table, so the token
// block and the size cell (`ctx`/`out`) start at the same display column at
// every depth. `<tokens>` is `read|cache_read|cache_write|out`, right-aligned,
// with the pipes skipping the column gap. Every session lists its children
// (subagents, hand runs, side sessions) by one rule (lib/hh_ps/selection.py):
// running first, then the RECENT_FINISHED_SHOWN newest finished or failed, then
// `+N xong · M lỗi`. The bad status follows the description so ok rows (most of
// them) leave no gap before the description. hh-ps already hides fully ended trees.
import type { Row, Tone } from '../types'

type Usage = { read?: number | null; cache_read?: number | null; cache_write?: number | null; out?: number | null; usd?: number | null }
type Sub = { description?: string; agent_type?: string; status?: string; context_tokens?: number | null; duration_seconds?: number | null; ended_at?: string | null; usage?: Usage | null }
type Run = {
  label?: string; backend?: string; status?: string; state?: string
  tokens?: { input?: number; cached_input?: number; output?: number } | null
  usage?: Usage | null
  started_at?: string | null; ended_at?: string | null; duration_seconds?: number | null
}
type Session = {
  session_id: string; name?: string | null; status?: string; context_tokens?: number | null
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
  totals?: { live_sessions?: number; running_subagents?: number; running_hand_runs?: number }
}

export const LEGEND = '▶ phiên này ● sống ○ đã dừng · giờ = lúc xong · token: đọc|cache đọc|cache ghi|ra · $ ước tính theo giá niêm yết'
// Finished or failed children listed per session; hh-ps constants.py keeps the same.
const RECENT_FINISHED_SHOWN = 3
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

function runIsLive(r: Run): boolean {
  // `state` is the registry's view checked against the process; a dead
  // process keeps `status: running` but reads `state: lost`.
  return r.state ? r.state === 'running' : r.status === 'running'
}

function runIsBad(r: Run): boolean {
  return r.state === 'lost' || (r.status != null && !OK_STATUSES.includes(r.status))
}

const kind = (raw: string | undefined) => cut(KIND_ALIASES[raw ?? ''] ?? raw ?? '-', KIND_MAX)

// A row before alignment: `lead` is the first column (mark + name/kind), `cols`
// the rest. All tree rows share one group so later columns line up; `group`
// null means a free-text row printed as is.
type Group = 'tree'
type Draft = { lead: string; cols: Col[]; tone: Tone; indent: number; group: Group | null; bad?: string }
type Col = { text: string; right?: boolean; glue?: boolean }

const COLUMN_GAP = '  '
// The pane draws each indent level as two spaces (register.tsx).
const INDENT_CELLS = 2
const TOKEN_SEPARATOR = '|'
const USD_MIN_VISIBLE = 0.01

const plain = (text: string, tone: Tone, indent: number): Draft => ({ lead: text, cols: [], tone, indent, group: null })

const tokenCell = (n: number | null | undefined) => (n != null ? short(n) : '-')
const usdText = (usd: number | null | undefined) => {
  if (usd == null) return '-'
  if (usd <= 0) return '$0'
  return usd < USD_MIN_VISIBLE ? '<$0.01' : `$${usd.toFixed(2)}`
}

// `read|cache_read|cache_write|out`, right-aligned; pipes skip COLUMN_GAP.
function usageCols(usage: Usage | null | undefined): Col[] {
  const values = [usage?.read, usage?.cache_read, usage?.cache_write, usage?.out]
  const cols: Col[] = []
  values.forEach((value, index) => {
    if (index) cols.push({ text: TOKEN_SEPARATOR, glue: true })
    cols.push({ text: tokenCell(value), right: true, glue: index > 0 })
  })
  cols.push({ text: usdText(usage?.usd), right: true })
  return cols
}

function childRow(mark: string, tone: Tone, k: string | undefined, what: string, bad: string, size: string,
  dur: string, end: string, usage: Usage | null | undefined, indent: number): Draft {
  const cols = [{ text: dur, right: true }, { text: end }, ...usageCols(usage),
    { text: size }, { text: cut(what, DESCRIPTION_MAX) }, { text: bad }]
  return { lead: `${mark} ${kind(k)}`, cols, tone, indent, group: 'tree' }
}

function runRow(r: Run, now: number, indent: number): Draft {
  const live = runIsLive(r)
  const lost = r.state === 'lost'
  const bad = !live && runIsBad(r)
  const dur = live || lost ? since(r.started_at, now) : r.duration_seconds
  const text = lost ? 'mất' : bad ? STATUS_ALIASES[r.status ?? ''] ?? r.status ?? '' : ''
  const mark = live ? MARK.running : bad ? MARK.bad : MARK.ok
  const tone: Tone = live ? 'running' : bad ? 'bad' : 'dim'
  return childRow(mark, tone, r.backend, r.label ?? '?', text, `out ${short(r.tokens?.output ?? 0)}`,
    age(dur), live || lost ? '' : endedText(r.ended_at, now), r.usage, indent)
}

function subRow(s: Sub, now: number, indent: number): Draft {
  const live = s.status === 'running' || s.status === 'silent'
  const silent = s.status === 'silent'
  const size = s.context_tokens != null ? `ctx ${short(s.context_tokens)}` : ''
  return childRow(live ? MARK.running : MARK.ok, silent ? 'bad' : live ? 'running' : 'dim', s.agent_type,
    s.description ?? '', silent ? 'im lặng' : '', size, age(s.duration_seconds),
    live ? '' : endedText(s.ended_at, now), s.usage, indent)
}

function isLive(s: Session): boolean {
  return s.live ?? (s.status === 'busy' || s.status === 'idle')
}

const sessionName = (s: Session) => cut(s.side_name ? `phụ:${s.side_name}` : s.name || s.session_id.slice(0, 8), NAME_MAX)
const ctx = (n: number | null | undefined) => (n != null ? `ctx ${short(n)}` : '')

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
    { text: live ? age(quiet) : endedText(s.ended_at, now), right: true },
    { text: !live ? '' : stale ? STUCK_TEXT : s.status ?? '?' },
    ...usageCols(s.usage),
    { text: ctx(s.context_tokens) },
  ]
  return { lead: `${mark} ${sessionName(s)}`, cols, tone, indent, group: 'tree' }
}

// A side session listed among its parent's children, in the child columns.
function sideRow(s: Session, now: number, isHere: boolean, indent: number): Draft {
  const { live, quiet, stale, mark, tone } = sessionLook(s, now, isHere)
  const start = since(s.started_at, now)
  const end = since(s.ended_at, now)
  const dur = live ? quiet : start != null && end != null ? start - end : null
  const cols = [
    { text: dur != null ? age(dur) : '', right: true },
    { text: live ? (stale ? STUCK_TEXT : '') : endedText(s.ended_at, now) },
    ...usageCols(s.usage),
    { text: ctx(s.context_tokens) },
    { text: cut(s.ai_title ?? '', DESCRIPTION_MAX) },
  ]
  return { lead: `${mark} ${sessionName(s)}`, cols, tone, indent, group: 'tree' }
}

const stamp = (iso: string | null | undefined) => (iso ? Date.parse(iso) : NaN)
type Item = { running: boolean; bad: boolean; end: number; rows: () => Draft[] }

// Running children first, then the newest finished or failed, then a summary.
function childRows(items: Item[], indent: number): Draft[] {
  const done = items.filter(x => !x.running).sort((a, b) => (Number.isNaN(b.end) ? -Infinity : b.end) - (Number.isNaN(a.end) ? -Infinity : a.end))
  const rest = done.slice(RECENT_FINISHED_SHOWN)
  const rows = [...items.filter(x => x.running), ...done.slice(0, RECENT_FINISHED_SHOWN)].flatMap(x => x.rows())
  const bad = rest.filter(x => x.bad).length
  const ok = rest.length - bad
  if (!rest.length) return rows
  const summary = plain(`+${ok ? `${ok} xong` : ''}${ok && bad ? ' · ' : ''}`, 'dim', indent)
  return [...rows, { ...summary, bad: bad ? `${bad} lỗi` : undefined }]
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
    ...(s.subagents ?? []).map(x => ({ running: x.status === 'running' || x.status === 'silent', bad: false,
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

  const drafts: Draft[] = []
  const seen = new Set<string>()
  for (const s of roots) drafts.push(...sessionTree(s, now, hereId, 0, kids, seen, false))
  const orphans = (data.orphan_runs ?? []).filter(runIsLive)
  if (orphans.length) {
    drafts.push(plain('hand ngoài không rõ phiên gọi', 'plain', 0))
    drafts.push(...orphans.map(r => runRow(r, now, 1)))
  }
  const rows = align(drafts)
  const t = data.totals ?? {}
  const header = `${t.live_sessions ?? 0} phiên sống · ${t.running_hand_runs ?? 0} hand chạy · ${t.running_subagents ?? 0} subagent${data.hidden_ended_sessions ? ` · ẩn ${data.hidden_ended_sessions} đã kết thúc` : ''}`
  return { rows, header }
}
