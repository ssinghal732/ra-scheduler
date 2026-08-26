"""Synthetic roster, availability, and preferences.

The real form parser replaces this module and nothing downstream changes: both
produce an AvailabilityData. Every field the form collects is generated here in
the same shape the parser must emit, so the swap is a swap and not a rewrite.

Availability means "physically can work" (class schedule, blackout dates).
Eligibility rules (returners-only week, pairing) are the solver's job and are
deliberately NOT baked in here.

The SHAPE mirrors the real form. The DISTRIBUTION is invented: how lopsided
real rankings are is unknown until responses land, and that distribution is
what decides how many people can actually get their first choice.
"""
from __future__ import annotations

import random

from .models import (
    FRONT_DESK,
    GAME_ROOM,
    TIER_LRA,
    TIER_NEW,
    TIER_RETURNER,
    RA,
    AvailabilityData,
    Preferences,
    ShiftInstance,
)

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
ROSTER_SHAPE = ((TIER_LRA, 3), (TIER_RETURNER, 14), (TIER_NEW, 26))  # D3
WEEKEND_TIMES = ("Morning", "Afternoon", "Evening")


def _make_preferences(rng: random.Random, conflict_days: set[str]) -> Preferences:
    """One RA's answers to the four preference questions on the form.

    Weekday rows marked "Class Conflict/Unavailable" carry no rank, matching the
    form: each row is either a rank or the conflict option, never both.
    """
    rankable = [d for d in WEEKDAYS if d not in conflict_days]
    rng.shuffle(rankable)
    weekday_rank = {d: i + 1 for i, d in enumerate(rankable)}

    # "[Saturdays]" / "[Sundays]" / "[Open]" - open is the empty set
    weekend_days = rng.choice(({"Saturday"}, {"Sunday"}, set(), set()))

    # "mark all that apply" across Morning/Afternoon/Evening; picking all three
    # or none both mean no preference, so both come out as the empty set
    picked = {t for t in WEEKEND_TIMES if rng.random() < 0.45}
    weekend_times = set() if len(picked) in (0, 3) else picked

    location = rng.choice((FRONT_DESK, GAME_ROOM, "", ""))  # "" = open to either
    return Preferences(weekday_rank=weekday_rank, weekend_days=weekend_days,
                       weekend_times=weekend_times, location=location)


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
    preferences: dict[str, Preferences] = {}
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
        preferences[ra.ra_id] = _make_preferences(rng, conflict_days)
    return AvailabilityData(roster=roster, available=available,
                            blackout_dates=blackouts, preferences=preferences)
