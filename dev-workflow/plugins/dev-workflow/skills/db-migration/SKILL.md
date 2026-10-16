---
name: db-migration
description: Add or change a database schema safely through a new numbered SQL migration (NNN_snake_case.sql) - never edit an applied migration (checksum ledger), fix forward, make DDL idempotent with IF NOT EXISTS / IF EXISTS, one transaction per migration, never hand-edit the ledger table, and update the store/repository code, integration tests, schema snapshot and table catalog in the same change. Use this whenever a task adds, drops or alters a table, column, index or constraint, touches the migrations folder, or hits a migration checksum/ledger error. Vietnamese triggers - "migration", "thêm cột", "thêm bảng", "đổi schema", "sửa bảng", "lỗi checksum", "bootstrap lỗi", "DB".
---

# Database Migration

## Summary

- **Purpose:** every schema change reaches every database (fresh and existing) the same way, through an
  ordered, immutable, idempotent migration, and the code and docs that read the schema move with it.
- **Core rules:**
  1. One new file `NNN_snake_case.sql` per change; next free number, three digits.
  2. An applied migration is immutable (comments and blank lines included). Fix forward with a new file.
  3. DDL is idempotent: `IF NOT EXISTS` / `IF EXISTS`.
  4. One transaction per migration; no statements that cannot run inside a transaction.
  5. Never edit the ledger table by hand and never apply a migration by hand with a SQL client.
  6. Same change updates: store/repository code, integration tests, schema snapshot (if the repo keeps
     one), table catalog doc.
  7. Destructive bootstrap (`--drop` or equivalent) only on test databases.
- **Lane:** a schema change is at least L1; when it changes an API/contract or spans modules it is L2
  (`dev-workflow:spec-plan` first).
- **Config keys used:** `[paths].migrations` (empty = auto-detect), `[docs_map]` (table catalog /
  schema docs), `[gate].commands`, `[gate].lint`, `[project].max_file_lines`; read with `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config --json` (see `${CLAUDE_PLUGIN_ROOT}/skills/dev-triage/references/config-defaults.md`).

## 1. Locate the repo's migration setup

### 1.1 Find the folder and conventions

- First `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config --get paths.migrations`. A non-empty value is the authoritative folder; if it
  does not exist, report the config error instead of guessing.
- Empty value (or no config): search `git ls-files | grep -E '(^|/)(db/)?migrations/'` (typical:
  `<backend>/db/migrations/`). If several or none match, ask the user which folder is authoritative and
  suggest recording it in `[paths].migrations`.
- Read the newest 2-3 migrations and the runner (bootstrap script or migration tool) to learn:
  numbering width and filename regex, ledger table name, checksum algorithm, whether a schema snapshot
  (e.g. `db/schema.sql`) runs before migrations, and how tests build their database.
- If the repo has a `.claude/rules/migrations.md` or a migrations section in `AGENTS.md`, it overrides
  the defaults here when stricter.

### 1.2 Decide whether a migration is "applied"

- Applied = it has run against **any** database (shared, staging, a teammate's dev DB). It is committed
  on a shared branch → treat as applied.
- Only a migration that never left your working tree may be edited. When in doubt, treat it as applied.

## 2. Write the migration

### 2.1 File

- Name: next number after the highest existing one, `NNN_<verb>_<object>.sql`
  (e.g. `042_add_status_to_orders.sql`), lowercase snake_case, matching the repo's regex.
- Header comment: purpose and the ticket/spec ID. Written once - you cannot fix it later.

### 2.2 Statements

- `CREATE TABLE/INDEX ... IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`,
  `DROP ... IF EXISTS`. A fresh database may already contain the object from the schema snapshot, so a
  bare `CREATE` passes on old databases and fails on new ones - the failure nobody sees until later.
- Constraints without `IF NOT EXISTS` support: guard with a `DO` block or a catalog check.
- Keep the migration transactional; split out statements that cannot run in a transaction
  (e.g. `CREATE INDEX CONCURRENTLY`) and follow the repo's documented exception, or ask.
- CHECK constraints must never evaluate to NULL: every branch comparing a nullable column needs an
  `IS NOT NULL` conjunct in the same branch (NULL passes a CHECK). Read column nullability from
  `information_schema.columns` instead of judging the expression's shape.
- Backfills: deterministic, idempotent, batched for large tables; any `ORDER BY ... LIMIT` ends in a
  unique column.
- Data-destroying changes (drop column/table, narrowing type) need explicit user approval first.

### 2.3 Fixing a mistake

- Wrong DDL in an applied migration → new migration that corrects it.
- Wrong comment in an applied migration → document in the spec, schema snapshot or
  `COMMENT ON ...` in a new migration; leave the old file byte-identical.
- Accidentally edited an applied file → revert it byte-for-byte (`git checkout -- <file>`). If it was
  already applied somewhere with the new checksum, report it; do not patch the ledger yourself.
- Applied out of band → use the runner's documented baseline/repair command, never a hand `INSERT`.

## 3. Move everything that reads the schema

| Surface | What to do |
|---|---|
| Schema snapshot (if any) | Mirror the change, marked with `-- migration NNN` |
| Store / repository / ORM code | Read and write the new columns; remove use of dropped ones |
| Queries already reading the table | `grep` the table and column names across the repo; update each |
| Fixtures, factories, fakes | Add the new column/default so tests reflect the real shape |
| Integration tests | Cover the new behaviour against a real database (not a mock) |
| API types / contracts | If exposed, update schemas and client types together |
| Table catalog doc | Path from `[docs_map]`; if no entry, ask where the catalog lives |

## 4. Verify

- Apply on a **fresh** database (built from scratch) and on an **existing** one (previous schema): both
  must succeed, and re-running the bootstrap must be a no-op.
- Run the integration tests that touch the table, then `[gate].commands` and `[gate].lint`.
- If the repo has a ledger-drift checker, run it.
- Destructive reset (`--drop`, `DROP DATABASE`, volume wipe) only on a database whose name marks it as a
  test database, or with the runner's explicit confirm flag; never on a shared or production database.
- Report: migration filename, fresh + existing DB results, tests and gate commands with results, docs updated.

## Brain/hand split

- **Brain:** decides whether the change needs spec/plan (L2), approves destructive changes, reviews the
  migration and every surface in section 3.
- **Hand:** writes the migration and code changes, runs fresh/existing DB checks and tests. The brief
  names the migrations folder, the next number and the surfaces to update; a hand that hits a checksum
  error stops and reports instead of touching the ledger.
