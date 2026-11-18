"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def _metric_by_id(spec: dict) -> dict[str, dict]:
    return {m["id"]: m for m in spec.get("metrics") or []}


def _slice_by_name(spec: dict) -> dict[str, dict]:
    return {s["name"]: s for s in spec.get("slices") or []}


def _item_slices(report: dict) -> dict[str, frozenset[str]]:
    out: dict[str, frozenset[str]] = {}
    for row in report.get("rows") or []:
        item_id = row["item_id"]
        tags = frozenset(row.get("slices") or [])
        if item_id in out and out[item_id] != tags:
            # Keep first; integrity will also flag if we compare to baseline.
            continue
        out[item_id] = tags
    return out


def _ratchet_problems(spec: dict, base_spec: dict) -> list[str]:
    problems: list[str] = []
    if spec.get("eval_set_version") != base_spec.get("eval_set_version"):
        return problems
    base_metrics = _metric_by_id(base_spec)
    for mid, bm in base_metrics.items():
        sm = _metric_by_id(spec).get(mid)
        if sm is None:
            problems.append(f"metric {mid} removed")
            continue
        if bm.get("blocking") and not sm.get("blocking"):
            problems.append(f"metric {mid} no longer blocking")
        bt, st = bm.get("threshold") or {}, sm.get("threshold") or {}
        if "min" in bt and ("min" not in st or float(st["min"]) < float(bt["min"])):
            problems.append(f"metric {mid} min loosened")
        if "max" in bt and ("max" not in st or float(st["max"]) > float(bt["max"])):
            problems.append(f"metric {mid} max loosened")
        if bt.get("no_significant_drop") and not st.get("no_significant_drop"):
            problems.append(f"metric {mid} dropped no_significant_drop")
    base_slices = _slice_by_name(base_spec)
    for name, bs in base_slices.items():
        ss = _slice_by_name(spec).get(name)
        if ss is None:
            problems.append(f"slice {name} removed")
            continue
        if bs.get("blocking") and not ss.get("blocking"):
            problems.append(f"slice {name} no longer blocking")
        if "min" in bs and ("min" not in ss or float(ss["min"]) < float(bs["min"])):
            problems.append(f"slice {name} min loosened")
        if bs.get("no_significant_drop") and not ss.get("no_significant_drop"):
            problems.append(f"slice {name} dropped no_significant_drop")
    return problems


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    for mid, val in (pr.get("metrics") or {}).items():
        if isinstance(val, (int, float)) and not isinstance(val, bool) and not math.isfinite(float(val)):
            problems.append(f"metric {mid} is NaN/inf")
    manifest = pr.get("manifest") or {}
    items = int(manifest.get("items") or 0)
    seeds = list(manifest.get("seeds") or [])
    expected_rows = items * len(seeds) if items and seeds else None
    rows = pr.get("rows") or []
    if expected_rows is not None and len(rows) != expected_rows:
        problems.append(f"row count {len(rows)} != items×seeds {expected_rows}")
    pr_keys = {(r.get("item_id"), r.get("seed")) for r in rows}
    base_keys = {(r.get("item_id"), r.get("seed")) for r in base.get("rows") or []}
    if pr_keys != base_keys:
        problems.append("(item_id, seed) set differs from baseline")
    if pr.get("evaluator_failures"):
        problems.append("evaluator_failures non-empty")
    row_metric_ids = set()
    for r in rows:
        row_metric_ids.update(k for k in r if k not in {"item_id", "seed", "slices", "cost"})
    for mid in [m["id"] for m in spec.get("metrics") or [] if m["id"] in row_metric_ids]:
        for r in rows:
            if mid in r and r[mid] is None:
                problems.append(f"row {r.get('item_id')}@{r.get('seed')} metric {mid} is None")
                break
    if base_spec is not None:
        problems.extend(_ratchet_problems(spec, base_spec))
    pr_slices = _item_slices(pr)
    base_slices = _item_slices(base)
    for item_id, tags in base_slices.items():
        if item_id in pr_slices and pr_slices[item_id] != tags:
            problems.append(f"item {item_id} slice tags changed")
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices") or []:
        name, mid = sl["name"], sl["metric"]
        per = per_item(pr, mid, slice_name=name)
        val = (sum(per.values()) / len(per)) if per else None
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "min" in sl and val < float(sl["min"]):
            verdict = "fail"
        if sl.get("no_significant_drop") and val is not None:
            a = per_item(pr, mid, slice_name=name)
            b = per_item(base, mid, slice_name=name)
            keys = sorted(set(a) & set(b))
            if keys:
                d, lo, hi = stats.paired_bootstrap(
                    [a[k] for k in keys], [b[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                )
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        sid = f"slice:{name}/{mid}"
        if verdict != "ok" and sl.get("blocking"):
            blocked.append(sid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if sl.get("blocking") else "warn")
        th = {k: sl[k] for k in ("min", "no_significant_drop") if k in sl}
        lines.append(f"  {sid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
