// Read only the explicitly sanitized fixture beside this script. No RPC or runtime discovery.
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, '../../..');
const require = createRequire(resolve(dirname(process.execPath), '../lib/node_modules/@getpaseo/cli/package.json'));
const loadEsbuild = require('esbuild');
const finalDir = resolve(repo, 'hybrid-hands/paseo-hh-tree');
const baselineDir = resolve(here, 'baseline/hybrid-hands/paseo-hh-tree');
const themes = {
  light: { colors: { surface0: '#FFFFFF', foreground: '#202020', foregroundMuted: '#666666', accent: '#AA44EE', statusSuccess: '#218739', statusDanger: '#C62828', statusWarning: '#976500', border: '#DDDDDD' } },
  dark: { colors: { surface0: '#171717', foreground: '#EEEEEE', foregroundMuted: '#AAAAAA', accent: '#AA44EE', statusSuccess: '#66BB6A', statusDanger: '#EF5350', statusWarning: '#FFD54F', border: '#444444' } },
};
const host = {
  name: 'synthetic-native-host',
  setup(build) {
    build.onResolve({ filter: /^(react-native|react|react\/jsx-runtime)$/ }, args => ({ path: args.path, namespace: 'fixture' }));
    build.onLoad({ filter: /.*/, namespace: 'fixture' }, args => ({ loader: 'js', contents:
      args.path === 'react-native'
        ? `export const View='View',Text='Text',Pressable='Pressable';`
        : `export const Fragment='Fragment'; export const jsx=(type,props,key)=>({type,props:props??{},key}); export const jsxs=jsx; export default {Fragment};`,
    }));
  },
};
async function bundle(directory, final = false) {
  const extra = final ? `export {panelRows} from './client/compact.ts'; export {ColoredRowText,ColoredSummary} from './client/ColoredText.tsx';` : '';
  const result = await loadEsbuild.build({
    stdin: { contents: `export {SessionBlock,OrphanSideBlock} from './client/SessionBlock.tsx'; export {nestSessions} from './client/nest.ts'; ${extra}`, resolveDir: directory, loader: 'tsx' },
    bundle: true, write: false, format: 'cjs', platform: 'node', jsx: 'automatic', plugins: [host], logLevel: 'silent',
  });
  const module = { exports: {} };
  new Function('module', 'exports', result.outputFiles[0].text)(module, module.exports);
  return module.exports;
}
const styleOf = style => Array.isArray(style) ? Object.assign({}, ...style.map(styleOf)) : style ?? {};
function spans(node, inherited = {}) {
  if (node == null || typeof node === 'boolean') return [];
  if (Array.isArray(node)) return node.flatMap(child => spans(child, inherited));
  if (typeof node === 'string' || typeof node === 'number') return [{ text: String(node), color: inherited.color ?? null }];
  if (typeof node.type === 'function') return spans(node.type(node.props), inherited);
  return spans(node.props.children, { ...inherited, ...styleOf(node.props.style) });
}
function rows(node, indentPx = 0, inherited = {}) {
  if (node == null || typeof node === 'boolean') return [];
  if (Array.isArray(node)) return node.flatMap(child => rows(child, indentPx, inherited));
  if (typeof node === 'string' || typeof node === 'number') return [{ indentPx, spans: spans(node, inherited) }];
  if (typeof node.type === 'function') return rows(node.type(node.props), indentPx, inherited);
  const style = { ...inherited, ...styleOf(node.props.style) };
  if (node.type === 'Text') return [{ indentPx, spans: spans(node.props.children, style) }];
  return rows(node.props.children, indentPx + (styleOf(node.props.style).paddingLeft ?? 0), style);
}
function render(api, tree, theme, final = false) {
  const nested = api.nestSessions(tree.sessions ?? []);
  const props = { depth: 0, theme, compact: true, now: Date.parse(tree.generated_at), expanded: {}, onToggle() {} };
  const summaryRows = final ? api.panelRows(tree).filter(row => row.kind === 'summary').map(row => ({ indentPx: 0, spans: [{ text: row.text, color: theme.colors.foregroundMuted }] })) : [];
  return [...summaryRows,
    ...nested.roots.flatMap(session => rows(api.SessionBlock({ ...props, session }))),
    ...rows(api.OrphanSideBlock({ ...props, sessions: nested.orphanSides })),
  ];
}
const asText = rendered => rendered.map(row => ' '.repeat(Math.round(row.indentPx / 8)) + row.spans.map(span => span.text).join('')).join('\n') + '\n';
try {
  const tree = JSON.parse(readFileSync(resolve(here, 'runtime-sanitized.json'), 'utf8'));
  const baseline = await bundle(baselineDir);
  const final = await bundle(finalDir, true);
  const before = render(baseline, tree, themes.light);
  const after = render(final, tree, themes.light, true);
  writeFileSync(resolve(here, 'panel-before.txt'), asText(before));
  writeFileSync(resolve(here, 'panel-after.txt'), asText(after));
  const colors = {};
  for (const [name, theme] of Object.entries(themes)) {
    const synthetic = ['running', 'completed', 'failed', 'idle', 'silent', 'unknown', 'lost'].flatMap(status =>
      rows(final.ColoredRowText({ item: { status, provider: 'codex', model: 'fixture-model', effort: 'low' }, name: `fixture-${status}`, now: 0, theme, compact: true })));
    synthetic.push(...rows(final.ColoredSummary({ text: '7 subagent: 2✓ 1✗ ●1 ?3', theme, compact: true })));
    colors[name] = { theme, actualSanitizedRows: render(final, tree, theme, true), syntheticStatesAndCounts: synthetic };
  }
  writeFileSync(resolve(here, 'color-render.json'), JSON.stringify({
    input: 'runtime-sanitized.json only', method: 'Actual baseline/final SessionBlock JSX bundled with installed esbuild; React/native host stubs, nested Text effective colors, paddingLeft retained in pixels; no device screenshot or automated color assertions',
    themes: colors,
  }, null, 2) + '\n');
  console.log(JSON.stringify({ input: 'runtime-sanitized.json', beforeRows: before.length, afterRows: after.length, outputs: ['panel-before.txt', 'panel-after.txt', 'color-render.json'] }));
} finally {
  loadEsbuild.stop();
}
