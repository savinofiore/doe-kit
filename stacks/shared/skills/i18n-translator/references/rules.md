# Translation Rules — Full Reference

This file is the authoritative reference for the i18n-translator skill. Read it before producing any translation output.

## Character counting

- Use Unicode **code point** count: `len(string)` in Python.
- This is what most UI frameworks measure when they decide to truncate or wrap (Flutter `String.length`, JavaScript `String.length`, Swift `String.count`).
- A combining mark (e.g., `é` written as `e + ´`) counts as 2 code points. Prefer the precomposed form (`é` = 1 code point).
- Emoji generally count as 1 grapheme cluster but 1+ code points; in practice, treat them as 2 code points unless you know the framework counts graphemes.

## Length budget

- Hard rule: `len(translation) ≤ len(source) + 1`.
- Soft preference: equal length when possible. Many UI containers are sized exactly to the source string.
- `+1` is for languages where one extra character is unavoidable for grammatical agreement (gender, articles, plural marks).

## Placeholder taxonomy and protection

| Type | Example | Notes |
|------|---------|-------|
| Curly single | `{name}`, `{0}`, `{count}` | Python format / ICU MessageFormat |
| Curly double | `{{name}}` | Mustache / Handlebars / some Vue |
| Printf | `%s`, `%d`, `%f` | C / Java / Dart `sprintf` |
| Printf positional | `%1$s`, `%2$d` | iOS / Android resources |
| Apple style | `%@` | Objective-C / Swift `NSString` |
| Dollar | `$name`, `$1` | Bash / Kotlin string templates |
| Escape | `\n`, `\t`, `\r`, `\\` | Newlines and tabs |
| HTML | `<b>`, `<br/>`, `<a href="x">y</a>` | Inline tags in some i18n strings |
| ICU plurals | `{count, plural, one {...} other {...}}` | Whole construct must be preserved; translate inside the branches |

**Protection algorithm:**
1. Detect every placeholder using regex (a Python pattern that matches all of the above).
2. Replace each placeholder with a unique sentinel: `__P0__`, `__P1__`, ...
3. Translate the resulting "skeleton" string.
4. Restore placeholders by replacing sentinels with the original tokens.
5. Verify count matches; if not, abort that leaf and flag it.

## Whitespace handling

- Leading/trailing spaces are **always meaningful** in i18n files. They're often deliberate concatenation glue: `" and "` is meant to sit between two other strings.
- Algorithm: capture the source's leading and trailing whitespace, translate the trimmed middle, re-attach.
- Internal whitespace (multiple spaces, tabs) should be preserved as-is.

## Punctuation style

- Preserve trailing punctuation: `.`, `...`, `…`, `!`, `?`, `:`, `;`, `,`, `…`.
- `...` (three ASCII dots) and `…` (Unicode ellipsis) are different characters and different lengths. Don't substitute one for the other.
- Some languages have language-specific punctuation:
  - Spanish opening `¿`, `¡` — add them when translating questions/exclamations into Spanish (this consumes characters from the budget!).
  - French requires non-breaking space before `:`, `;`, `?`, `!` in formal typography. **Skip this rule for app UIs** — it's almost never used and inflates length.
  - Greek question mark is `;` (semicolon).
  - Arabic question mark is `؟`, comma is `،`.
- For CJK: Chinese/Japanese full-width punctuation (`。`, `，`, `？`) takes 1 code point, like ASCII. Use full-width when natural.

## Case preservation

| Source case | Action |
|-------------|--------|
| `OK`, `CANCEL` (ALL CAPS) | Render target ALL CAPS when target script supports case. CJK / Arabic / Hebrew / Georgian / Thai have no case → leave as-is. |
| `Save`, `Try Again` (Title Case) | Render Title Case in target. |
| `save`, `try again` (lowercase) | Render lowercase in target. |
| `iPhone`, `eBay`, `iOS` (mixed/brand) | Pass through unchanged — these are brands. |

## Non-translatable strings

Pass through unchanged:
- Pure numeric: `"1"`, `"42"`, `"3.14"`
- ISO currency / country codes: `"EUR"`, `"USD"`, `"IT"`, `"US"`
- URLs and email addresses
- Single-character symbols: `"+"`, `"-"`, `"×"`, `"©"`
- Hex colors: `"#FF0000"`
- File extensions: `".pdf"`, `".jpg"`
- Pure punctuation: `"…"`, `":"`

## Edge cases

### Very short source strings (1-3 chars)

- Sources like `"OK"`, `"e"` (Italian "and"), `"Yes"` are the hardest to keep within budget for languages with no equivalent short word.
- Strategy: prefer the natural short word in the target. If no short equivalent exists, use the shortest acceptable form even if longer than `source + 1`, **and flag it**.
- For function words (`"e"` → `"and"` is 3 chars vs source 1 char → +2 over budget), this is unavoidable. Flag in report.

### Empty strings

- An empty source (`""`) translates to `""`. Don't invent text.

### Strings that are already English (or mixed)

- If the source language file contains some untranslated English (common when devs leave English fallbacks), translate them normally to the target.

### Months, weekdays, numbers spelled out

- These have established names in every language. Use the canonical localized form even if longer.
- Months are particularly tricky: Italian "Gennaio" (7 chars) → German "Januar" (6, fits), → Russian "Январь" (6, fits), → Georgian "იანვარი" (7, fits exactly).

### Honorifics, formality

- Match the source's formality level. If the source uses `"tu"` form (Italian informal), use `"du"` (German), `"tú"` (Spanish), `"ты"` (Russian), etc.
- Japanese: pick formality based on source tone (casual vs polite vs honorific).

## Quality vs. length trade-off

If forcing a translation into the length budget produces text that:
- A native speaker would not understand
- Is grammatically broken
- Is offensive or culturally inappropriate
- Loses essential meaning (e.g., omits "not" in a negative)

Then **do not produce it**. Pick the shortest acceptable correct form and **flag it as an overflow**. The user can then decide whether to expand the UI container or accept the natural length.

## What to flag in the report

For every leaf that has any of these conditions:
- `len(target) > len(source) + 1`
- Placeholder count or order differs
- Leading/trailing whitespace differs
- Source had case style X but target has case style Y due to script limitations

The report shows: key path, source, target, source length, target length, delta, reason.
