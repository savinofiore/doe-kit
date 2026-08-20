#!/usr/bin/env python3
"""
Runs the benchmark: every (arm x task x seed) cell, each in a fresh working copy.

    bench/run.py --arms A0_baseline,A2_doe --tasks all --seeds 5 --out bench/results/
    bench/run.py --dry-run          # validate arms, tasks and placeholders, invoke nothing

This orchestrates; it does not judge. Nothing here inspects the produced code — scoring is
score.py's job, and it runs afterwards so that a scoring bug can be fixed and everything
rescored without paying for the runs twice.

The agent command is configurable because the harness must not privilege one CLI. It is a
template with {prompt_file}, {workdir}, {seed} and {token_budget} placeholders, e.g.

    --agent-cmd 'claude -p "$(cat {prompt_file})" --output-format json --permission-mode acceptEdits'

Standard library only.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parent
KIT = BENCH.parent


def sh(cmd, cwd=None, timeout=3600, capture=True):
    r = subprocess.run(cmd, shell=True, cwd=cwd, timeout=timeout,
                       capture_output=capture, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def find_usage(blob):
    """Pull token and cost figures out of an agent's JSON output, tolerantly.

    Every CLI names these differently and renames them between versions. Rather than pin one
    schema, walk the structure for the keys we know about, and return None when nothing is
    found — a missing token count must read as missing, never as zero, or the cost axis of the
    whole benchmark silently collapses toward the origin.
    """
    tokens, usd = 0, None
    keys = ("input_tokens", "output_tokens", "cache_creation_input_tokens",
            "cache_read_input_tokens", "thinking_tokens")

    def walk(node):
        nonlocal tokens, usd
        if isinstance(node, dict):
            for k, v in node.items():
                if k in keys and isinstance(v, (int, float)):
                    tokens += int(v)
                elif k in ("total_cost_usd", "cost_usd") and isinstance(v, (int, float)):
                    usd = float(v)
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(blob)
    return (tokens or None), usd


def parse_agent_output(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Some CLIs stream JSON lines; take the last complete object.
        for line in reversed(text.strip().splitlines()):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def prepare_workdir(task_dir: Path, workdir: Path):
    shutil.rmtree(workdir, ignore_errors=True)
    shutil.copytree(task_dir / "fixture", workdir)
    sh("git init -q . && git add -A && git -c user.email=bench@local "
       "-c user.name=bench commit -qm fixture", cwd=workdir)


def build_prompt(task_dir: Path, arm: dict, workdir: Path, budget, task_cfg):
    """Task text + the arm's protocol suffix.

    Every arm is told how to run the tests. If the baseline cannot run the suite at all, the
    experiment measures tool access rather than protocol, and the result is worthless.
    """
    body = (task_dir / "prompt.md").read_text()
    suffix = ""
    if arm.get("prompt_suffix"):
        suffix = (BENCH / arm["prompt_suffix"]).read_text()
    prompt = body if not suffix else f"{body}\n\n---\n\n{suffix}"
    prompt = (prompt
              .replace("{token_budget}", str(budget) if budget else "unbounded")
              .replace("{agent_tests}", task_cfg.get("commands", {}).get("agent_tests", ""))
              .replace("{protected_roots}", ", ".join(task_cfg.get("protected_roots", []))))
    path = workdir.parent / "prompt.txt"
    path.write_text(prompt)
    return path


def matched_budget(out: Path, arm: dict, task: str, seed: int):
    """A3's cap is A2's actual spend on the SAME task and seed — never the average."""
    ref = arm.get("match_budget_from")
    if not ref:
        return None
    meta = out / ref / task / str(seed) / "meta.json"
    if not meta.exists():
        return None
    return json.loads(meta.read_text()).get("tokens")


def run_cell(arm, task_dir: Path, seed: int, out: Path, agent_cmd: str, dry: bool):
    task = task_dir.name
    cell = out / arm["id"] / task / str(seed)
    workdir = cell / "workdir"
    cell.mkdir(parents=True, exist_ok=True)

    budget = matched_budget(out, arm, task, seed)
    if arm.get("match_budget_from") and budget is None and not dry:
        print(f"  skip {arm['id']}/{task}/{seed}: no reference run to match against "
              f"— run {arm['match_budget_from']} first")
        return None

    task_cfg = json.loads((task_dir / "task.json").read_text())
    if not dry:
        prepare_workdir(task_dir, workdir)
    prompt_file = build_prompt(task_dir, arm, workdir, budget, task_cfg) if not dry else None
    notes = []
    for step in arm.get("setup", []):
        cmd = step.format(kit=KIT, workdir=workdir, stack=task_cfg.get("stack", ""))
        if "install.sh" in cmd and task_cfg.get("stack") not in ("flutter", "web-ts"):
            # The reference task is stdlib Python, which has no installer. Say so in the run
            # record rather than pretending the kit was installed.
            notes.append(f"setup skipped, no installer for stack "
                         f"{task_cfg.get('stack')!r}: {cmd}")
            continue
        if dry:
            notes.append(f"would run: {cmd}")
        else:
            rc, log = sh(cmd, cwd=workdir)
            notes.append(f"setup rc={rc}: {cmd}")

    cmd = agent_cmd.format(prompt_file=prompt_file, workdir=workdir, seed=seed,
                           token_budget=budget or "")
    if dry:
        print(f"  [dry] {arm['id']}/{task}/{seed}: {cmd}")
        for n in notes:
            print(f"        {n}")
        return None

    started = time.time()
    rc, output = sh(cmd, cwd=workdir, timeout=arm.get("timeout", 3600))
    elapsed = round(time.time() - started, 1)
    (cell / "agent.log").write_text(output)

    parsed = parse_agent_output(output)
    tokens, usd = find_usage(parsed) if parsed else (None, None)
    truncated = bool(budget and tokens and tokens > budget * 1.1)

    meta = {
        "arm": arm["id"],
        "task": task,
        "seed": seed,
        "model": os.environ.get("BENCH_MODEL_ID", "unrecorded"),
        "agent_cmd": cmd,
        "exit_code": rc,
        "tokens": tokens,
        "usd": usd,
        "seconds": elapsed,
        "approvals": arm.get("approvals", 0),
        "token_budget": budget,
        "truncated": truncated,
        "under_budget": bool(budget and tokens and tokens < budget * 0.9),
        "notes": notes,
        "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (cell / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"  {arm['id']}/{task}/{seed}: rc={rc} tokens={tokens} {elapsed}s"
          + ("  TRUNCATED" if truncated else ""))
    return meta


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--arms", default="A0_baseline,A1_baseline_rich,A2_doe,A3_baseline_matched")
    ap.add_argument("--tasks", default="all")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--out", default=str(BENCH / "results"))
    ap.add_argument("--agent-cmd", default=os.environ.get("BENCH_AGENT_CMD", ""))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.agent_cmd and not args.dry_run:
        print("run: --agent-cmd (or $BENCH_AGENT_CMD) is required. See bench/README.md.",
              file=sys.stderr)
        return 2

    arms = []
    for name in args.arms.split(","):
        path = BENCH / "arms" / f"{name.strip()}.json"
        if not path.exists():
            print(f"run: no such arm: {path}", file=sys.stderr)
            return 2
        arms.append(json.loads(path.read_text()))

    tasks = sorted(p for p in (BENCH / "tasks").iterdir() if (p / "task.json").exists())
    if args.tasks != "all":
        wanted = {t.strip() for t in args.tasks.split(",")}
        tasks = [t for t in tasks if t.name in wanted]
    if not tasks:
        print("run: no tasks selected", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    # Arms run in the order given so that a budget-matched arm always finds its reference.
    for arm in arms:
        print(f"\n== {arm['id']} — {arm.get('description', '')}")
        for task_dir in tasks:
            for seed in range(args.seeds):
                run_cell(arm, task_dir, seed, out, args.agent_cmd, args.dry_run)
    print("\nnext: bench/score.py", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
