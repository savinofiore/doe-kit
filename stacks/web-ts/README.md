# Stack: web-ts (TypeScript · Vitest)

Target: Next.js / React / Node projects with `tsc`, `eslint` and Vitest.

Protected roots: **`src/`** and **`tests/`**.

## Gate

```bash
.doe/execution/run.sh                    # typecheck + lint + whole unit suite
.doe/execution/run.sh tests/core/models  # narrow to a path
.doe/execution/run.sh --name "Post"      # filter by test name
.doe/execution/run.sh --quick            # skip lint (fast RED→GREEN loop)

.doe/execution/coverage.sh               # full gate: + coverage threshold on changed files
DOE_COVERAGE_MIN=90 .doe/execution/coverage.sh
DOE_BASE_REF=develop .doe/execution/coverage.sh
```

`run.sh` is the fast gate for the red→green loop. `coverage.sh` is the one that runs in CI.

`coverage-check.mjs` reads `coverage/coverage-summary.json` and enforces the threshold on every
`src/` file changed against the merge-base with the base ref. Keep its `EXEMPT_PREFIXES` in
sync with `coverage.exclude` in `vitest.config.ts`.

### Required Vitest config

```ts
// vitest.config.ts
export default defineConfig({
  test: {
    environment: 'node',          // no jsdom: gate tests are framework-free
    include: ['tests/**/*.test.ts'],
    coverage: {
      all: true,
      reporter: ['text', 'json-summary'],   // json-summary is what coverage-check.mjs reads
      include: ['src/**/*.ts'],
      exclude: ['src/app/**', 'src/components/**', 'src/types/**', 'src/lib/**'],
    },
  },
});
```

`json-summary` is not optional: without it `coverage/coverage-summary.json` never appears and
the coverage gate fails red for safety.

## Test scope

- **Unit tests only.** No component or E2E tests inside the gate.
- **Environment `node`, no jsdom.** If a test needs the DOM, the logic is in the wrong place:
  move it into `src/core/`.
- **What gets tested** (all of it lives in `src/core/`, framework-free):
  - **Models / schemas** → `parse`, `Row → Domain` mappers, enum parsing, edge cases (null,
    missing keys, wrong types).
  - **Services (use cases)** → orchestration with injected fake repositories.
  - **Repositories** → transport client mocked, response and error mapping.
  - **Utils** → pure functions.
- **Mocking:** Vitest `vi.fn()` and hand-written fakes. No codegen, no external mocking library.
- **`tests/` mirrors `src/`** (`src/core/models/post.ts` → `tests/core/models/post.test.ts`).

## Architecture constraints the generated code must respect

- **Business logic never lives in a component or a hook**: it lives in `src/core/` and gets
  imported. `src/app/` and `src/components/` are thin layers.
- **Repository pattern is mandatory**: no direct database or API calls from components, route
  handlers or server actions. Always through `src/core/repositories/`.
- **The data client is injected**, never imported inside a repository — that injection is what
  makes the repository testable.
- **One validation point at the boundary** (DB → domain, form → domain), with a schema library.
- **Server-only secrets never cross the client boundary.**

These are not style preferences: the first three are what make a deterministic offline gate
possible at all.

## Recommended permissions

`.claude/settings.json` — so the agent can run the gate without a prompt each time:

```json
{
  "permissions": {
    "allow": [
      "Bash(.doe/execution/run.sh:*)",
      "Bash(.doe/execution/coverage.sh:*)",
      "Bash(.doe/execution/directive_guard.py:*)",
      "Bash(npx vitest run:*)",
      "Bash(npx tsc --noEmit)",
      "Bash(npm run lint:*)",
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(git log:*)"
    ]
  }
}
```
