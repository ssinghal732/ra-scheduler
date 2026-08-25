"""Synthetic roster + availability. Thursday's real form parser replaces this
module and nothing downstream changes: both produce an AvailabilityData.

Availability means "physically can work" (class schedule, blackout dates).
Eligibility rules (returners-only week, pairing) are the solver's job and are
deliberately NOT baked in here.
"""
from __future__ import annotations

import random

from .models import (
    TIER_LRA,
    TIER_NEW,
    TIER_RETURNER,
    RA,
    AvailabilityData,
    ShiftInstance,
)

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
ROSTER_SHAPE = ((TIER_LRA, 3), (TIER_RETURNER, 14), (TIER_NEW, 26))  # D3


def make_roster() -> list[RA]:
    roster, i = [], 0
    for tier, count in ROSTER_SHAPE:
        for _ in range(count):
            roster.append(RA(ra_id=f"R{i:02d}", name=f"R{i:02d}", tier=tier))
            i += 1
    return roster


def make_availability(shifts: list[ShiftInstance], seed: int = 7) -> AvailabilityData:
    rng = random.Random(seed)
    roster = make_roster()
    all_dates = sorted({s.date for s in shifts})

    available: dict[str, set[str]] = {}
    blackouts: dict[str, set] = {}
    for ra in roster:
        conflict_days = set(rng.sample(WEEKDAYS, rng.choice((0, 1, 1, 2))))  # matrix conflicts
        blackout = set(rng.sample(all_dates, rng.randint(2, 5)))             # date can't-dos
        ok: set[str] = set()
        for s in shifts:
            if s.date in blackout:
                continue
            if s.dow in conflict_days and s.shift == "Evening (Weekday)":
                continue
            if s.shift != "Evening (Weekday)" and rng.random() < 0.12:  # weekend texture
                continue
            ok.add(s.key)
        available[ra.ra_id] = ok
        blackouts[ra.ra_id] = blackout
    return AvailabilityData(roster=roster, available=available, blackout_dates=blackouts)
