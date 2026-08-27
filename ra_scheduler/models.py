"""Domain model for the RA duty scheduler.

Single source of truth for tiers, rule-blocks, staffing shapes, and load
targets. Every other module imports from here; no rule lives in two places.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# --------------------------------------------------------------------------- #
# Tiers
# --------------------------------------------------------------------------- #
TIER_LRA = "LRA"
TIER_RETURNER = "returner"
TIER_NEW = "new"
EXPERIENCED_TIERS = frozenset({TIER_LRA, TIER_RETURNER})  # D5/D6: LRA = experienced


@dataclass(frozen=True)
class RA:
    ra_id: str  # stable key; never key on free-text names (spec)
    name: str
    tier: str  # TIER_LRA | TIER_RETURNER | TIER_NEW

    @property
    def experienced(self) -> bool:
        return self.tier in EXPERIENCED_TIERS


# --------------------------------------------------------------------------- #
# Rule blocks (D1): same solver everywhere, rules gated by date
# --------------------------------------------------------------------------- #
RETURNERS_ONLY_END = date(2026, 9, 13)   # Sep 8-13: new RAs ineligible
PAIRING_END = date(2026, 10, 18)         # Sep 14-Oct 18: half experienced / half new

BLOCK_RETURNERS_ONLY = "returners_only"
BLOCK_PAIRING = "pairing"
BLOCK_NORMAL = "normal"


def block_of(d: date) -> str:
    if d <= RETURNERS_ONLY_END:
        return BLOCK_RETURNERS_ONLY
    if d <= PAIRING_END:
        return BLOCK_PAIRING
    return BLOCK_NORMAL


# --------------------------------------------------------------------------- #
# Shifts
# --------------------------------------------------------------------------- #
# shift name (as it appears in the grid) -> (front-desk seats, game-room seats)
STAFFING: dict[str, tuple[int, int]] = {
    "Evening (Weekday)": (2, 2),
    "Morning": (2, 0),
    "Afternoon": (2, 0),
    "Evening (Weekend)": (2, 2),
}

# One of the leads' unwritten rules (2026-08-27): spread each person's shifts
# across the quarter. Nobody should be done by week four while someone else
# only works the last few weeks. Encoded as a SOFT cap on shifts per person per
# calendar week (Monday to Sunday). Soft because the pairing block front-loads
# experienced RAs by rule, so a hard cap would make some quarters impossible.
MAX_SHIFTS_PER_WEEK = 1

# consecutive same-day weekend shifts (hard rule H3). Morning->Evening is fine.
BACK_TO_BACK_PAIRS = (("Morning", "Afternoon"), ("Afternoon", "Evening (Weekend)"))


@dataclass(frozen=True)
class ShiftInstance:
    sid: int                 # index into the quarter's shift list
    date: date
    dow: str                 # "Monday" ... "Sunday", as written in the grid
    shift: str               # key into STAFFING
    time: str                # display string, carried from the grid
    rounds: str              # duty-round location, carried from the grid
    week: str                # week label from the grid ("-2", "0", ...), for export

    @property
    def n_fra(self) -> int:
        return STAFFING[self.shift][0]

    @property
    def n_gra(self) -> int:
        return STAFFING[self.shift][1]

    @property
    def seats(self) -> int:
        return self.n_fra + self.n_gra

    @property
    def block(self) -> str:
        return block_of(self.date)

    @property
    def key(self) -> str:
        """Availability key. The parser and solver must agree on this format."""
        return f"{self.date.isoformat()}|{self.shift}"


# --------------------------------------------------------------------------- #
# Preferences: the SOFT signals the form collects.
#
# Every field is optional and an empty one costs nothing, so an RA who skipped
# a question is never penalised. Hard constraints never live here: a weekday
# marked "Class Conflict/Unavailable" is absent from `available` instead, which
# is what makes it unbreakable.
# --------------------------------------------------------------------------- #
FRONT_DESK, GAME_ROOM = "Front Desk", "Game Room"

# Priority order, Shivam's 2026-08-26 ranking of what he would want as an RA:
#   1. weekday          2. weekend day     3. weekend time     4. desk location
#
# Encoded as costs, so the worst miss in each category outranks the worst miss
# in the next: weekday tops out at 3, a wrong weekend day costs 2, a wrong
# weekend time costs 1. Desk location is not priced here at all; it is settled
# in roles.py AFTER the schedule exists, which is what keeps it last and stops
# it from ever pulling somebody off the day or time they asked for.
#
# The form promises "your first or second most preferred weekday", so ranks 1
# and 2 both count as kept. Past that the cost climbs by one per step: enough
# to steer, gentle enough that a 5th choice is not treated as a catastrophe.
RANK_COST = {1: 0, 2: 0, 3: 1, 4: 2, 5: 3}
MAX_RANK_COST = max(RANK_COST.values())
WRONG_WEEKEND_DAY, WRONG_WEEKEND_TIME = 2, 1
MAX_WEEKEND_COST = WRONG_WEEKEND_DAY + WRONG_WEEKEND_TIME


@dataclass
class Preferences:
    """One RA's soft preferences, in the shape the form collects them."""
    weekday_rank: dict[str, int] = field(default_factory=dict)   # "Monday" -> 1..5
    weekend_days: set[str] = field(default_factory=set)          # {"Saturday"}; empty = open
    weekend_times: set[str] = field(default_factory=set)         # {"Morning","Evening"}; empty = any
    location: str = ""                                           # FRONT_DESK | GAME_ROOM | "" = either

    def weekday_cost(self, dow: str) -> int:
        rank = self.weekday_rank.get(dow)
        return RANK_COST.get(rank, 0) if rank else 0

    def weekend_cost(self, dow: str, time_label: str) -> int:
        day = 0 if not self.weekend_days or dow in self.weekend_days else WRONG_WEEKEND_DAY
        time = 0 if not self.weekend_times or time_label in self.weekend_times else WRONG_WEEKEND_TIME
        return day + time


# "Evening (Weekend)" is the shift name; "Evening" is what the form calls it.
WEEKEND_TIME_LABEL = {"Morning": "Morning", "Afternoon": "Afternoon",
                      "Evening (Weekend)": "Evening"}


# --------------------------------------------------------------------------- #
# Availability bundle: what the form parser (or synthetic stand-in) produces
# --------------------------------------------------------------------------- #
@dataclass
class AvailabilityData:
    roster: list[RA]
    available: dict[str, set[str]]        # ra_id -> set of ShiftInstance.key they CAN work
    blackout_dates: dict[str, set[date]] = field(default_factory=dict)
    # ^ date-specific can't-dos (weddings/exams). Feeds the Exceptions column;
    #   already reflected inside `available`, kept separately only for display.
    preferences: dict[str, Preferences] = field(default_factory=dict)
    # ^ ra_id -> Preferences. Missing entries mean "no preference", which costs
    #   nothing, so the solver behaves exactly as before on data without them.

    def prefs(self, ra_id: str) -> Preferences:
        return self.preferences.get(ra_id) or Preferences()


# --------------------------------------------------------------------------- #
# Load targets (D3/F3): new = B, returner = B-1, LRA = floor(B/2)
# --------------------------------------------------------------------------- #
def compute_targets(total_seats: int, roster: list[RA]) -> dict[str, int]:
    """Derive per-tier shift targets from this quarter's seat count.

    Picks the largest baseline B whose implied total does not exceed the seats;
    the soft minimax objective absorbs the remainder as +1s. Derived (not
    hardcoded) so the same code is right if the grid ever changes.
    """
    n = {t: sum(1 for r in roster if r.tier == t) for t in (TIER_NEW, TIER_RETURNER, TIER_LRA)}
    b = 1
    while True:
        implied = n[TIER_NEW] * (b + 1) + n[TIER_RETURNER] * b + n[TIER_LRA] * ((b + 1) // 2)
        if implied > total_seats:
            break
        b += 1
    baseline = b  # b+1 overshot, so new = b, returner = b-1
    return {TIER_NEW: baseline, TIER_RETURNER: baseline - 1, TIER_LRA: baseline // 2}
