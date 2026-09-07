#!/usr/bin/env python3
"""
Validator for length-preserving i18n translations.

    python3 validate.py <source.json> <target.json> [--budget 1]

Checks four things, and reports every violation with its full key path:

  1. STRUCTURE  — identical keys and nesting. Missing or extra keys are drift, and drift is
                  how a language file silently loses a screen.
  2. LENGTH     — len(target) <= len(source) + budget, counted in Unicode code points.
  3. PLACEHOLDERS — every placeholder in the source appears in the target, same multiset.
  4. WHITESPACE — leading and trailing whitespace preserved exactly.

Exit code 0 when clean, 1 when any check fails, so it can be wired into CI.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Placeholder families the translator must never touch. Kept in one regex so the multiset
# comparison below sees them all as equal citizens.
PLACEHOLDER_RE = re.compile(
    r"""(
        \{\{[^{}]*\}\}        # {{name}}  mustache / handlebars
      | \{[^{}]*\}            # {name}, {0}  ICU / python
      | %\d+\$[@sdif]         # %1$s  positional printf
      | %[@sdif]              # %s, %d, %@
      | \$\{[^{}]*\}          # ${name}
      | \$[A-Za-z_][A-Za-z0-9_]*  # $name
      | </?[A-Za-z][^<>]*/?>  # <b>, </b>, <br/>, <a href="...">
      | \\[nrt]               # escape sequences, literal in JSON source text
    )""",
    re.VERBOSE,
)

PASSTHROUGH_RE = re.compile(
    r"""^(
        \s*                                  # empty / whitespace only
      | [\d\s.,:+\-]*                        # numeric-ish
      | https?://\S+                         # url
      | [^@\s]+@[^@\s]+\.[^@\s]+             # email
      | [A-Z]{3}                             # currency code
    )$""",
    re.VERBOSE,
)


def flatten(node, prefix: str = "") -> dict[str, str]:
    """Flattens a nested translation object into {dotted.key: leaf string}."""
    flat: dict[str, str] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            flat.update(flatten(value, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            flat.update(flatten(value, f"{prefix}[{index}]"))
    else:
        flat[prefix] = node if isinstance(node, str) else json.dumps(node, ensure_ascii=False)
    return flat


def placeholders(text: str) -> list[str]:
    return sorted(m.group(0) for m in PLACEHOLDER_RE.finditer(text))


def edges(text: str) -> tuple[str, str]:
    """Leading and trailing whitespace, which carry meaning in concatenated UI strings."""
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()) :]
    return lead, trail


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"validate: file not found: {path}")
    except json.JSONDecodeError as exc:
        sys.exit(f"validate: {path} is not valid JSON — {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a length-preserving translation.")
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--budget", type=int, default=1, help="extra characters allowed (default 1)")
    args = parser.parse_args()

    src = flatten(load(args.source))
    dst = flatten(load(args.target))

    missing = sorted(set(src) - set(dst))
    extra = sorted(set(dst) - set(src))

    overflow: list[tuple[str, int, int, str, str]] = []
    lost_placeholders: list[tuple[str, list[str], list[str]]] = []
    whitespace: list[tuple[str, str, str]] = []

    for key in sorted(set(src) & set(dst)):
        s, t = src[key], dst[key]

        if PASSTHROUGH_RE.match(s):
            if s != t:
                whitespace.append((key, repr(s), repr(t)))
            continue

        budget = len(s) + args.budget
        if len(t) > budget:
            overflow.append((key, len(t), budget, s, t))

        ps, pt = placeholders(s), placeholders(t)
        if ps != pt:
            lost_placeholders.append((key, ps, pt))

        if edges(s) != edges(t):
            whitespace.append((key, repr(edges(s)), repr(edges(t))))

    print(f"source: {args.source}  ({len(src)} leaves)")
    print(f"target: {args.target}  ({len(dst)} leaves)")
    print(f"budget: source length + {args.budget}\n")

    failed = False

    if missing or extra:
        failed = True
        print(f"STRUCTURE — {len(missing)} missing, {len(extra)} extra")
        for key in missing:
            print(f"  ✗ missing in target: {key}")
        for key in extra:
            print(f"  ✗ not in source:     {key}")
        print()

    if lost_placeholders:
        failed = True
        noun = "leaf" if len(lost_placeholders) == 1 else "leaves"
        print(f"PLACEHOLDERS — {len(lost_placeholders)} {noun} changed")
        for key, ps, pt in lost_placeholders:
            print(f"  ✗ {key}\n      source: {ps}\n      target: {pt}")
        print()

    if whitespace:
        failed = True
        noun = "leaf differs" if len(whitespace) == 1 else "leaves differ"
        print(f"WHITESPACE — {len(whitespace)} {noun} at the edges")
        for key, s, t in whitespace:
            print(f"  ✗ {key}\n      source: {s}\n      target: {t}")
        print()

    if overflow:
        failed = True
        noun = "leaf" if len(overflow) == 1 else "leaves"
        print(f"LENGTH — {len(overflow)} {noun} over budget")
        for key, got, budget, s, t in overflow:
            print(f"  ✗ {key}  ({got} > {budget})\n      source: {s!r}\n      target: {t!r}")
        print()

    if failed:
        print("FAIL — fix the leaves above, or document each overflow in the report.")
        return 1

    print("OK — structure, placeholders, whitespace and length all within contract.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
