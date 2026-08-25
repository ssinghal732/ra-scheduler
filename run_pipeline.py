"""End-to-end pipeline: grid -> availability -> solve -> roles -> validate -> xlsx.

Usage:
  python run_pipeline.py --grid <schedule.xlsx> --out <filled.xlsx> [--seed N]

Availability is synthetic until the real form parser lands (Aug 27); swap in
the real AvailabilityData there and nothing else changes.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict

from ra_scheduler.grid import load_grid
from ra_scheduler.synthetic import make_availability
from ra_scheduler import preflight
from ra_scheduler.solver import solve
from ra_scheduler.roles import assign_all_roles
from ra_scheduler.validate import validate
from ra_scheduler.export import write_schedule


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0, help="role-slotting seed")
    ap.add_argument("--preflight-lines", type=int, default=20,
                    help="how many preflight findings to print")
    ap.add_argument("--preflight-all", action="store_true",
                    help="print every preflight finding")
    args = ap.parse_args()

    shifts, holidays = load_grid(args.grid)
    print(f"[grid]      {len(shifts)} shifts, {sum(s.seats for s in shifts)} seats, "
          f"{len(holidays)} holiday rows, {shifts[0].date} -> {shifts[-1].date}")

    data = make_availability(shifts)  # <- replaced by the real parser on Aug 27
    print(f"[avail]     {len(data.roster)} RAs (synthetic)")

    findings = preflight.check(shifts, data)
    print(f"[preflight] {preflight.summarize(findings)}")
    limit = len(findings) if args.preflight_all else args.preflight_lines
    for f in findings[:limit]:
        print("   ", f)
    if len(findings) > limit:
        print(f"    ... {len(findings) - limit} more (--preflight-all to see them)")

    result = solve(shifts, data)
    print(f"[solve]     {result.status}, max deviation {result.max_deviation}")
    if not result.feasible:
        print("[solve]     INFEASIBLE: some shift cannot be legally staffed.", file=sys.stderr)
        blocking = [f for f in findings if f.severity == preflight.BLOCKING]
        if blocking:
            print("[solve]     preflight already flagged why:", file=sys.stderr)
            for f in blocking[:10]:
                print("   ", f, file=sys.stderr)
        else:
            print("[solve]     preflight found nothing blocking, so the conflict is an "
                  "interaction between shifts, not a single short one.", file=sys.stderr)
        return 1
    if result.training_shortfalls:
        print(f"[solve]     WARNING: below training floor: {result.training_shortfalls}")

    roles = assign_all_roles(shifts, result.assignment, data.roster, seed=args.seed)

    errors = validate(shifts, data, result.assignment, roles)
    print(f"[validate]  {len(errors)} hard-rule/role violations")
    for e in errors[:10]:
        print("   ", e)
    if errors:
        return 2

    by_tier = defaultdict(list)
    for ra in data.roster:
        by_tier[ra.tier].append(result.counts[ra.ra_id])
    for t in ("LRA", "returner", "new"):
        c = by_tier[t]
        print(f"[fairness]  {t:9s} target {result.targets[t]:2d} -> "
              f"min {min(c)} / mean {sum(c)/len(c):.1f} / max {max(c)}")

    write_schedule(args.out, shifts, holidays, roles, data)
    print(f"[export]    wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
