---
name: i18n-translator
description: Translate app/UI localization JSON files from a source language into any target language while preserving exact string lengths to prevent UI overflow. Use this skill whenever the user provides a localization JSON (i18n, l10n, language file, translations file) and asks to translate it, localize it, or generate a new language version — including non-Latin scripts like Georgian, Arabic, Japanese, Chinese, Korean, Hebrew, Thai, Hindi. Trigger also for phrases like "traduci questo JSON", "translate this language file", "localize app strings", "generate Spanish version", "add German support", or any request to produce a translated version of an app strings file. Always respect the strict +1 character constraint and preserve placeholders, whitespace, and punctuation style exactly.
---

# i18n Translator (length-preserving)

Translate app localization JSON files into any target language **without breaking UI layouts**. The translated output for every leaf string must have a length within `source_length + 1` characters whenever linguistically possible. When impossible, flag the overflow in a report instead of producing it silently.

## When to use

- User provides a JSON file with UI strings (nested or flat) and asks for a translation into one or more languages.
- User says: "traduci", "translate", "localize", "i18n", "l10n", "add <language>", "generate <language>.json".
- Works for any target language regardless of script (Latin, Cyrillic, Greek, Arabic, Hebrew, CJK, Devanagari, Georgian, Thai, Armenian, etc.).

## Process

1. **Read the source JSON** from the path the user provides (or paste). Identify the source language (usually inferable from the content, or ask if ambiguous).
2. **Confirm target language(s)** with the user if not stated. Accept one or many.
3. **Translate leaf-by-leaf** following the rules in `references/rules.md`. Read that file before producing output — it contains the full character budget algorithm and placeholder protection rules.
4. **Write each translation** to `<target_lang_code>.json` (ISO 639-1 codes: `en.json`, `es.json`, `de.json`, `ka.json` for Georgian, `ja.json`, `ar.json`, etc.).
5. **Validate** the output by running `scripts/validate.py source.json target.json` to check structure, lengths, and placeholders. The script produces a report of any issues.
6. **Present** the translated file(s) and the validation report to the user. Be explicit about every leaf that exceeded the `+1` budget and why — never hide overflows.

## Hard rules (never violate)

1. **Length budget**: `len(translated) <= len(source) + 1` characters. Counting is by Unicode code points (Python `len()` on a `str`), not bytes. This handles CJK and combining marks correctly for almost all UI cases. If the user has a more specific metric (e.g., rendered width), they must say so.
2. **Structure preservation**: the output JSON must have **identical keys, nesting, and order** as the source. Never add, remove, rename, or reorder keys.
3. **Placeholder preservation**: every placeholder in the source must appear identically in the translation, in the same order. Placeholders to detect:
   - `{name}`, `{0}`, `{1}` (Python/ICU style)
   - `{{name}}`, `{{count}}` (Mustache/Handlebars)
   - `%s`, `%d`, `%1$s`, `%@` (printf / iOS style)
   - `$name`, `$1` (shell / bash style)
   - `\n`, `\t`, `\r` (escape sequences)
   - HTML tags `<b>`, `<i>`, `<br/>`, `<a href="...">...</a>` if present
4. **Whitespace preservation**: leading and trailing spaces in the source must be preserved exactly. A source like `" e ti aiuteremo a..."` must translate to `" and we will help you..."` — leading space kept.
5. **Punctuation style**: trailing punctuation (`.`, `...`, `!`, `?`, `:`, `,`) must be preserved. Don't add/remove ellipsis. Don't change `…` ↔ `...`.
6. **Case style**: if the source is ALL CAPS (e.g., `"OK"`, `"CONFIRM"`), the target should be ALL CAPS when natural in the target language (some scripts have no case — leave as-is). If it's Title Case, mirror it. If it's lowercase, mirror it.
7. **Numeric / non-translatable values**: pure numeric strings (`"1"`, `"42"`), URLs, email addresses, single-character symbols, and currency codes (`"EUR"`, `"USD"`) are passed through unchanged.

## Translation algorithm per leaf

For each leaf string `src`:

1. If `src` is empty, numeric-only, a URL/email, or a pure code (e.g., currency code), copy it unchanged.
2. Extract and "freeze" all placeholders, replacing them with sentinels (e.g., `__P0__`, `__P1__`) so they're not translated.
3. Note: leading/trailing whitespace, trailing punctuation, case style.
4. Generate a candidate translation in the target language with the placeholders re-inserted at semantically correct positions.
5. Measure `len(candidate)`. Budget: `len(src) + 1`.
6. **If within budget**: accept.
7. **If over budget**: try up to 4 alternative renderings, in this order:
   - Shorter synonym (`"Confirm"` → `"OK"`, `"Settings"` → `"Setup"` → `"Prefs"`)
   - Common abbreviation accepted in UI for that language (`"Information"` → `"Info"`)
   - Imperative/telegraphic style (`"Please retry"` → `"Retry"`)
   - Drop redundant articles/particles where the target language allows it without becoming ungrammatical.
8. **If still over budget** after step 7: pick the shortest grammatically acceptable form and **mark it as an overflow** in the report (do NOT produce a translation that is wrong or incomprehensible just to fit).

Apply common-sense quality limits: never produce text the average native speaker wouldn't understand. A flagged overflow is better than a meaningless string.

## Language-specific tips

- **German, Russian, Finnish, Hungarian**: words tend to be longer than Italian/English. Expect more overflows; lean on compounds and abbreviations.
- **CJK (Chinese, Japanese, Korean)**: characters are often 1 logical char each but 1 Chinese character usually conveys what 2-4 Latin chars convey, so length budget is rarely a problem.
- **Arabic, Hebrew**: shorter than English in most cases. RTL doesn't affect length.
- **Georgian, Armenian, Thai**: characters per word can be high. Budget can be tight; use shorter native equivalents where idiomatic.
- **Turkish, Finnish**: agglutinative — single words can be very long. Prefer analytic phrasings when over budget.

## Output format

- Write each language to a separate file: `en.json`, `es.json`, `ka.json` (Georgian), `ja.json`, etc.
- Use 2-space indentation, UTF-8, no BOM, `ensure_ascii=False` (so non-Latin scripts are written as native characters, not `\uXXXX` escapes).
- Preserve key order from the source.
- After writing, **always run the validator** and show its output to the user.

## Validation

After producing each target file, run:

```bash
python3 /path/to/skill/scripts/validate.py <source.json> <target.json>
```

The validator reports:
- Missing or extra keys (structural drift)
- Leaves where `len(target) > len(source) + 1` (overflow)
- Leaves where placeholders changed/were lost
- Leaves where leading/trailing whitespace differs

Read `references/rules.md` for the full rule reference and edge-case handling before producing output. Read `references/examples.md` for worked examples covering tricky strings.
