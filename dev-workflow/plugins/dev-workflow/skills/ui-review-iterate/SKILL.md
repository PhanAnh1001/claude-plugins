---
name: ui-review-iterate
description: Change and review a frontend screen against the request point by point - start the frontend with the repo's documented command, open the page in an available browser tool, take before/after screenshots, check each requested point on the screenshot, batch small tweaks into one round instead of many, keep UI strings in the project's language, and run the frontend test/lint/typecheck/build before saying done. Use this whenever the user asks to adjust how a screen looks or behaves, or complains about layout, colours, spacing, buttons, readability, even for a "small" UI tweak. Vietnamese triggers - "giao diện", "UI", "nút", "màu", "khó nhìn", "chỉnh màn hình", "lệch", "căn", "font", "hiển thị sai".
---

# UI Review and Iterate

## Summary

- **Purpose:** finish UI requests in as few rounds as possible by checking the real rendered page
  against an explicit checklist, instead of reporting "done" from code alone.
- **Loop:** checklist from the request → run frontend → screenshot **before** → change (all small
  tweaks in one batch) → screenshot **after** → tick each point on the screenshot → frontend checks →
  report with both screenshots.
- **Done means:** every checklist point verified on an "after" screenshot, plus frontend test, lint,
  typecheck and build green (whichever the repo has).
- **Language:** user-facing strings follow `[frontend].ui_language` (empty = `[project].doc_language`;
  the repo's frontend rules win when stricter), with full diacritics where the language has them.
- **Config keys used:** `[frontend].dev_command`, `[frontend].checks`, `[frontend].ui_language`,
  `[gate].commands`, `[gate].lint`, `[project].doc_language`, `[project].max_file_lines`, `[docs_map]`;
  read with `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config --json` (see `${CLAUDE_PLUGIN_ROOT}/skills/dev-triage/references/config-defaults.md`). Empty frontend keys: read the commands from the repo (§ 1.2).

## 1. Prepare

### 1.1 Turn the request into a checklist

- Split the request into atomic, visually checkable points: `P1 button "Lưu" is primary colour`,
  `P2 table header stays visible on scroll`, `P3 text contrast readable on dark background`.
- Add the implicit ones: works at the narrow width the app supports, light/dark theme if the app has
  both, no layout shift, no console errors.
- Vague words ("khó nhìn", "xấu") → propose a concrete interpretation in the checklist and confirm it
  if the change is large; for small ones state the assumption and proceed.

### 1.2 Find how the frontend runs

- Start from config: `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config --get frontend --json` gives `dev_command` and `checks`. Use them
  as given; read the repo only for what they leave out (port, backend/proxy, conventions).
- Read, in order: the frontend's own `AGENTS.md`/`CLAUDE.md`, `.claude/rules/` for frontend paths, the
  root `AGENTS.md`, `package.json` scripts, `[gate].commands`.
- Note: dev command and port, required backend/proxy, test/lint/typecheck/build commands, UI conventions
  (component library, design tokens, string language).
- If the repo provides a launch skill, or the `run` skill applies, use it to start the app.
- Start the dev server as a background process; stop it when finished.

### 1.3 Pick the browser tool

- Use what the session has: the built-in browser pane (`mcp__Claude_Browser__*`; read
  `anthropic-skills:built-in-browser` first), Claude in Chrome (`mcp__claude-in-chrome__*`; read
  `anthropic-skills:chrome-browser` first), or a headless browser the repo already depends on
  (e.g. Playwright) for scripted screenshots.
- If no browser tool is available, say so, do the code change and checks, and list the points the user
  must verify visually.

## 2. Iterate

### 2.1 Before screenshot

- Open the exact page and state (data loaded, dialog open, hovered row) the request is about; screenshot it.
- Record the URL and the steps to reach that state so "after" is comparable.

### 2.2 Change in one batch

- Apply every small tweak from the checklist in one round; do not ship one colour change per round.
- Follow the repo's conventions: existing components and design tokens over new ad-hoc styles, named
  constants instead of magic values, pure logic in the tested utility layer, components thin.
- Keep files under `[project].max_file_lines`; split a component that grows past it.
- New or changed UI strings in `[frontend].ui_language` (empty = `[project].doc_language`).

### 2.3 After screenshot and point-by-point check

- Reload, reach the same state, screenshot again (plus narrow width / other theme when relevant).
- For each checklist point write `OK` / `NOT OK` with what the screenshot shows. Fix NOT OK points and
  repeat this step, still batching.
- Check the browser console for new errors or warnings.

## 3. Finish

### 3.1 Frontend checks

- Run every command in `[frontend].checks` (or, when empty, the frontend's test, lint, typecheck and
  build commands found in 1.2), plus any `[gate].commands`
  that cover the frontend. A failing build is not done, even if the screenshot looks right.
- If types mirror an API contract, keep them in sync with the contract doc (`[docs_map]`).

### 3.2 Report

- Checklist with OK/NOT OK per point, before/after screenshots (or their paths in a temp location, not
  the repo), commands run with results, assumptions made, anything the user should check on a real
  device.
- Do not commit screenshots to the repo unless the user asks.

## Brain/hand split

- **Brain:** writes the checklist, confirms ambiguous wording with the user, judges the screenshots.
- **Hand:** runs the frontend, captures screenshots, makes the batched change, runs frontend checks,
  returns screenshots and command output. One hand per batch, not one per tweak.
