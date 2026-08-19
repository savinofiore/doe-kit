#!/usr/bin/env python3
"""
Mutation scorer — the anti-gaming metric for "did the agent write real tests?"

Coverage says a line ran. It does not say anyone looked at the result. A test that calls the
function and asserts nothing gives 100% coverage and 0% mutation score, and an agent optimising
against a coverage gate finds that out in one turn.

This perturbs the *implementation* one operator at a time and re-runs the *agent's own* test
command. A mutant that makes no test fail is a behaviour change nobody was watching.

    bench/mutation.py --root WORKDIR --src src --test-cmd "python3 -m unittest discover -s tests"
    bench/mutation.py ... --max-mutants 60 --json out.json

Exit 0 with a report on stdout. Exit 2 if the suite is not green before mutation — a red
baseline makes every mutant look killed, which is the most flattering possible bug.

Python 3.9+, standard library only.
"""

import argparse
import ast
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

CMP_SWAP = {
    ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Is: ast.IsNot, ast.IsNot: ast.Is,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
}
BIN_SWAP = {
    ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv, ast.Div: ast.Mult,
    ast.FloorDiv: ast.Mult, ast.Mod: ast.Mult, ast.Pow: ast.Mult,
}
BOOL_SWAP = {ast.And: ast.Or, ast.Or: ast.And}


class Mutator(ast.NodeTransformer):
    """Applies exactly one mutation — the `target`-th candidate in traversal order.

    Called with target=None it mutates nothing and `count` reports how many candidates exist,
    so enumeration and application share one traversal and can never disagree.
    """

    def __init__(self, target=None):
        self.target = target
        self.count = 0
        self.applied = None

    def _take(self, label, lineno):
        i = self.count
        self.count += 1
        if self.target == i:
            self.applied = f"L{lineno}: {label}"
            return True
        return False

    def visit_BinOp(self, node):
        self.generic_visit(node)
        op = type(node.op)
        if op in BIN_SWAP:
            new = BIN_SWAP[op]
            if self._take(f"{op.__name__} -> {new.__name__}", node.lineno):
                node.op = new()
        return node

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        op = type(node.op)
        if op in BIN_SWAP:
            new = BIN_SWAP[op]
            if self._take(f"aug {op.__name__} -> {new.__name__}", node.lineno):
                node.op = new()
        return node

    def visit_Compare(self, node):
        self.generic_visit(node)
        for idx, op in enumerate(node.ops):
            t = type(op)
            if t in CMP_SWAP:
                new = CMP_SWAP[t]
                if self._take(f"{t.__name__} -> {new.__name__}", node.lineno):
                    node.ops[idx] = new()
        return node

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        op = type(node.op)
        if op in BOOL_SWAP:
            new = BOOL_SWAP[op]
            if self._take(f"{op.__name__} -> {new.__name__}", node.lineno):
                node.op = new()
        return node

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Not) and self._take("drop `not`", node.lineno):
            return node.operand
        return node

    def visit_Constant(self, node):
        # Strings are skipped: mutating a docstring or a message produces a mutant no
        # reasonable test should catch, and inflates the survivor list with noise.
        if isinstance(node.value, bool):
            if self._take(f"{node.value} -> {not node.value}", node.lineno):
                return ast.copy_location(ast.Constant(value=not node.value), node)
        elif isinstance(node.value, (int, float)):
            if self._take(f"{node.value!r} -> {node.value + 1!r}", node.lineno):
                return ast.copy_location(ast.Constant(value=node.value + 1), node)
        return node


def source_files(root: Path, src: str):
    p = root / src
    if p.is_file():
        return [p]
    return sorted(f for f in p.rglob("*.py")
                  if "test" not in f.name and "__pycache__" not in str(f))


def run(cmd, cwd, timeout):
    # Bytecode caching is validated on (mtime_seconds, size). Mutants are written to the same
    # path within the same second and often unparse to the same length, so a stale .pyc gets
    # imported and the mutant "survives" without ever having run. That failure mode is silent
    # and inflates nothing but the survivor list, which is exactly the wrong direction.
    for cache in Path(cwd).rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, timeout=timeout, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode
    except subprocess.TimeoutExpired:
        # A mutant that hangs is a mutant the suite noticed by wedging on it. Killed.
        return 124


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--root", required=True, help="working directory the tests run in")
    ap.add_argument("--src", default="src", help="file or directory to mutate")
    ap.add_argument("--test-cmd", required=True, help="the agent's own test command")
    ap.add_argument("--max-mutants", type=int, default=60)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--seed", type=int, default=0, help="fixes which mutants get sampled")
    ap.add_argument("--json", help="write the report here as well as stdout")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    files = source_files(root, args.src)
    if not files:
        print(f"mutation: no source files under {root / args.src}", file=sys.stderr)
        return 2

    baseline = run(args.test_cmd, root, args.timeout)
    if baseline != 0:
        print(f"mutation: baseline suite is RED (exit {baseline}) — refusing to score",
              file=sys.stderr)
        return 2

    candidates = []
    for f in files:
        try:
            tree = ast.parse(f.read_text())
        except SyntaxError:
            continue
        m = Mutator(None)
        m.visit(tree)
        candidates += [(f, i) for i in range(m.count)]

    if not candidates:
        print("mutation: no viable mutation points", file=sys.stderr)
        return 2

    if len(candidates) > args.max_mutants:
        random.Random(args.seed).shuffle(candidates)
        candidates = sorted(candidates[:args.max_mutants], key=lambda c: (str(c[0]), c[1]))

    killed, survived = 0, []
    started = time.time()
    for path, idx in candidates:
        original = path.read_text()
        tree = ast.parse(original)
        m = Mutator(idx)
        mutated = ast.fix_missing_locations(m.visit(tree))
        try:
            path.write_text(ast.unparse(mutated))
            rc = run(args.test_cmd, root, args.timeout)
        finally:
            path.write_text(original)
        if rc != 0:
            killed += 1
        else:
            survived.append(f"{path.relative_to(root)} {m.applied}")

    total = len(candidates)
    report = {
        "total": total,
        "killed": killed,
        "survived": survived,
        "score": round(killed / total, 4),
        "seconds": round(time.time() - started, 1),
        "files": [str(f.relative_to(root)) for f in files],
    }
    print(json.dumps(report, indent=2))
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
