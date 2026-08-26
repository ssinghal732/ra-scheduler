"""CP-SAT selection model: decides WHO works each shift.

Hard rules (never violated):
  H1 availability   H2 exact fill   H3 no same-day back-to-back weekend shifts
  H4 returners-only week (new RAs ineligible)   H5 pairing = half experienced

Soft objective, in priority order (all soft per F1 - only availability blocks):
  P1 training floor: every new RA >= TRAIN_FLOOR pairing-period shifts (Q1)
  P2 minimax fairness: minimize the largest |count - target| (F2)
  P3 spread deviations; heavier weight pulls LRAs to their target (F3)
  P4 preferences: weekday rank, weekend day, weekend time

P4 is a TIEBREAKER and nothing more. Shivam's call 2026-08-26: solve for
fairness. The fairness terms are scaled by more than the worst possible total
preference cost, so no arrangement of preferences can ever justify moving one
person one shift off their target. Among schedules that are equally fair, the
solver then picks the one people asked for. There is enough weekday capacity
(48 seats on each of five days) that this rarely costs anything.

Desk preference (Front Desk vs Game Room) is NOT here. The solver never learns
that desks exist; it picks people and roles.py seats them. See roles.py.

Role labels (who is Primary, who is at which desk) are NOT decided here; see
roles.py. This module returns plain data and has no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict

from ortools.sat.python import cp_model

from .models import (
    BACK_TO_BACK_PAIRS,
    BLOCK_PAIRING,
    BLOCK_RETURNERS_ONLY,
    MAX_RANK_COST,
    MAX_WEEKEND_COST,
    TIER_LRA,
    TIER_NEW,
    WEEKEND_TIME_LABEL,
    AvailabilityData,
    ShiftInstance,
    compute_targets,
)

TRAIN_FLOOR = 2          # Q1: minimum pairing-period shifts per new RA
W_TRAIN, W_MAXDEV = 5000, 1000  # P1 > P2 > P3
DEV_WEIGHT = {TIER_LRA: 3}      # F3: stronger pull to target for LRAs (default 1)


def _preference_cost(shift: ShiftInstance, data: AvailabilityData, ra_id: str) -> int:
    """What it costs to put this RA on this shift, in preference points only."""
    prefs = data.prefs(ra_id)
    if shift.shift == "Evening (Weekday)":
        return prefs.weekday_cost(shift.dow)
    label = WEEKEND_TIME_LABEL.get(shift.shift)
    return prefs.weekend_cost(shift.dow, label) if label else 0


def _fairness_scale(shifts: list[ShiftInstance]) -> int:
    """Big enough that all preferences together cannot outweigh one unit of fairness.

    Derived from the grid rather than hardcoded, the same way targets are, so a
    changed grid or a changed cost curve cannot quietly invert the priority.
    """
    worst = sum(s.seats * (MAX_RANK_COST if s.shift == "Evening (Weekday)"
                           else MAX_WEEKEND_COST)
                for s in shifts)
    return worst + 1


@dataclass
class SolveResult:
    status: str
    assignment: dict[int, list[str]]      # sid -> [ra_id]
    targets: dict[str, int]               # tier -> target count
    counts: dict[str, int]                # ra_id -> shifts assigned
    max_deviation: int
    training_shortfalls: dict[str, int]   # new RAs below the floor -> missing shifts
    preference_cost: int = 0              # total soft-preference points paid

    @property
    def feasible(self) -> bool:
        return self.status in ("OPTIMAL", "FEASIBLE")


def solve(
    shifts: list[ShiftInstance],
    data: AvailabilityData,
    time_limit_s: float = 60,
    workers: int = 8,
) -> SolveResult:
    tier = {ra.ra_id: ra.tier for ra in data.roster}
    experienced = {ra.ra_id for ra in data.roster if ra.experienced}
    targets = compute_targets(sum(s.seats for s in shifts), data.roster)

    m = cp_model.CpModel()

    # H1: variables exist only where the RA is available
    x: dict[tuple[str, int], cp_model.IntVar] = {}
    for s in shifts:
        for ra in data.roster:
            if s.key in data.available.get(ra.ra_id, ()):
                x[(ra.ra_id, s.sid)] = m.NewBoolVar(f"x_{ra.ra_id}_{s.sid}")

    def vars_for(s: ShiftInstance, pred=lambda rid: True):
        return [v for (rid, sid), v in x.items() if sid == s.sid and pred(rid)]

    for s in shifts:  # H2
        m.Add(sum(vars_for(s)) == s.seats)

    per_day: dict[tuple[str, object], dict[str, cp_model.IntVar]] = defaultdict(dict)  # H3
    for (rid, sid), v in x.items():
        s = shifts[sid]
        per_day[(rid, s.date)][s.shift] = v
    for day_shifts in per_day.values():
        for a, b in BACK_TO_BACK_PAIRS:
            if a in day_shifts and b in day_shifts:
                m.Add(day_shifts[a] + day_shifts[b] <= 1)

    for s in shifts:  # H4 / H5
        if s.block == BLOCK_RETURNERS_ONLY:
            m.Add(sum(vars_for(s, lambda rid: tier[rid] == TIER_NEW)) == 0)
        elif s.block == BLOCK_PAIRING:
            m.Add(sum(vars_for(s, lambda rid: rid in experienced)) == s.seats // 2)

    # P2/P3: fairness
    max_dev = m.NewIntVar(0, len(shifts), "max_dev")
    count_vars, dev_vars = {}, {}
    for ra in data.roster:
        c = m.NewIntVar(0, len(shifts), f"count_{ra.ra_id}")
        m.Add(c == sum(v for (rid, _), v in x.items() if rid == ra.ra_id))
        d = m.NewIntVar(0, len(shifts), f"dev_{ra.ra_id}")
        t = targets[ra.tier]
        m.Add(c - t <= d)
        m.Add(t - c <= d)
        m.Add(d <= max_dev)
        count_vars[ra.ra_id], dev_vars[ra.ra_id] = c, d

    # P1: training floor (soft)
    shortfall_vars = {}
    for ra in data.roster:
        if ra.tier != TIER_NEW:
            continue
        pc = m.NewIntVar(0, len(shifts), f"pair_count_{ra.ra_id}")
        m.Add(pc == sum(
            v for (rid, sid), v in x.items()
            if rid == ra.ra_id and shifts[sid].block == BLOCK_PAIRING
        ))
        sf = m.NewIntVar(0, TRAIN_FLOOR, f"shortfall_{ra.ra_id}")
        m.Add(sf >= TRAIN_FLOOR - pc)
        shortfall_vars[ra.ra_id] = sf

    # P4: preferences, as a strict tiebreaker under the scaled fairness terms.
    pref_terms = [
        _preference_cost(shifts[sid], data, rid) * v
        for (rid, sid), v in x.items()
        if _preference_cost(shifts[sid], data, rid)
    ]
    scale = _fairness_scale(shifts)

    m.Minimize(
        scale * (
            W_TRAIN * sum(shortfall_vars.values())
            + W_MAXDEV * max_dev
            + sum(DEV_WEIGHT.get(tier[rid], 1) * d for rid, d in dev_vars.items())
        )
        + sum(pref_terms)
    )

    sv = cp_model.CpSolver()
    sv.parameters.max_time_in_seconds = time_limit_s
    sv.parameters.num_search_workers = workers
    status = sv.StatusName(sv.Solve(m))

    if status not in ("OPTIMAL", "FEASIBLE"):
        return SolveResult(status, {}, targets, {}, -1, {}, 0)

    assignment: dict[int, list[str]] = defaultdict(list)
    for (rid, sid), v in x.items():
        if sv.Value(v):
            assignment[sid].append(rid)
    return SolveResult(
        status=status,
        assignment=dict(assignment),
        targets=targets,
        counts={rid: sv.Value(c) for rid, c in count_vars.items()},
        max_deviation=sv.Value(max_dev),
        training_shortfalls={
            rid: sv.Value(sf) for rid, sf in shortfall_vars.items() if sv.Value(sf) > 0
        },
        preference_cost=sum(
            _preference_cost(shifts[sid], data, rid)
            for (rid, sid), v in x.items() if sv.Value(v)
        ),
    )
