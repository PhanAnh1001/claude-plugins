// Pure decision for `ui.hh_tree.enabled`: parse the shim's JSON, fail open on anything unexpected.

export interface UiToggle {
  enabled: boolean
  source: string
}

/** Fallback keeps the old behaviour: pane on when config is unreadable. */
export const UI_ENABLED_FALLBACK: UiToggle = { enabled: true, source: 'plugin' }

export function parseUiToggle(stdout: string | undefined, exitCode = 0): UiToggle {
  if (exitCode !== 0 || !stdout) return UI_ENABLED_FALLBACK
  try {
    const data = JSON.parse(stdout) as Partial<UiToggle>
    if (data.enabled !== false) return UI_ENABLED_FALLBACK
    return { enabled: false, source: typeof data.source === 'string' && data.source ? data.source : '?' }
  } catch {
    return UI_ENABLED_FALLBACK
  }
}

export function disabledMessage(source: string): string {
  return `Pane hh-ps đang tắt bởi cấu hình ui.hh_tree.enabled=false (nguồn: ${source}). `
    + 'Đặt true trong ~/.hybrid-hands/config.json hoặc .claude/hybrid-hands.json rồi mở phiên mới.'
}
