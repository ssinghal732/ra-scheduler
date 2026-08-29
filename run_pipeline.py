"""End-to-end pipeline: grid -> availability -> solve -> roles -> validate -> xlsx.

Usage:
  python run_pipeline.py --grid <schedule.xlsx> --out <filled.xlsx> \
      --roster <roster.xlsx> --availability <form-export.xlsx> [--sheet NAME] [--seed N]

Omit --roster and --availability and the run uses invented people: the
output filename is then forced to carry SYNTHETIC and says so.
"""
from __future__ import annotations

import argparse
import sys
import textwrap
from collections import defaultdict

from ra_scheduler.grid import load_grid
from ra_scheduler.synthetic import make_availability
from ra_scheduler import parse_form
from ra_scheduler import preflight
from ra_scheduler.solver import solve
from ra_scheduler.roles import assign_all_roles
from ra_scheduler.validate import validate
from ra_scheduler.models import WEEKEND_TIME_LABEL
from ra_scheduler.export import synthetic_path, write_schedule


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--roster", help="roster xlsx: Email | Name | Tier")
    ap.add_argument("--availability", help="Google Form response export xlsx")
    ap.add_argument("--sheet", help="sheet name inside the form export (default: first)")
    ap.add_argument("--seed", type=int, default=0, help="role-slotting seed")
    ap.add_argument("--preflight-lines", type=int, default=20,
                    help="how many preflight findings to print")
    ap.add_argument("--preflight-all", action="store_true",
                    help="print every preflight finding")
    args = ap.parse_args()

    shifts, holidays = load_grid(args.grid)
    print(f"[grid]      {len(shifts)} shifts, {sum(s.seats for s in shifts)} seats, "
          f"{len(holidays)} holiday rows, {shifts[0].date} -> {shifts[-1].date}")

    availability_is_synthetic = args.availability is None
    if availability_is_synthetic:
        if args.roster:
            print("[avail]     --roster given without --availability; using synthetic for both",
                  file=sys.stderr)
        data = make_availability(shifts)
        print(f"[avail]     {len(data.roster)} RAs (SYNTHETIC, invented people)")
    else:
        if not args.roster:
            print("[avail]     --availability needs --roster too", file=sys.stderr)
            return 1
        data, report = parse_form.load(args.roster, args.availability, shifts, sheet=args.sheet)
        for k, v in report.matched.items():
            print(f"[parse]     {k:16s} <- {v}")
        print(f"[parse]     {report.summary()}")
        reads: dict[str, list[tuple[str, str]]] = {}
        for sev, label, fs in report.grouped():
            if sev == parse_form.READ:
                for f in fs:                      # gather; printed per person below
                    box, _, text = f.message.partition(": ")
                    reads.setdefault(f.who, []).append((box.replace(" concerns", ""), text))
                continue
            print(f"    {sev}  {label}  ({len(fs)})")
            for f in fs:
                print(f"        {f.who:28s} {f.message}")
        if reads:
            n = sum(len(v) for v in reads.values())
            print(f"    READ  concerns boxes, read every one  ({n} from {len(reads)} people)")
            for who in sorted(reads, key=str.lower):
                print(f"        {who}")
                for box, text in reads[who]:
                    print(textwrap.fill(text, width=76,
                                        initial_indent=f"          {box + ':':9s}",
                                        subsequent_indent=" " * 19))
                print()
        if report.must_stop:
            print("[parse]     STOP findings above must be resolved before solving.", file=sys.stderr)
            return 3
        print(f"[avail]     {len(data.roster)} RAs from the form export")

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

    roles = assign_all_roles(shifts, result.assignment, data.roster, seed=args.seed, data=data)

    errors = validate(shifts, data, result.assignment, roles)
    print(f"[validate]  {len(errors)} hard-rule/role violations")
    for e in errors[:10]:
        print("   ", e)
    if errors:
        return 2

    at_ideal = sum(1 for ra in data.roster
                   if result.weekday_counts.get(ra.ra_id) == result.ideal_weekday[ra.tier])
    print(f"[balance]   worst weekday/weekend imbalance {result.max_imbalance} shift(s); "
          f"{at_ideal}/{len(data.roster)} RAs on their ideal mix")
    for tname in ("LRA", "returner", "new"):
        want = result.ideal_weekday[tname]
        print(f"[balance]   {tname:9s} ideal {want} weekday / "
              f"{result.targets[tname] - want} weekend")

    print(f"[spread]    {result.week_excess} shift(s) beyond one-per-person-per-week; "
          f"busiest anyone gets in a single week: {result.busiest_week}")

    by_tier = defaultdict(list)
    for ra in data.roster:
        by_tier[ra.tier].append(result.counts[ra.ra_id])
    for t in ("LRA", "returner", "new"):
        c = by_tier[t]
        print(f"[fairness]  {t:9s} target {result.targets[t]:2d} -> "
              f"min {min(c)} / mean {sum(c)/len(c):.1f} / max {max(c)}")

    # The form promises RAs their 1st or 2nd choice weekday. Report against that.
    got, missed, weekend_ok, weekend_n = 0, 0, 0, 0
    for s in shifts:
        for rid in result.assignment.get(s.sid, []):
            prefs = data.prefs(rid)
            if s.shift == "Evening (Weekday)" and prefs.weekday_rank:
                if prefs.weekday_rank.get(s.dow, 9) <= 2:
                    got += 1
                else:
                    missed += 1
            label = WEEKEND_TIME_LABEL.get(s.shift)
            if label and (prefs.weekend_days or prefs.weekend_times):
                weekend_n += 1
                weekend_ok += prefs.weekend_cost(s.dow, label) == 0
    if got + missed:
        print(f"[prefs]     weekday shifts on a 1st or 2nd choice day: "
              f"{got}/{got + missed} ({got / (got + missed):.0%})")
    if weekend_n:
        print(f"[prefs]     weekend shifts matching day AND time asked for: "
              f"{weekend_ok}/{weekend_n} ({weekend_ok / weekend_n:.0%})")
    desk_ok = desk_n = 0
    for sid, table in roles.items():
        for role, rid in table.items():
            want = data.prefs(rid).location
            if want:
                desk_n += 1
                desk_ok += want.startswith("Front") == role.startswith("Front")
    if desk_n:
        print(f"[prefs]     seated at the desk they asked for: "
              f"{desk_ok}/{desk_n} ({desk_ok / desk_n:.0%})")
    print(f"[prefs]     total preference cost {result.preference_cost} "
          f"(0 = everyone got everything)")

    out = synthetic_path(args.out) if availability_is_synthetic else args.out
    write_schedule(out, shifts, holidays, roles, data)
    print(f"[export]    wrote {out}")
    if availability_is_synthetic:
        if out != args.out:
            print(f"[export]    renamed from {args.out}: availability was synthetic")
        print("[export]    These are invented people on real dates. Do not send this to anyone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
