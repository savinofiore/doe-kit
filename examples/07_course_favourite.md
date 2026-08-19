# FEATURE directive: favourite toggle on the course card

> A worked example of a filled FEATURE directive — the artefact `/directive` produces and a
> human approves. Shown at `STATE: APPROVED` (the state that unlocks the guard).
> In a real project this file lives in `.doe/directives/` and is deleted at L3 cleanup.
> Stack in this example: web-ts (`src/` + `tests/`, Vitest).

STATE: APPROVED

## Type

**feature** — new functionality.

## Objective

A user can mark a course as favourite from its card, and unmark it. The state survives a
reload because it is persisted server-side.

## Current vs expected behaviour

| | |
|---|---|
| **Current** | The card shows title, duration and progress. There is no favourite affordance and the domain model carries no such flag. |
| **Expected** | The card shows a toggle. Tapping it calls the repository and updates the state. On a transport error the toggle reverts and an error is surfaced — no optimistic state is kept. |

## Files involved

- `src/core/models/course.ts` — the model gains `isFavourite`
- `src/core/repositories/course-repository.ts` — new `setFavourite`
- `src/core/services/course-service.ts` — orchestration and rollback
- `src/components/course-card.tsx` — the toggle (thin layer, out of the gate)

## Tests involved

- `tests/core/models/course.test.ts`
- `tests/core/services/course-service.test.ts`
- **Baseline:** `.doe/execution/run.sh tests/core` → GREEN before anything (verified: 41 passed).

## Impact on existing tests (default: NONE)

The change is additive: `isFavourite` defaults to `false` when the key is missing, so every
existing parse test stays valid. The table stays **empty** — and that emptiness is a claim the
execution must prove: the existing tests remain green throughout.

| test `file:group` | action | reason → which behaviour changes |
|---|---|---|
| _(empty: backward compatible)_ | | |

## Test Contract (MANDATORY — written BEFORE the code)

### `tests/core/models/course.test.ts`

```ts
describe('Course.parse', () => {
  it('reads isFavourite from the payload', () => {
    expect(Course.parse({ id: '1', title: 'x', is_favourite: true }).isFavourite).toBe(true);
  });

  it('defaults isFavourite to false when the key is missing', () => {
    expect(Course.parse({ id: '1', title: 'x' }).isFavourite).toBe(false);
  });

  it('withFavourite returns a new instance and leaves the original untouched', () => {
    const course = Course.parse({ id: '1', title: 'x' });
    const next = course.withFavourite(true);
    expect(next.isFavourite).toBe(true);
    expect(course.isFavourite).toBe(false);   // no mutation in place
  });
});
```

### `tests/core/services/course-service.test.ts`

```ts
describe('CourseService.toggleFavourite', () => {
  const makeRepo = (overrides = {}) => ({
    setFavourite: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  });

  it('flips the flag and persists it', async () => {
    const repo = makeRepo();
    const service = new CourseService(repo);
    service.load([Course.parse({ id: '1', title: 'x' })]);

    await service.toggleFavourite('1');

    expect(repo.setFavourite).toHaveBeenCalledWith('1', true);
    expect(service.byId('1').isFavourite).toBe(true);
  });

  it('reverts the flag when the repository throws', async () => {
    const repo = makeRepo({ setFavourite: vi.fn().mockRejectedValue(new Error('boom')) });
    const service = new CourseService(repo);
    service.load([Course.parse({ id: '1', title: 'x' })]);

    await expect(service.toggleFavourite('1')).rejects.toThrow();
    expect(service.byId('1').isFavourite).toBe(false);   // rolled back
  });

  it('throws on an unknown id without touching the repository', async () => {
    const repo = makeRepo();
    const service = new CourseService(repo);
    service.load([]);

    await expect(service.toggleFavourite('nope')).rejects.toThrow(/unknown course/i);
    expect(repo.setFavourite).not.toHaveBeenCalled();
  });
});
```

**Edge cases covered:** missing key in the payload, unknown id, transport error and rollback,
no mutation in place.

## Files to change

### MODIFY: `src/core/models/course.ts`

**Add:**

```ts
readonly isFavourite: boolean;

// in parse():  isFavourite: raw.is_favourite ?? false

withFavourite(value: boolean): Course {
  return new Course({ ...this, isFavourite: value });
}
```

### MODIFY: `src/core/repositories/course-repository.ts`

```ts
async setFavourite(id: string, value: boolean): Promise<void> {
  const { error } = await this.client
    .from('courses')
    .update({ is_favourite: value })
    .eq('id', id);
  if (error) throw RepositoryError.from(error);
}
```

### MODIFY: `src/core/services/course-service.ts`

```ts
async toggleFavourite(id: string): Promise<void> {
  const current = this.byId(id);
  if (!current) throw new Error(`unknown course: ${id}`);

  const next = !current.isFavourite;
  this.replace(current.withFavourite(next));      // optimistic
  try {
    await this.repository.setFavourite(id, next);
  } catch (error) {
    this.replace(current);                        // rollback
    throw error;
  }
}
```

## UI/UX

```
┌─────────────────────────────┐
│ Course title            ♡   │  ← toggle, 44×44 target, aria-label
│ 12 min · 40% complete       │
└─────────────────────────────┘
```

Constraints: design tokens only, no hardcoded colours; the icon is not the only state
indicator (`aria-pressed` carries it too). See the `ui-standards` skill.

## Execution plan (L2 — FEATURE flow)

1. Baseline `tests/core` → GREEN.
2. Materialise the six Test Contract tests. Impact table is empty → touch no existing test.
3. `.doe/execution/run.sh tests/core` → **RED** (six failures; the other 41 stay green).
4. Write the production code.
5. `.doe/execution/run.sh` → iterate until **GREEN**.

## Verification (L3)

1. [ ] `.doe/execution/run.sh` exits GREEN (typecheck + lint + whole suite).
2. [ ] Test Contract fully covered, edge cases included.
3. [ ] The 41 pre-existing tests never went red (proof of backward compatibility).
4. [ ] Directive complete → **delete this file** from `.doe/directives/`.

## Notes

- The optimistic update was in the first DRAFT as "keep the state and retry in the background".
  Rejected at review: a favourite that silently un-favourites itself on the next load is worse
  than a visible failure. This is the kind of thing the approval gate is for.
