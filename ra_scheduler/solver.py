"""CP-SAT selection model: decides WHO works each shift.

Hard rules (never violated):
  H1 availability   H2 exact fill   H3 no same-day back-to-back weekend shifts
  H4 returners-only week (new RAs ineligible)   H5 pairing = half experienced

Soft objective, in priority order (all soft per F1 - only availability blocks):
  P1 training floor: every new RA >= TRAIN_FLOOR pairing-period shifts (Q1)
  P2 minimax fairness: minimize the largest |count - target| (F2)
  P3 weekday/weekend balance: everyone's mix near the grid's own ratio
  P4 spread across the quarter: at most one shift per person per week, softly
  P5 spread deviations; heavier weight pulls LRAs to their target (F3)
  P6 preferences: weekday rank, weekend day, weekend time

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

from dataclasses import dataclass, field
from collections import defaultdict
from datetime import date, timedelta

from ortools.sat.python import cp_model

from .models import (
    BACK_TO_BACK_PAIRS,
    BLOCK_PAIRING,
    BLOCK_RETURNERS_ONLY,
    MAX_RANK_COST,
    MAX_SHIFTS_PER_WEEK,
    MAX_WEEKEND_COST,
    TIER_LRA,
    TIER_NEW,
    WEEKEND_TIME_LABEL,
    AvailabilityData,
    ShiftInstance,
    compute_targets,
)

TRAIN_FLOOR = 2                     # Q1: minimum pairing-period shifts per new RA
W_TRAIN, W_MAXDEV, W_MAXIMB = 5000, 1000, 100   # P1 > P2 > P3
W_IMBSUM = 1                        # spread of the weekday/weekend mix
W_WEEK = 3                          # each shift beyond MAX_SHIFTS_PER_WEEK in one week
PREF_MINIMAX = False                # option A (2026-11-22, under test): also minimize the
                                    # worst single person's preference total, weighted so
                                    # one point of "worst" beats any reshuffle of the total
PREF_SEAT_MINIMAX = False           # option A, two-stage (under test): above that, minimize
                                    # the worst single seat anyone gets (nobody's 5th choice
                                    # if the grid allows it), then spread, then the total


def week_of(d: date, first: date) -> int:
    """Calendar week index, Monday to Sunday, counted from the quarter's first week."""
    first_monday = first - timedelta(days=first.weekday())
    return (d - first_monday).days // 7
DEV_WEIGHT = {TIER_LRA: 3}          # F3: stronger pull to target for LRAs (default 1)


def _weekday_share(shifts: list[ShiftInstance]) -> float:
    """What fraction of the quarter's seats are weekday evenings.

    Derived from the grid, not hardcoded: this quarter it is 240/448 = 53.6%,
    which is why a 10-shift returner's balanced split comes out 5 and 5.
    """
    total = sum(s.seats for s in shifts)
    weekday = sum(s.seats for s in shifts if s.shift == "Evening (Weekday)")
    return weekday / total if total else 0.0


def _preference_cost(shift: ShiftInstance, data: AvailabilityData, ra_id: str) -> int:
    """What it costs to put this RA on this shift, in preference points only."""
    prefs = data.prefs(ra_id)
    if shift.shift == "Evening (Weekday)":
        return prefs.weekday_cost(shift.dow)
    label = WEEKEND_TIME_LABEL.get(shift.shift)
    return prefs.weekend_cost(shift.dow, label) if label else 0


def _worst_total_pref(shifts: list[ShiftInstance]) -> int:
    """The largest preference total any schedule on this grid could pay."""
    return sum(s.seats * (MAX_RANK_COST if s.shift == "Evening (Weekday)"
                          else MAX_WEEKEND_COST)
               for s in shifts)


def _fairness_scale(shifts: list[ShiftInstance]) -> int:
    """Big enough that all preferences together cannot outweigh one unit of fairness.

    Derived from the grid rather than hardcoded, the same way targets are, so a
    changed grid or a changed cost curve cannot quietly invert the priority.
    With PREF_MINIMAX on, the preference tier also carries the worst-person term
    at weight (worst_total + 1), so the scale grows to cover that too.
    """
    return _pref_tier_max(shifts) + 1


def _pref_tier_max(shifts: list[ShiftInstance]) -> int:
    """Largest value the whole preference tier can take, given the flags."""
    worst = _worst_total_pref(shifts)
    top = worst                                   # plain total
    if PREF_MINIMAX:
        top += (worst + 1) * worst                # worst person, weight worst+1
    if PREF_SEAT_MINIMAX:
        top += (top + 1) * max(MAX_RANK_COST, MAX_WEEKEND_COST)   # worst seat, above both
    return top


@dataclass
class SolveResult:
    status: str
    assignment: dict[int, list[str]]      # sid -> [ra_id]
    targets: dict[str, int]               # tier -> target count
    counts: dict[str, int]                # ra_id -> shifts assigned
    max_deviation: int
    training_shortfalls: dict[str, int]   # new RAs below the floor -> missing shifts
    preference_cost: int = 0              # total soft-preference points paid
    worst_person_pref: int = 0            # option A: largest single person's preference total
    worst_seat_pref: int = 0              # option A two-stage: costliest single seat anyone got
    max_imbalance: int = 0                # worst weekday/weekend mix, shifts from ideal
    weekday_counts: dict[str, int] = field(default_factory=dict)
    ideal_weekday: dict[str, int] = field(default_factory=dict)   # tier -> ideal
    week_excess: int = 0                  # shifts beyond one-per-week, summed over everyone
    busiest_week: int = 0                 # most shifts any one person has in one week

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

    # P3: weekday/weekend balance (soft). An RA who cannot do weekdays at all
    # legitimately ends up weekend-heavy, so this is a goal the solver abandons
    # when availability will not allow it, never a rule.
    share = _weekday_share(shifts)
    ideal_weekday = {tier_name: round(target * share) for tier_name, target in targets.items()}
    max_imb = m.NewIntVar(0, len(shifts), "max_imbalance")
    wk_vars, imb_vars = {}, {}
    for ra in data.roster:
        wc = m.NewIntVar(0, len(shifts), f"weekday_{ra.ra_id}")
        m.Add(wc == sum(
            v for (rid, sid), v in x.items()
            if rid == ra.ra_id and shifts[sid].shift == "Evening (Weekday)"
        ))
        imb = m.NewIntVar(0, len(shifts), f"imbalance_{ra.ra_id}")
        want = ideal_weekday[ra.tier]
        m.Add(wc - want <= imb)
        m.Add(want - wc <= imb)
        m.Add(imb <= max_imb)
        wk_vars[ra.ra_id], imb_vars[ra.ra_id] = wc, imb

    # P4: spread across the quarter (soft). One of the leads' unwritten rules:
    # nobody done by week four while someone else only works the last few weeks.
    first_date = min(s.date for s in shifts)
    weeks: dict[int, list[int]] = defaultdict(list)
    for s in shifts:
        weeks[week_of(s.date, first_date)].append(s.sid)
    excess_vars = []
    week_count_vars = []
    for ra in data.roster:
        for w, sids in weeks.items():
            vs = [x[(ra.ra_id, sid)] for sid in sids if (ra.ra_id, sid) in x]
            if len(vs) <= MAX_SHIFTS_PER_WEEK:
                continue                      # cannot exceed the cap this week anyway
            wc = m.NewIntVar(0, len(vs), f"week_{ra.ra_id}_{w}")
            m.Add(wc == sum(vs))
            ex = m.NewIntVar(0, len(vs), f"weekexcess_{ra.ra_id}_{w}")
            m.Add(ex >= wc - MAX_SHIFTS_PER_WEEK)
            excess_vars.append(ex)
            week_count_vars.append(wc)

    # P1: training floor (soft). Only when the quarter has a pairing block;
    # with no pairing shifts to count, every new RA would read as short.
    shortfall_vars = {}
    has_pairing = any(s.block == BLOCK_PAIRING for s in shifts)
    for ra in data.roster:
        if ra.tier != TIER_NEW or not has_pairing:
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

    # Option A: the worst single person's preference total, lexicographically
    # above the plain total (weight = worst possible total + 1) and below fairness.
    worst_pref = worst_seat = None
    pref_objective = sum(pref_terms)
    worst_total = _worst_total_pref(shifts)
    if PREF_MINIMAX:
        person_pref = {}
        for ra in data.roster:
            pp = m.NewIntVar(0, worst_total, f"pref_{ra.ra_id}")
            m.Add(pp == sum(
                _preference_cost(shifts[sid], data, rid) * v
                for (rid, sid), v in x.items()
                if rid == ra.ra_id and _preference_cost(shifts[sid], data, rid)
            ))
            person_pref[ra.ra_id] = pp
        worst_pref = m.NewIntVar(0, worst_total, "worst_pref")
        for pp in person_pref.values():
            m.Add(worst_pref >= pp)
        pref_objective = (worst_total + 1) * worst_pref + sum(pref_terms)
    if PREF_SEAT_MINIMAX:
        below = worst_total + ((worst_total + 1) * worst_total if PREF_MINIMAX else 0)
        worst_seat = m.NewIntVar(0, max(MAX_RANK_COST, MAX_WEEKEND_COST), "worst_seat")
        for (rid, sid), v in x.items():
            c = _preference_cost(shifts[sid], data, rid)
            if c:
                m.Add(worst_seat >= c * v)
        pref_objective = (below + 1) * worst_seat + pref_objective

    m.Minimize(
        scale * (
            W_TRAIN * sum(shortfall_vars.values())
            + W_MAXDEV * max_dev
            + W_MAXIMB * max_imb
            + sum(DEV_WEIGHT.get(tier[rid], 1) * d for rid, d in dev_vars.items())
            + W_IMBSUM * sum(imb_vars.values())
            + W_WEEK * sum(excess_vars)
        )
        + pref_objective
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
        max_imbalance=sv.Value(max_imb),
        worst_person_pref=sv.Value(worst_pref) if worst_pref is not None else 0,
        worst_seat_pref=sv.Value(worst_seat) if worst_seat is not None else 0,
        weekday_counts={rid: sv.Value(w) for rid, w in wk_vars.items()},
        ideal_weekday=ideal_weekday,
        week_excess=sum(sv.Value(e) for e in excess_vars),
        busiest_week=max((sv.Value(wc) for wc in week_count_vars), default=0),
    )
