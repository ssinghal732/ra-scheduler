"""Independent validation. Deliberately re-implements every rule from scratch
(shares no logic with solver.py or roles.py) so a bug in the model cannot hide
itself. "Zero violations" from here is the claim the schedulers get.
"""
from __future__ import annotations

from collections import defaultdict

from .models import (
    BACK_TO_BACK_PAIRS,
    BLOCK_PAIRING,
    BLOCK_RETURNERS_ONLY,
    AvailabilityData,
    ShiftInstance,
)
from .roles import FD_P, FD_S, GR_P, GR_S


def validate(
    shifts: list[ShiftInstance],
    data: AvailabilityData,
    assignment: dict[int, list[str]],
    roles: dict[int, dict[str, str]] | None = None,
) -> list[str]:
    errors: list[str] = []
    tier = {ra.ra_id: ra.tier for ra in data.roster}
    is_new = lambda rid: tier[rid] == "new"

    for s in shifts:
        who = assignment.get(s.sid, [])
        if len(who) != s.seats:
            errors.append(f"{s.key}: {len(who)} assigned, needs {s.seats}")
        if len(set(who)) != len(who):
            errors.append(f"{s.key}: duplicate assignment")
        for rid in who:
            if s.key not in data.available.get(rid, ()):
                errors.append(f"{s.key}: {rid} is not available")
        if s.block == BLOCK_RETURNERS_ONLY and any(is_new(r) for r in who):
            errors.append(f"{s.key}: new RA in returners-only week")
        if s.block == BLOCK_PAIRING:
            n_new = sum(1 for r in who if is_new(r))
            if n_new != s.seats // 2:
                errors.append(f"{s.key}: pairing needs {s.seats // 2} new, got {n_new}")

    # back-to-back, rebuilt from the assignment alone
    day_shifts: dict[tuple[str, object], set[str]] = defaultdict(set)
    for s in shifts:
        for rid in assignment.get(s.sid, []):
            day_shifts[(rid, s.date)].add(s.shift)
    for (rid, d), names in day_shifts.items():
        for a, b in BACK_TO_BACK_PAIRS:
            if a in names and b in names:
                errors.append(f"{rid} {d}: back-to-back {a} -> {b}")

    if roles is not None:
        for s in shifts:
            table = roles.get(s.sid, {})
            expected = {FD_P, FD_S, GR_P, GR_S} if s.seats == 4 else {FD_P, FD_S}
            if set(table) != expected:
                errors.append(f"{s.key}: role table has {sorted(table)}")
                continue
            if sorted(table.values()) != sorted(assignment.get(s.sid, [])):
                errors.append(f"{s.key}: role table people != assigned people")
            if s.block == BLOCK_PAIRING:
                if s.seats == 4:
                    pairs = ((table[FD_P], table[GR_P]), (table[FD_S], table[GR_S]))
                else:
                    pairs = ((table[FD_P], table[FD_S]),)
                for pair in pairs:
                    if sum(1 for p in pair if is_new(p)) != 1:
                        errors.append(f"{s.key}: pairing pair not 1 experienced + 1 new")
    return errors
