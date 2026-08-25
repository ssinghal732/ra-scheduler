"""Pre-solve arithmetic check: says WHY a solve is going to fail, before it does.

CP-SAT reports infeasibility as one word. This module counts, in plain numbers,
the things that make a solve impossible, and names the date attached to each.

It is a necessary-condition check, not a proof. Counting per shift misses
interaction: if one RA is the only person free for two different shifts, both
look fine here and the solve still fails. The solver stays the authority.

Three families of finding:
  BLOCKING  the solve cannot succeed; the arithmetic already rules it out
  TIGHT     legal but with no slack, which forces those people and squeezes fairness
  NOTE      probably a data problem rather than a scheduling one

Run it after parsing and before solving. It never blocks the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict

from itertools import combinations

from .models import (
    BACK_TO_BACK_PAIRS,
    BLOCK_NORMAL,
    BLOCK_PAIRING,
    BLOCK_RETURNERS_ONLY,
    AvailabilityData,
    ShiftInstance,
)

BLOCKING, TIGHT, NOTE = "BLOCKING", "TIGHT", "NOTE"
SLACK_IS_TIGHT = 1  # spare seats at or below this get reported


@dataclass(frozen=True)
class Finding:
    severity: str
    where: str    # a date, a block name, or an ra_id: whatever the reader needs to look at
    message: str

    def __str__(self) -> str:
        return f"[{self.severity:8s}] {self.where:24s} {self.message}"


def _most_shifts_in_one_day(names: set[str]) -> int:
    """Largest set of same-date shifts one RA could legally work, given H3.

    Brute force over subsets: a duty date carries at most three shifts, so this
    is a handful of comparisons and it stays correct if BACK_TO_BACK_PAIRS grows.
    """
    banned = {frozenset(p) for p in BACK_TO_BACK_PAIRS}
    for size in range(len(names), 0, -1):
        for combo in combinations(sorted(names), size):
            if not any(frozenset(p) in banned for p in combinations(combo, 2)):
                return size
    return 0


def _need(s: ShiftInstance) -> tuple[int, int]:
    """(experienced seats, new seats) this shift must fill, per the block rules."""
    if s.block == BLOCK_RETURNERS_ONLY:
        return s.seats, 0
    if s.block == BLOCK_PAIRING:
        return s.seats // 2, s.seats - s.seats // 2
    return 0, 0  # normal: composition is unconstrained


def check(shifts: list[ShiftInstance], data: AvailabilityData) -> list[Finding]:
    out: list[Finding] = []
    experienced = {ra.ra_id for ra in data.roster if ra.experienced}
    valid_keys = {s.key for s in shifts}

    # --- data integrity: the failure mode that looks like a scheduling conflict ---
    for ra in data.roster:
        keys = data.available.get(ra.ra_id, set())
        if not keys:
            out.append(Finding(NOTE, ra.ra_id, "available for nothing all quarter "
                                               "(non-submitter, or a parse miss)"))
        stray = keys - valid_keys
        if stray:
            sample = sorted(stray)[:2]
            out.append(Finding(NOTE, ra.ra_id,
                               f"{len(stray)} availability key(s) match no shift in the grid, "
                               f"e.g. {sample}"))

    # --- per shift: enough eligible people free to fill the seats ---
    free: dict[int, tuple[int, int]] = {}
    for s in shifts:
        exp = sum(1 for ra in data.roster
                  if ra.ra_id in experienced and s.key in data.available.get(ra.ra_id, ()))
        new = sum(1 for ra in data.roster
                  if ra.ra_id not in experienced and s.key in data.available.get(ra.ra_id, ()))
        free[s.sid] = (exp, new)

        need_exp, need_new = _need(s)
        where = f"{s.date} {s.shift}"

        if s.block == BLOCK_NORMAL:
            slack = exp + new - s.seats
            if slack < 0:
                out.append(Finding(BLOCKING, where,
                                   f"{s.seats} seats, only {exp + new} RAs free"))
            elif slack <= SLACK_IS_TIGHT:
                out.append(Finding(TIGHT, where,
                                   f"{s.seats} seats, {exp + new} RAs free ({slack} spare)"))
            continue

        for label, have, want in (("experienced", exp, need_exp), ("new", new, need_new)):
            if want == 0:
                continue
            slack = have - want
            if slack < 0:
                out.append(Finding(BLOCKING, where,
                                   f"needs {want} {label}, only {have} free"))
            elif slack <= SLACK_IS_TIGHT:
                out.append(Finding(TIGHT, where,
                                   f"needs {want} {label}, {have} free ({slack} spare)"))

    # --- per block: the total can fall short even when no single shift looks short ---
    # This is the returners-only week's real risk: 32 seats over 17 people is fine
    # only if each of them can take about two, and H3 caps what one person covers
    # per date. A per-shift count alone never sees that ceiling.
    by_date: dict[str, dict[object, set[str]]] = defaultdict(lambda: defaultdict(set))
    for s in shifts:
        by_date[s.block][s.date].add(s.shift)

    def capacity_of(pool: set[str], block: str) -> tuple[int, int]:
        """(seats this pool could cover in the block, how many of them are usable)."""
        total, bodies = 0, 0
        for rid in pool:
            free = data.available.get(rid, set())
            mine = sum(
                _most_shifts_in_one_day({n for n in names if f"{d.isoformat()}|{n}" in free})
                for d, names in by_date[block].items()
            )
            total += mine
            bodies += 1 if mine else 0
        return total, bodies

    all_ids = {ra.ra_id for ra in data.roster}
    new_ids = all_ids - experienced

    for block in (BLOCK_RETURNERS_ONLY, BLOCK_PAIRING, BLOCK_NORMAL):
        in_block = [s for s in shifts if s.block == block]
        if not in_block:
            continue
        seats = sum(s.seats for s in in_block)

        # Split the demand the way the block's own rule splits it. Checking the
        # whole pool against all seats is redundant with the per-shift counts;
        # checking each tier against the seats only that tier can fill is not.
        if block == BLOCK_RETURNERS_ONLY:
            demands = [("experienced RA", experienced, seats)]
        elif block == BLOCK_PAIRING:
            demands = [("experienced RA", experienced, sum(s.seats // 2 for s in in_block)),
                       ("new RA", new_ids, sum(s.seats - s.seats // 2 for s in in_block))]
        else:
            demands = [("RA", all_ids, seats)]

        for label, pool, needed in demands:
            cap, bodies = capacity_of(pool, block)
            if cap < needed:
                out.append(Finding(BLOCKING, block,
                                   f"{needed} seats need an {label}; the {len(pool)} of them "
                                   f"can supply at most {cap} without breaking the same-day rule"))
            elif not bodies:
                out.append(Finding(BLOCKING, block, f"no {label} is available at all"))
            else:
                out.append(Finding(NOTE, block,
                                   f"{needed} seats for {bodies} available {label}s "
                                   f"({needed / bodies:.1f} each), capacity {cap}"))

    order = {BLOCKING: 0, TIGHT: 1, NOTE: 2}
    return sorted(out, key=lambda f: (order[f.severity], f.where))


def summarize(findings: list[Finding]) -> str:
    n = defaultdict(int)
    for f in findings:
        n[f.severity] += 1
    return f"{n[BLOCKING]} blocking, {n[TIGHT]} tight, {n[NOTE]} notes"
