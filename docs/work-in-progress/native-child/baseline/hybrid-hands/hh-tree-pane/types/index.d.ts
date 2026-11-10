export type Tone = 'main' | 'busy' | 'idle' | 'running' | 'bad' | 'dim' | 'plain'

// `bad` is a trailing part drawn in the error colour (the `M lỗi` of a summary).
export type Row = { text: string; tone: Tone; indent: number; bad?: string }

export type TreeSnapshot = { rows: Row[]; header: string; error: string | null }

declare module 'claude-code' {
  interface PluginState {
    'hh-tree-pane': { tree: Shaped<TreeSnapshot> }
  }
}
