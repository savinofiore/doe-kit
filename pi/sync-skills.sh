#!/usr/bin/env bash
#
# Regenerate pi/skills/ from skills/.
#
# The Pi package ships the same skills under namespaced names, so `/skill:doe-execute` can
# never collide with another package's `/skill:execute`. Those copies are mechanical, which
# is exactly why they rot: editing skills/<name>/SKILL.md leaves the pi copy behind, and a
# stale copy is not a broken build — it is a skill that quietly teaches the old process.
#
#   pi/sync-skills.sh            regenerate
#   pi/sync-skills.sh --check    fail if anything is out of date (what CI runs)
#
# The transform, and the whole of it:
#   skills/<name>/               → pi/skills/doe-<name>/
#   SKILL.md `name: <name>`      → `name: doe-<name>`, plus the Pi invocation note
#   every other file             → copied verbatim
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CHECK=0
[[ "${1:-}" == "--check" ]] && CHECK=1

python3 - <<'PY'
import shutil
from pathlib import Path

src_root = Path("skills")
dst_root = Path("pi/skills")

NOTE = "> **Pi:** invoke this skill with `/skill:{name}`.\n\n\n"


def namespaced(text: str, name: str) -> str:
    """Rename the skill and announce its Pi invocation, touching nothing else."""
    lines = text.splitlines(keepends=True)
    # The frontmatter is the first `---`-delimited block; `name:` inside it is the only
    # line renamed. The description mentions the old name in prose and must stay as written.
    close = next(i for i, line in enumerate(lines[1:], 1) if line.rstrip() == "---")
    for i in range(1, close):
        if lines[i].startswith("name: "):
            lines[i] = f"name: {name}\n"
            break
    else:
        raise SystemExit(f"no `name:` in the frontmatter of {name}")
    head, body = lines[: close + 1], lines[close + 1 :]
    # One blank line after the frontmatter, then the note, then the body as it was.
    while body and not body[0].strip():
        body = body[1:]
    return "".join(head) + "\n" + NOTE.format(name=name) + "".join(body)


wanted = set()
for src in sorted(p for p in src_root.iterdir() if p.is_dir()):
    name = f"doe-{src.name}"
    dst = dst_root / name
    wanted.add(dst)
    for item in sorted(src.rglob("*")):
        if item.is_dir():
            continue
        target = dst / item.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        if item.name == "SKILL.md":
            target.write_text(namespaced(item.read_text(encoding="utf-8"), name), encoding="utf-8")
        else:
            shutil.copy2(item, target)

# A skill deleted from skills/ must not survive under pi/.
for stale in sorted(p for p in dst_root.iterdir() if p.is_dir() and p not in wanted):
    shutil.rmtree(stale)
    print(f"removed stale {stale}")
PY

if [[ $CHECK -eq 1 ]]; then
  if ! git diff --quiet -- pi/skills || [[ -n "$(git ls-files --others --exclude-standard pi/skills)" ]]; then
    echo "pi/skills/ is out of date with skills/ — run pi/sync-skills.sh and commit the result" >&2
    git --no-pager diff --stat -- pi/skills >&2
    git ls-files --others --exclude-standard pi/skills >&2
    exit 1
  fi
  echo "pi/skills/ is in sync with skills/"
fi
