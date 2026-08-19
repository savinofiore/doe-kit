---
name: riverpod-architect
description: Design the end-to-end state architecture of a Flutter feature before any code exists — picks the Riverpod pattern per piece of state, proposes the file structure, maps the dependencies, and hands the result to /directive as the feature's spec. Writes no application code. Use for a new or complex feature with several interdependent states.
allowed-tools: Read, Glob, Grep, Bash
---

# Riverpod Architect — design the state, then write the directive

Designs the **complete** state architecture of a feature: from the requirement to a file
structure ready to be specified. It produces a design, not code.

## Where this sits in DOE

This runs **before** `/directive`, and it is the reason `/directive` can enumerate its Test
Contract properly. The order matters:

```
riverpod-architect  → the design: what state exists, which pattern, which dependencies
/directive          → the spec: that design + the Test Contract, STATE: DRAFT
human approval      → STATE: APPROVED
/execute NN         → the code
```

Designing the state *is* enumerating the use cases, and enumerating the use cases *is*
enumerating the tests. A feature whose state design is vague produces a vague Test Contract,
and a vague Test Contract produces a green gate that proves nothing.

**This skill writes no application code.** It has no write tools for a reason: the guard would
block it anyway, and it should.

## Configuration

Read `.doe/conventions.json` (`state`, `paths`, `data` sections) for this project's patterns,
registry location and whether codegen is in use. Missing file → ask; do not assume
hand-written providers on a project that uses generation, or vice versa.

## Flow

### Step 1 — Gather the requirements

For the feature, identify:

1. **Entities** involved (models, lists, single objects).
2. **Sources**: which repository, local storage, other providers.
3. **Operations**: fetch, CRUD, pagination, refresh, filters, optimistic mutations.
4. **Dependencies** between states (a filtered list that depends on the current user).
5. **Lifecycle**: app-wide, or scoped to a route (`.autoDispose`).

Ask for whatever is missing. A design built on assumed requirements is the expensive kind of
wrong — it survives review because it is internally consistent.

### Step 2 — Pick a pattern per piece of state

```
Kind of state?
├─ Simple value (bool/int/String/single object)  → simpleValue pattern
├─ List with CRUD
│  ├─ paginated                                  → listPaginated pattern
│  └─ not paginated                              → listCrud pattern
├─ Complex object with logic
│  ├─ depends on other providers                 → complexWithDeps pattern
│  └─ standalone                                 → complexStandalone pattern
└─ One-shot async fetch, never mutated           → readOnlyFetch pattern
```

The concrete class names come from `state.patterns` in the config.

A real feature usually combines several: a paginated list notifier, a filter value, and a
derived provider that combines them. Say so explicitly — a single god-notifier holding all of
it is the most common design smell here, and it is also untestable in pieces.

### Step 3 — Propose the file structure

From `paths` in the config:

```
lib/
├── models/<domain>/<entity>.dart          # the model contract from `data.modelContract`
├── repositories/<domain>_repository.dart  # transport, error mapping
├── providers/<domain>/
│   ├── <feature>_state.dart               # sealed state, when the state is complex
│   └── <feature>_provider.dart            # the notifier
└── pages/<domain>/<feature>_page.dart     # thin view layer
```

Mirror it in the test tree — that mirror is what the directive's Test Contract will fill:

```
test/
├── models/<domain>/<entity>_test.dart
├── repositories/<domain>_repository_test.dart
└── providers/<domain>/<feature>_provider_test.dart
```

Note which of these are **gate-eligible** (models, repositories, providers: yes; pages: no).
That split is what the directive needs to know, and getting it wrong is what produces a feature
where the gate measures nothing.

### Step 4 — Map the dependencies

Who watches whom, and with which API:

- `ref.watch()` → reactive rebuild (build methods, derived providers).
- `ref.read()` → one-shot actions (callbacks, init).
- `ref.listen()` → side effects (navigation, snackbars, chained refresh).
- `ref.invalidate()` / `ref.refresh()` → explicit invalidation.

A derived provider that combines states:

```dart
final unreadCountProvider = Provider<int>((ref) {
  final state = ref.watch(notificationsProvider);
  return state.items.where((n) => !n.isRead).length;
});
```

Derived providers are free to test and cheap to get right — prefer one over duplicating the
same computation in two widgets.

### Step 5 — Output the design

Produce, **before any code**:

1. A table: `piece of state | pattern | file | dependencies | gate-eligible?`
2. Provider and state-class signatures (sealed states listed with their variants).
3. Registration order in the provider registry (repository → notifier → derived).
4. Notes on `.autoDispose` and cleanup.
5. **The use-case list** — one line per behaviour the feature must exhibit, including the
   failure paths (empty list, transport error, unknown enum, unauthorised). This list becomes
   the directive's Test Contract almost verbatim, which is the whole point of doing the design
   first.

Then stop and hand off:

> *"Design ready. Run `/directive` to turn it into a spec with a Test Contract, then approve it
> and `/execute`."*

## Binding rules

- **Immutable state**: never mutate a state collection in place; build a new list and reassign
  through the copy method. This is the single most common source of "the UI does not update"
  and it is trivially testable — which means it belongs in the Test Contract, every time.
- **Sealed states** for complex state, so the view is an exhaustive `switch` with no default
  branch hiding an unhandled case.
- **No business logic in the widget.** Not a style rule: the widget layer is outside the gate
  perimeter, so logic that lives there is logic nothing verifies.
- **Codegen** follows the config. Do not introduce a generator into a project that deliberately
  avoids one.
- Models carry the contract in `data.modelContract`.

## What this skill will not do

- Write providers, models or pages — that is `/execute`, after an approved directive.
- Decide a pattern with the requirements still ambiguous — ask instead.
- Design around an existing bug. If the current state is broken, that is a `/directive` bug flow
  first; redesigning on top of a defect hides it.
