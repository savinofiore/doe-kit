#!/usr/bin/env python3
"""
Turns scored runs into a report you are allowed to publish.

    bench/analyze.py bench/results/ --report bench/results/REPORT.md

What it produces:

  * per-arm means with 95% CIs from a cluster bootstrap that resamples TASKS, not runs
    (20 tasks x 5 seeds is 20 independent units, not 100 — getting this wrong shrinks every
    interval by ~sqrt(5) and turns noise into a finding);
  * the paired A2 - A3 delta per task, with a bootstrap CI and a Wilcoxon signed-rank test —
    the token-matched comparison, which is the only one that can falsify H2;
  * a within-task demeaned regression of quality on log(tokens), which is the dose-response
    slope with task difficulty differenced out;
  * a cost-quality frontier as an SVG.

Standard library only, so it runs anywhere the kit runs.
"""

import argparse
import json
import math
import random
import statistics
from pathlib import Path

BOOTSTRAP = 10000
PRIMARY = "resolved"


# ---------------------------------------------------------------- loading

def load(results: Path):
    rows = []
    for f in sorted(results.rglob("metrics.json")):
        m = json.loads(f.read_text())
        mut = m.get("mutation") or {}
        pre = m.get("pre_existing_tests") or {}
        reg = m.get("regression") or {}
        rows.append({
            "arm": m["arm"],
            "task": m["task"],
            "seed": m["seed"],
            "tier": m.get("tier"),
            "resolved": 1.0 if m["hidden"]["resolved"] else 0.0,
            "mutation": mut.get("score") if mut.get("scored") else None,
            "regression_green": (1.0 if reg.get("green") else 0.0) if reg else None,
            "touched_old_tests": (1.0 if pre.get("count", 0) else 0.0) if pre else None,
            "tokens": m.get("tokens"),
            "usd": m.get("usd"),
            "approvals": m.get("approvals", 0),
            "truncated": bool(m.get("truncated")),
        })
    return rows


def by_task(rows, arm, metric):
    """Collapse seeds within a task first — the task is the unit of analysis."""
    buckets = {}
    for r in rows:
        if r["arm"] != arm or r[metric] is None:
            continue
        buckets.setdefault(r["task"], []).append(r[metric])
    return {t: statistics.fmean(v) for t, v in buckets.items()}


# ---------------------------------------------------------------- statistics

def bootstrap_ci(values, rng, reps=BOOTSTRAP, alpha=0.05):
    """Percentile bootstrap over the given units (one value per task)."""
    if len(values) < 2:
        return (float("nan"), float("nan"))
    n = len(values)
    means = []
    for _ in range(reps):
        means.append(statistics.fmean(values[rng.randrange(n)] for _ in range(n)))
    means.sort()
    lo = means[int(alpha / 2 * reps)]
    hi = means[min(reps - 1, int((1 - alpha / 2) * reps))]
    return (lo, hi)


def wilcoxon_signed_rank(deltas):
    """Distribution-free backstop for the paired comparison.

    Normal approximation with tie correction. Below ~10 non-zero pairs the approximation is
    unreliable — the caller prints the n so a reader can discount it.
    """
    d = [x for x in deltas if x != 0]
    n = len(d)
    if n < 6:
        return {"n": n, "p": None, "note": "too few non-zero pairs for a normal approximation"}
    order = sorted(range(n), key=lambda i: abs(d[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(d[order[j + 1]]) == abs(d[order[i]]):
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    w_plus = sum(r for r, x in zip(ranks, d) if x > 0)
    mu = n * (n + 1) / 4
    sigma = math.sqrt(n * (n + 1) * (2 * n + 1) / 24)
    z = (w_plus - mu) / sigma if sigma else 0.0
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return {"n": n, "z": round(z, 3), "p": round(p, 5)}


def demeaned_slope(rows, arm, metric="resolved"):
    """Quality on log(tokens), with a task fixed effect removed by demeaning.

    This is the whole defence against Simpson's paradox: hard tasks cost more AND score worse,
    so the pooled slope can come out negative while every within-task slope is positive.
    """
    pts = [r for r in rows
           if r["arm"] == arm and r.get("tokens") and r[metric] is not None]
    groups = {}
    for r in pts:
        groups.setdefault(r["task"], []).append((math.log(r["tokens"]), r[metric]))
    xs, ys, tasks = [], [], []
    for task, vals in groups.items():
        if len(vals) < 2:
            continue  # a single run per task carries no within-task variation
        mx = statistics.fmean(v[0] for v in vals)
        my = statistics.fmean(v[1] for v in vals)
        for x, y in vals:
            xs.append(x - mx)
            ys.append(y - my)
            tasks.append(task)
    if len(xs) < 3:
        return None
    sxx = sum(x * x for x in xs)
    if sxx == 0:
        return None
    beta = sum(x * y for x, y in zip(xs, ys)) / sxx

    rng = random.Random(7)
    uniq = sorted(set(tasks))
    draws = []
    for _ in range(1000):
        picked = [uniq[rng.randrange(len(uniq))] for _ in range(len(uniq))]
        bx, by = [], []
        for t in picked:
            for x, y, tt in zip(xs, ys, tasks):
                if tt == t:
                    bx.append(x)
                    by.append(y)
        s = sum(x * x for x in bx)
        if s:
            draws.append(sum(x * y for x, y in zip(bx, by)) / s)
    draws.sort()
    lo = draws[int(0.025 * len(draws))] if draws else float("nan")
    hi = draws[int(0.975 * len(draws))] if draws else float("nan")
    # Per doubling of the budget: log(2) * beta.
    return {"slope_per_ln_token": beta, "per_doubling": beta * math.log(2),
            "ci_per_doubling": (lo * math.log(2), hi * math.log(2)), "n_obs": len(xs)}


# ---------------------------------------------------------------- output

def fmt(x, digits=3):
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{digits}f}"


def frontier_svg(rows, arms, path: Path):
    """Tokens (x, log scale) against resolve rate (y), one point per arm."""
    pts = []
    for arm in arms:
        tk = [r["tokens"] for r in rows if r["arm"] == arm and r.get("tokens")]
        q = [r["resolved"] for r in rows if r["arm"] == arm]
        if tk and q:
            pts.append((arm, statistics.median(tk), statistics.fmean(q)))
    if not pts:
        return False
    W, H, PAD = 720, 420, 64
    xs = [math.log10(p[1]) for p in pts]
    x0, x1 = min(xs) - 0.15, max(xs) + 0.15
    def px(x): return PAD + (math.log10(x) - x0) / (x1 - x0) * (W - 2 * PAD)
    def py(y): return H - PAD - y * (H - 2 * PAD)
    colours = ["#59636e", "#9a6700", "#1a7f37", "#4c6ef5", "#cf222e", "#8250df"]
    body = [f'<rect width="{W}" height="{H}" fill="#ffffff"/>']
    for g in range(0, 6):
        y = g / 5
        body.append(f'<line x1="{PAD}" y1="{py(y):.1f}" x2="{W - PAD}" y2="{py(y):.1f}" '
                    f'stroke="#e6e8eb" stroke-width="1"/>')
        body.append(f'<text x="{PAD - 10}" y="{py(y) + 4:.1f}" text-anchor="end" '
                    f'font-size="11" fill="#59636e">{y:.1f}</text>')
    for i, (arm, tok, qual) in enumerate(sorted(pts, key=lambda p: p[1])):
        c = colours[i % len(colours)]
        body.append(f'<circle cx="{px(tok):.1f}" cy="{py(qual):.1f}" r="6" fill="{c}"/>')
        body.append(f'<text x="{px(tok):.1f}" y="{py(qual) - 14:.1f}" text-anchor="middle" '
                    f'font-size="12" fill="{c}">{arm}</text>')
        body.append(f'<text x="{px(tok):.1f}" y="{H - PAD + 18:.1f}" text-anchor="middle" '
                    f'font-size="10" fill="#59636e">{tok / 1000:.0f}k</text>')
    body.append(f'<line x1="{PAD}" y1="{H - PAD}" x2="{W - PAD}" y2="{H - PAD}" stroke="#1f2328"/>')
    body.append(f'<line x1="{PAD}" y1="{PAD}" x2="{PAD}" y2="{H - PAD}" stroke="#1f2328"/>')
    body.append(f'<text x="{W / 2}" y="{H - 14}" text-anchor="middle" font-size="12" '
                f'fill="#1f2328">median tokens per task (log scale)</text>')
    body.append(f'<text x="18" y="{H / 2}" text-anchor="middle" font-size="12" fill="#1f2328" '
                f'transform="rotate(-90 18 {H / 2})">resolve rate (hidden suite)</text>')
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="ui-monospace, Menlo, monospace">'
        + "".join(body) + "</svg>")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("results")
    ap.add_argument("--report", default=None)
    ap.add_argument("--treatment", default="A2_doe", help="the arm under test")
    ap.add_argument("--control", default="A3_baseline_matched",
                    help="the token-matched control — the H2 comparison")
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()

    rows = load(Path(args.results))
    if not rows:
        print("analyze: no scored runs found — run score.py first")
        return 1
    rng = random.Random(args.seed)
    arms = sorted({r["arm"] for r in rows})
    tasks = sorted({r["task"] for r in rows})

    out = ["# Benchmark report", "",
           f"`{len(rows)}` runs · `{len(tasks)}` tasks · `{len(arms)}` arms · "
           f"bootstrap {BOOTSTRAP} resamples, clustered on task", "",
           "Primary endpoint: **resolve rate on the hidden acceptance suite**. "
           "Everything else is secondary and exploratory.", "",
           "## Per-arm", "",
           "| arm | resolve@1 | mutation score | regressions green | touched old tests | "
           "median tokens | approvals | truncated |", "|---|---|---|---|---|---|---|---|"]

    for arm in arms:
        cells = []
        for metric in ("resolved", "mutation", "regression_green", "touched_old_tests"):
            per_task = by_task(rows, arm, metric)
            vals = list(per_task.values())
            if not vals:
                cells.append("—")
                continue
            lo, hi = bootstrap_ci(vals, rng)
            cells.append(f"{fmt(statistics.fmean(vals))} [{fmt(lo)}, {fmt(hi)}]")
        toks = [r["tokens"] for r in rows if r["arm"] == arm and r.get("tokens")]
        appr = [r["approvals"] for r in rows if r["arm"] == arm]
        trunc = [r["truncated"] for r in rows if r["arm"] == arm]
        out.append(f"| `{arm}` | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | "
                   f"{int(statistics.median(toks)) if toks else '—'} | "
                   f"{fmt(statistics.fmean(appr) if appr else None, 2)} | "
                   f"{sum(trunc)}/{len(trunc)} |")

    # ---- H2: the token-matched paired comparison
    out += ["", f"## H2 — `{args.treatment}` vs `{args.control}` at matched budget", ""]
    a = by_task(rows, args.treatment, PRIMARY)
    b = by_task(rows, args.control, PRIMARY)
    shared = sorted(set(a) & set(b))
    if len(shared) < 2:
        out.append(f"Not enough paired tasks (`{len(shared)}`). "
                   "This is the comparison the whole design exists for — run both arms.")
    else:
        deltas = [a[t] - b[t] for t in shared]
        lo, hi = bootstrap_ci(deltas, rng)
        w = wilcoxon_signed_rank(deltas)
        mean_d = statistics.fmean(deltas)
        verdict = ("**H2 survives** — the CI excludes 0 in the positive direction."
                   if lo > 0 else
                   "**H2 does not survive on this data** — the CI contains 0 (or is negative). "
                   "At a matched budget the structure did not beat the spend. Report that.")
        out += [f"| tasks | mean delta | 95% CI | Wilcoxon |", "|---|---|---|---|",
                f"| {len(shared)} | {fmt(mean_d)} | [{fmt(lo)}, {fmt(hi)}] | "
                f"n={w['n']}, p={w.get('p')} |", "", verdict, "",
                "Per-task deltas (a single task carrying the whole effect is a finding, "
                "not a result):", "",
                "| task | " + args.treatment + " | " + args.control + " | delta |",
                "|---|---|---|---|"]
        for t in shared:
            out.append(f"| `{t}` | {fmt(a[t], 2)} | {fmt(b[t], 2)} | {fmt(a[t] - b[t], 2)} |")

    # ---- H1/H3: dose-response
    out += ["", "## H1 / H3 — dose–response within each process", "",
            "Slope of resolve rate on `log(tokens)`, task fixed effect demeaned out. "
            "Reported per doubling of the token budget.", "",
            "| arm | delta resolve per doubling | 95% CI | n obs |", "|---|---|---|---|"]
    for arm in arms:
        s = demeaned_slope(rows, arm)
        if not s:
            out.append(f"| `{arm}` | — | — | — |")
            continue
        lo, hi = s["ci_per_doubling"]
        out.append(f"| `{arm}` | {fmt(s['per_doubling'])} | [{fmt(lo)}, {fmt(hi)}] | "
                   f"{s['n_obs']} |")

    report_path = Path(args.report) if args.report else Path(args.results) / "REPORT.md"
    svg = report_path.parent / "frontier.svg"
    if frontier_svg(rows, arms, svg):
        out += ["", "## Cost–quality frontier", "", f"![frontier]({svg.name})", "",
                "The point where this curve flattens is the budget past which you are paying "
                "for nothing (H3)."]

    out += ["", "## Required caveats", "",
            "- Effects are per-task means; the unit of analysis is the task, not the run.",
            "- Truncated runs are included and counted in the truncation column. A high "
            "truncation rate in the matched-control arm makes the H2 comparison unfair to "
            "the control, and the result is not yet earned.",
            "- Mutation score is computed only over runs whose own suite was green; the "
            "arms' n for that column differ, and an arm that wrote no tests contributes "
            "nothing rather than a zero.",
            "- Secondary metrics need a Holm–Bonferroni correction before anyone calls them "
            "significant.", ""]

    report_path.write_text("\n".join(out))
    print("\n".join(out))
    print(f"\nwritten: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
