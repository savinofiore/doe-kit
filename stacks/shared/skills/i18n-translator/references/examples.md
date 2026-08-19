# Worked Examples

Examples drawn from real fintech app strings. Each shows source, char count, target candidates, and the chosen output.

## Example 1: Short button label

```
Source (it):  "OK"           (2 chars)
Target (en):  "OK"           (2 chars) ✓ in budget
Target (de):  "OK"           (2 chars) ✓ in budget
Target (ka):  "კარგი"        (5 chars) ✗ overflow +3 — FLAG
```

For Georgian, no shorter natural form exists. Output `"კარგი"` and flag.

## Example 2: Title with ellipsis

```
Source (it):  "Ops..."       (6 chars)
Target (en):  "Oops..."      (7 chars) ✓ +1, exactly at budget
Target (es):  "Vaya..."      (6 chars) ✓ in budget
Target (de):  "Hoppla..."    (8 chars) ✗ overflow +2 — try shorter
                "Ups..."     (6 chars) ✓ in budget — USE
```

Note the trailing `...` is preserved exactly (3 ASCII dots, not Unicode `…`).

## Example 3: Sentence with leading space (concatenation glue)

```
Source (it):  " e ti aiuteremo a risolvere il problema."   (40 chars)
Target (en):  " and we'll help you solve the problem."     (38 chars) ✓
Target (es):  " y te ayudaremos a resolver el problema."   (40 chars) ✓
```

Leading space preserved. Trailing period preserved.

## Example 4: Connectivity message

```
Source (it):  "Sembra che tu sia in una zona sperduta... prova a cambiare rete e riprova."   (74 chars)
Target (en):  "Looks like you're in a dead zone... try switching networks and retry."        (69 chars) ✓
```

## Example 5: Months (numeric keys, named values)

```
Source:  "1": "Gennaio"     (7 chars)
EN:      "1": "January"     (7 chars) ✓
DE:      "1": "Januar"      (6 chars) ✓
KA:      "1": "იანვარი"      (7 chars) ✓ (fits exactly)
JA:      "1": "1月"          (2 chars) ✓ (much shorter, fine)
```

Note: the key `"1"` is **not** translated. Only the value.

## Example 6: Placeholder preservation

```
Source (it):  "Ciao {name}, hai {count} notifiche."   (33 chars, 2 placeholders)
Target (en):  "Hi {name}, you have {count} alerts."   (35 chars) ✗ overflow +2
                                                       Try: "Hi {name}, {count} new alerts."   (29 chars) ✓ — USE
```

Both placeholders preserved in same order. Final translation is shorter than source — that's allowed.

## Example 7: Function word (very short, often impossible)

```
Source (it):  "e"            (1 char)
Target (en):  "and"          (3 chars) ✗ overflow +2 — FLAG
Target (es):  "y"            (1 char) ✓
Target (de):  "u."           (2 chars) abbreviation, but unusual; better:
                "und"        (3 chars) ✗ overflow +2 — FLAG
```

For function words, overflow is often unavoidable. Always flag.

## Example 8: ALL CAPS button

```
Source (it):  "CONFERMA"     (8 chars)
Target (en):  "CONFIRM"      (7 chars) ✓
Target (es):  "CONFIRMAR"    (9 chars) ✗ overflow +1, but exactly at budget
                                       Wait, source is 8, budget is 9 → ✓ within budget
Target (de):  "BESTÄTIGEN"   (10 chars) ✗ overflow +2 — try shorter
                "OK"         (2 chars) — wrong meaning, don't use
                "JA"         (2 chars) — different meaning
                Pick: "BESTÄTIGEN" — FLAG
```

When no shorter form preserves meaning, flag.

## Example 9: ICU plural

```
Source (en):  "{count, plural, one {# item} other {# items}}"
Target (it):  "{count, plural, one {# elemento} other {# elementi}}"
```

Translate inside the branches. Keep the ICU structure exactly.

## Example 10: Brand / non-translatable

```
Source:  "Powered by Stripe"           (17 chars)
Target:  "Powered by Stripe"           (17 chars) — keep "Stripe" untranslated
```

Brand names are pass-through.

---

## How the validator output looks

After translating, run the validator. Sample output for a partial translation:

```
i18n validation: it.json → de.json
==================================
✓ Structure: 47/47 keys match
⚠ Overflow: 3 leaves exceed source_length + 1
✓ Placeholders: all preserved
✓ Whitespace: all preserved

Overflow details:
  common.ok               src=2  tgt=2  Δ=0   ✓
  and                     src=1  tgt=3  Δ=+2  ✗  "e" → "und"
  generic_error.button    src=6  tgt=10 Δ=+4  ✗  "Chiudi" → "Schließen"
  months.1                src=7  tgt=6  Δ=-1  ✓

Total: 44 ✓ within budget, 3 ✗ overflow
```

Always show the user this output verbatim alongside the translated file.
