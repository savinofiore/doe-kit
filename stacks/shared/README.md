# Shared skills

Stack-agnostic convention skills, installed alongside every stack. They are not part of the
DOE gate — they are the conventions the generated code has to satisfy, and the review
checklist leans on them.

| Skill | What it covers |
|---|---|
| [`ui-standards`](skills/ui-standards/) | Accessibility, touch targets, responsive breakpoints, typography, animation timing, light/dark contrast, plus a pre-delivery checklist |
| [`i18n-translator`](skills/i18n-translator/) | Length-preserving translation of localisation JSON, with a validator that fails CI on structural drift, lost placeholders or overflow |

## Why these two and not more

Both encode rules a unit test cannot check but a reviewer can, which is exactly the category
the DOE review splits out as "non-testable → direct fix". Keeping them as skills means the
review has something concrete to point at instead of an opinion.

`i18n-translator` ships `scripts/validate.py`, which is the exception: it *is* mechanical, it
exits non-zero, and it belongs in CI next to the gate.

```bash
python3 .claude/skills/i18n-translator/scripts/validate.py locales/en.json locales/de.json
```

Structural drift in a language file is how a screen silently loses its strings in one locale
and nobody notices for a release.
