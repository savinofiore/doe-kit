---
name: scaffold-feature
description: Scaffold a complete Flutter feature — model, repository, state, provider, page, component, route, translations and the mirrored tests — following Clean Architecture and the project's own conventions from .doe/conventions.json. Runs as the implementation step of an approved directive, never on its own.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Scaffold Feature — the whole slice, tests included

Scaffolds a complete feature: model → repository → state → provider → page → component →
route → translations, plus the mirrored test files.

## Where this sits in DOE

**This is an implementation step. It runs inside `/execute NN`, on an APPROVED directive.**

Ask yourself which situation you are in:

| Situation | What to do |
|---|---|
| No directive yet | Do NOT scaffold. Run `riverpod-architect` for the design, then `/directive`. This skill's structure section is what the directive's "Files to change" should contain. |
| Directive APPROVED, executing it | Scaffold — in the order below, tests first. |
| Directive is DRAFT | Stop. The guard blocks `lib/` anyway. |

The order inside `/execute` is not negotiable and it is the opposite of the intuitive one:

```
1. baseline gate                                    → green
2. scaffold the TEST files from the Test Contract   → run gate → RED (nothing exists yet)
3. scaffold model → repository → state → provider   → gate goes green piece by piece
4. scaffold page → component → route → translations → outside the gate perimeter
5. full gate                                        → green
```

Scaffolding production code before the tests produces tests written to match whatever the code
happened to do. That is the failure this whole system exists to prevent, and a scaffolder is
the easiest place to reintroduce it.

## Configuration

Read `.doe/conventions.json` — `package`, `paths`, `naming`, `tokens`, `state`, `data`, `i18n`.
Every name in the templates below comes from there. Missing file → stop and ask; do not copy
another project's design system into this one.

## Step 1 — Requirements (from the directive, not from scratch)

If the directive is complete, these are already in it. Read them from there. Ask only for what
is genuinely missing:

1. **Domain name** (`rewards`, `badges`, `notifications`)
2. **Feature type**: list · list+detail · CRUD · dashboard
3. **Pagination?**
4. **Model fields** and their JSON keys
5. **Endpoint**

Before creating anything, check the domain does not already exist:

```bash
grep -rn "class <Model>" lib/models/
grep -rn "class <Domain>Repository" lib/repositories/
```

## Step 2 — Tests first (from the directive's Test Contract)

Materialise the test files the directive specified. Mirror paths:

```
test/models/<domain>/<entity>_test.dart
test/repositories/<domain>_repository_test.dart
test/providers/<domain>/<feature>_provider_test.dart
```

Run the gate. **They must be RED** — the production classes do not exist yet, so they fail to
compile. That is the correct red. Confirm it before writing a line of production code.

Cover, at minimum: parse with every field, parse with missing/null keys, the copy contract, the
empty-list case, the mapped transport error, and each state transition the design named.

## Step 3 — Model

`<paths.models><entity>.dart` — the contract from `data.modelContract`, hand-written when
`data.codegen` is false.

```dart
import 'package:<package>/utils/json.dart';

class <Entity> {
  final String id;
  final String title;
  final String? imageUrl;

  const <Entity>({required this.id, required this.title, this.imageUrl});

  factory <Entity>.fromJson(JSON json) => <Entity>(
        id: json['id'] as String,
        title: json['title'] as String,
        imageUrl: json['image_url'] as String?,
      );

  JSON toJson() => {'id': id, 'title': title, 'image_url': imageUrl};

  <Entity> copyWith({String? id, String? title, String? imageUrl}) => <Entity>(
        id: id ?? this.id,
        title: title ?? this.title,
        imageUrl: imageUrl ?? this.imageUrl,
      );
}
```

Use the **exact** JSON keys from the backend. A guessed key produces a null at runtime and a
green test, because the test was written against the same guess.

## Step 4 — Repository

`<paths.repositories><domain>_repository.dart`. Transport and client accessor from `data`.

```dart
class <Domain>Repository {
  final Ref _ref;
  <Domain>Repository(this._ref);

  Future<List<<Entity>>> get<Entity>s() async {
    const String path = '<domain>';
    try {
      final response = await <data.clientAccessor>.get(path);
      final List<JSON> data = response.data as List<JSON>;
      return data.map(<Entity>.fromJson).toList();
    } on DioException catch (_) {
      throw <data.errorType>();
    }
  }
}
```

Paginated variant: take the page number, read the items and the next-page cursor from the
envelope, and return the updater type the project uses.

The repository is gate-eligible: its error mapping is exactly the kind of thing that breaks
silently and that a mocked-transport test catches in three lines.

## Step 5 — State (when the state is complex)

`<paths.state><feature>_state.dart`, sealed when `state.sealedStates` is true:

```dart
sealed class <Domain>State {}

class <Domain>InitialState extends <Domain>State {}
class <Domain>LoadingState extends <Domain>State {}
class <Domain>ErrorState extends <Domain>State {
  final String message;
  <Domain>ErrorState(this.message);
}
class <Domain>DataState extends <Domain>State {
  final List<<Entity>> items;
  <Domain>DataState({required this.items});
  <Domain>DataState copyWith({List<<Entity>>? items}) =>
      <Domain>DataState(items: items ?? this.items);
}
```

Skip this file entirely for a read-only fetch: `state.patterns.readOnlyFetch` needs no state
class, and inventing one is ceremony the next reader has to decode.

## Step 6 — Provider

`<paths.state><feature>_provider.dart`, using the pattern the design picked.

```dart
class <Domain>Provider extends StateNotifier<<Domain>State> {
  final <Domain>Repository _repository;
  <Domain>Provider(this._repository) : super(<Domain>InitialState());

  Future<void> load() async {
    state = <Domain>LoadingState();
    try {
      state = <Domain>DataState(items: await _repository.get<Entity>s());
    } catch (err) {
      state = <Domain>ErrorState(err.toString());
    }
  }
}
```

Never mutate a state collection in place. Every transition assigns a new state object with a
new list.

## Step 7 — Register

Add to `<paths.providerRegistry>`, in dependency order — repository, then notifier, then
derived providers:

```dart
final <domain>RepositoryProvider =
    Provider<<Domain>Repository>((ref) => <Domain>Repository(ref));

final <domain>Provider =
    StateNotifierProvider<<Domain>Provider, <Domain>State>(
        (ref) => <Domain>Provider(ref.watch(<domain>RepositoryProvider))..load());
```

An unregistered provider fails at runtime, not at analysis time. Check this before saying done.

## Step 8 — Page and component

`<paths.pages><feature>_page.dart` and `<paths.componentsLocal><feature>_card.dart`.

Rules, all from the config:

- Class name: `<Domain>` + `naming.pageSuffix`; component prefixed with `naming.componentPrefix`.
- `static const String path` when `naming.pageRequiresStaticPath`.
- **Colours, text styles, radii and sizes come from tokens only** — no literals. See the
  `fix-style` skill for the mapping.
- User-visible strings go through `i18n.call`, never inline.
- An exhaustive `switch` over the sealed state, no default branch.

This layer is **outside the gate perimeter**. It is not exempt from being correct; it is exempt
from being measured — which is precisely why the logic must not drift into it.

## Step 9 — Route and translations

Add the route to `<paths.routes>`, and the keys to `<i18n.files>` following `i18n.keyStyle`:

```json
{
  "<domain>": {
    "title": "…",
    "empty": "…",
    "error": "…"
  }
}
```

Add the keys to **every** locale file, not just the default one. A key present in one locale
and missing in another is a runtime blank in production, and no test in the gate sees it.

## Step 10 — Green gate and checklist

- [ ] Tests were RED before the production code existed
- [ ] `.doe/execution/run.sh` GREEN (analyze + whole suite)
- [ ] Model contract complete, JSON keys verified against the backend
- [ ] Repository maps its errors
- [ ] Provider registered in the registry
- [ ] No state collection mutated in place
- [ ] Page has the static path; component follows the prefix
- [ ] Zero hardcoded colours/styles/sizes/radii — run `fix-style` on the new folder
- [ ] Translation keys in every locale file
- [ ] Route reachable
- [ ] Directive checklist complete → delete the directive (L3)

## Extensions

**Detail page**: add `<paths.pages>pages/<feature>_detail_page.dart` and a parameterised route
(`/<domain>/:id`), with a `FutureProvider.family` for the by-id fetch.

**Full CRUD**: add `create` / `update` / `delete` to the repository — and a test per method to
the directive's Test Contract. A CRUD scaffold with tests only on `read` is the usual way the
coverage gate ends up green over a half-tested feature.

**Domain error type**: when the feature needs its own error, add it next to the project's other
API errors, with the matching translation keys.

## RULES

- **Never scaffold without an APPROVED directive.**
- **Tests before production code**, always, in that order.
- **Config first** — no `.doe/conventions.json`, no scaffold.
- **Never invent JSON keys.** Ask, or read the API contract.
- **Never add a dependency** (a codegen package, a state library) that the config says the
  project avoids.
- Report what was created, what went RED then GREEN, and anything left for the user to decide.
