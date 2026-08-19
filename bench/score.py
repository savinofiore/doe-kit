#!/usr/bin/env python3
"""
Scores finished benchmark runs. One run in, one metrics.json out.

    bench/score.py bench/results/            # score every unscored run
    bench/score.py bench/results/ --force    # rescore everything

A run directory is whatever `run.py` produced:

    results/<arm>/<task>/<seed>/
    ├── meta.json     arm, task, seed, model id, tokens, USD, seconds, approvals
    ├── workdir/      the repository as the agent left it
    └── agent.log

Nothing here reads the agent's own claims about what it did. Every number comes from running
something. Standard library only.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent


def sh(cmd, cwd, timeout=600):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, timeout=timeout, env=env,
                           capture_output=True, text=True)
        return r.returncode, (r.stdout + r.stderr)[-4000:]
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hidden_suite(task_dir: Path, workdir: Path):
    """The primary endpoint. The agent has never seen these tests."""
    rc, out = sh(f"{task_dir / 'verify.sh'} {workdir}", cwd=task_dir)
    return {"resolved": rc == 0, "exit_code": rc, "tail": out[-1500:]}


def regression(task_dir: Path, workdir: Path, cfg: dict):
    """The fixture's original suite, restored from the task and run against the new source.

    Restored rather than read from the workdir on purpose: an agent that edited the old tests
    into agreement with its new behaviour must not be able to pass this.
    """
    if not cfg:
        return None
    overlay = workdir / "_bench_regression"
    shutil.rmtree(overlay, ignore_errors=True)
    shutil.copytree(task_dir / "fixture" / cfg["fixture_dir"], overlay)
    try:
        rc, out = sh(cfg["cmd"], cwd=workdir)
    finally:
        shutil.rmtree(overlay, ignore_errors=True)
    return {"green": rc == 0, "exit_code": rc, "tail": out[-1500:]}


def touched_pre_existing_tests(task_dir: Path, workdir: Path, cfg: dict):
    """Did the agent edit tests that already existed? The red-test rule, measured."""
    if not cfg:
        return None
    src = task_dir / "fixture" / cfg["fixture_dir"]
    modified, deleted = [], []
    for original in sorted(src.rglob("*.py")):
        rel = original.relative_to(task_dir / "fixture")
        current = workdir / rel
        if not current.exists():
            deleted.append(str(rel))
        elif digest(current) != digest(original):
            modified.append(str(rel))
    return {"modified": modified, "deleted": deleted,
            "count": len(modified) + len(deleted)}


def mutation(task_dir: Path, workdir: Path, cfg: dict, seed: int):
    """Test quality: mutants of the source killed by the agent's OWN tests."""
    if not cfg:
        return None
    cmd = (f"{BENCH / 'mutation.py'} --root {workdir} --src {cfg['src']} "
           f"--test-cmd {json.dumps(cfg['test_cmd'])} "
           f"--max-mutants {cfg.get('max_mutants', 60)} --seed {seed}")
    rc, out = sh(cmd, cwd=workdir, timeout=3600)
    if rc != 0:
        # A red or missing suite is not a zero score, it is *no* score. Averaging a missing
        # value as 0 would let an arm that writes no tests look merely bad instead of absent.
        return {"scored": False, "reason": out.strip()[-500:]}
    try:
        report = json.loads(out[out.index("{"):out.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return {"scored": False, "reason": "unparseable mutation report"}
    report["scored"] = True
    return report


def wrote_tests(task_dir: Path, workdir: Path, cfg: dict):
    """New test files that were not in the fixture."""
    if not cfg:
        return None
    fixture_tests = {p.name for p in (task_dir / "fixture" / cfg["fixture_dir"]).rglob("*.py")}
    current = (workdir / cfg["fixture_dir"])
    if not current.exists():
        return {"new_files": [], "count": 0}
    new = [str(p.relative_to(workdir)) for p in sorted(current.rglob("*.py"))
           if p.name not in fixture_tests]
    return {"new_files": new, "count": len(new)}


def score_run(run_dir: Path, tasks_root: Path):
    meta = json.loads((run_dir / "meta.json").read_text())
    task_dir = tasks_root / meta["task"]
    task = json.loads((task_dir / "task.json").read_text())
    workdir = run_dir / "workdir"

    reg_cfg = task.get("regression")
    metrics = {
        "arm": meta["arm"],
        "task": meta["task"],
        "seed": meta["seed"],
        "tier": task.get("tier"),
        "model": meta.get("model"),
        "tokens": meta.get("tokens"),
        "usd": meta.get("usd"),
        "seconds": meta.get("seconds"),
        "approvals": meta.get("approvals", 0),
        "truncated": meta.get("truncated", False),
        "hidden": hidden_suite(task_dir, workdir),
        "regression": regression(task_dir, workdir, reg_cfg),
        "pre_existing_tests": touched_pre_existing_tests(task_dir, workdir, reg_cfg),
        "new_tests": wrote_tests(task_dir, workdir, reg_cfg),
        "mutation": mutation(task_dir, workdir, task.get("mutation"), meta.get("seed", 0)),
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("results", help="results root written by run.py")
    ap.add_argument("--tasks", default=str(BENCH / "tasks"))
    ap.add_argument("--force", action="store_true", help="rescore runs that already have metrics")
    args = ap.parse_args()

    runs = sorted(p.parent for p in Path(args.results).rglob("meta.json"))
    if not runs:
        print(f"score: no runs under {args.results}", file=sys.stderr)
        return 1

    done = 0
    for run_dir in runs:
        if (run_dir / "metrics.json").exists() and not args.force:
            continue
        m = score_run(run_dir, Path(args.tasks))
        mut = m["mutation"]
        mut_s = f"{mut['score']:.2f}" if mut and mut.get("scored") else "—"
        print(f"{m['arm']:<20} {m['task']:<28} seed={m['seed']} "
              f"resolved={str(m['hidden']['resolved']):<5} mutation={mut_s} "
              f"touched_old_tests={(m['pre_existing_tests'] or {}).get('count', '—')}")
        done += 1
    print(f"\nscored {done} run(s), {len(runs)} total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
