#!/usr/bin/env node
/**
 * DOE L2 — coverage threshold on CHANGED files.
 *
 * Reads `coverage/coverage-summary.json` (produced by `vitest run --coverage`) and checks
 * that every `src/` file touched against the base ref clears the line-coverage threshold.
 *
 * Rule: a changed logic file with no test is red. Global coverage does not matter — what
 * matters is that what you touched in this directive is covered.
 *
 *   node .doe/execution/coverage-check.mjs --min 80 --base main
 */

import { execFileSync } from 'node:child_process';
import { readFileSync, existsSync } from 'node:fs';
import { relative, resolve } from 'node:path';

const ROOT = resolve(import.meta.dirname, '../..');
const SUMMARY = resolve(ROOT, 'coverage/coverage-summary.json');

/**
 * Prefixes exempt from the coverage gate. Keep them aligned with `coverage.exclude` in
 * `vitest.config.ts`: they are the thin layers (routes, components, types, framework glue)
 * that by definition hold no business logic.
 *
 * Moving logic in here is violating the architecture, not earning an exemption.
 */
const EXEMPT_PREFIXES = [
  'src/app/',
  'src/components/',
  'src/types/',
  'src/lib/',
];

const EXEMPT_SUFFIXES = ['.d.ts', '.css', '.json'];

function parseArgs(argv) {
  const args = { min: 80, base: 'main' };
  for (let i = 0; i < argv.length; i += 2) {
    const flag = argv[i];
    const value = argv[i + 1];
    if (flag === '--min') args.min = Number(value);
    else if (flag === '--base') args.base = value;
  }
  if (!Number.isFinite(args.min)) {
    fail(`--min is not a valid number`);
  }
  return args;
}

function fail(message) {
  console.error(`coverage-check: ${message}`);
  process.exit(1);
}

function git(...args) {
  return execFileSync('git', args, { cwd: ROOT, encoding: 'utf8' }).trim();
}

function tryGit(...args) {
  try {
    return git(...args);
  } catch {
    return null;
  }
}

/** Resolves the base ref to a sha, trying the remote variants too. */
function resolveBase(base) {
  for (const candidate of [base, `origin/${base}`, `refs/remotes/origin/${base}`]) {
    const sha = tryGit('rev-parse', '--verify', '--quiet', `${candidate}^{commit}`);
    if (sha) return { ref: candidate, sha };
  }
  return null;
}

function changedFiles(baseSha) {
  // merge-base: compare against the divergence point, not the tip of the base ref, so an
  // advance on main does not drag other people's files into this directive's diff.
  const mergeBase = tryGit('merge-base', baseSha, 'HEAD') ?? baseSha;
  const out = git('diff', '--name-only', '--diff-filter=ACMR', mergeBase, '--');
  return out ? out.split('\n').filter(Boolean) : [];
}

function isExempt(file) {
  return (
    EXEMPT_PREFIXES.some((p) => file.startsWith(p)) ||
    EXEMPT_SUFFIXES.some((s) => file.endsWith(s))
  );
}

const { min, base } = parseArgs(process.argv.slice(2));

if (!existsSync(SUMMARY)) {
  fail(
    `${relative(ROOT, SUMMARY)} not found.\n` +
      `  Run first: npx vitest run --coverage`,
  );
}

const resolved = resolveBase(base);
if (!resolved) {
  console.error(
    `coverage-check: base ref "${base}" not found in the clone.\n` +
      `  CI needs fetch-depth: 0 (or an explicit fetch of the branch).\n` +
      `  Locally: DOE_BASE_REF=<existing-ref> .doe/execution/coverage.sh\n` +
      `  Coverage gate NOT evaluated → red for safety.`,
  );
  process.exit(1);
}

const summary = JSON.parse(readFileSync(SUMMARY, 'utf8'));

/** @type {Map<string, {lines: {pct: number}}>} keys relative to the repo root */
const byFile = new Map();
for (const [key, value] of Object.entries(summary)) {
  if (key === 'total') continue;
  byFile.set(relative(ROOT, resolve(ROOT, key)), value);
}

const changed = changedFiles(resolved.sha).filter(
  (f) => f.startsWith('src/') && !isExempt(f),
);

if (changed.length === 0) {
  console.log(`No logic file changed vs ${resolved.ref} — coverage gate n/a.`);
  process.exit(0);
}

const failures = [];
const rows = [];

for (const file of changed) {
  const entry = byFile.get(file);
  if (!entry) {
    // Not exempt and not in the report: either it was just created and vitest never saw
    // it, or `coverage.all` is not working. Either way, it is not covered.
    failures.push({ file, pct: 0, reason: 'absent from the coverage report' });
    rows.push([file, '0.00%', 'MISSING']);
    continue;
  }
  const pct = entry.lines?.pct ?? 0;
  const ok = pct >= min;
  if (!ok) failures.push({ file, pct, reason: `below threshold` });
  rows.push([file, `${pct.toFixed(2)}%`, ok ? 'OK' : 'RED']);
}

const width = Math.max(...rows.map(([f]) => f.length), 4);
for (const [file, pct, status] of rows) {
  console.log(`  ${file.padEnd(width)}  ${pct.padStart(8)}  ${status}`);
}

console.log(
  `\n${changed.length} logic files changed vs ${resolved.ref}, threshold ${min}% (lines).`,
);

if (failures.length > 0) {
  console.error(`\n${failures.length} files below threshold:`);
  for (const { file, pct, reason } of failures) {
    console.error(`  ✗ ${file} — ${pct.toFixed(2)}% (${reason})`);
  }
  console.error(
    `\nA changed logic file with no test is red.\n` +
      `Add the missing tests in tests/ (mirror of src/); do not lower the threshold.`,
  );
  process.exit(1);
}

console.log('Every changed file is above threshold.');
