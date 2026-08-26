"""Tests for the soft-preference layer.

The property that matters most is the FIRST one: fairness must strictly beat
every preference combined. Shivam's call 2026-08-26, "solve for fairness".
If that inverts, the tool starts trading someone's fair share for someone
else's convenience, quietly.

Run:  python tests/test_preferences.py
"""
import random
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ra_scheduler.models import (
    FRONT_DESK, GAME_ROOM, MAX_RANK_COST, MAX_WEEKEND_COST, RANK_COST,
    WRONG_WEEKEND_DAY, WRONG_WEEKEND_TIME,
    RA, AvailabilityData, Preferences, ShiftInstance,
)
from ra_scheduler.roles import FD_P, FD_S, GR_P, GR_S, assign_roles
from ra_scheduler.solver import _fairness_scale, _preference_cost

NORMAL_DAY = date(2026, 11, 7)      # after the pairing block
PAIRING_DAY = date(2026, 10, 3)


def _shift(shift="Evening (Weekday)", d=NORMAL_DAY, dow="Saturday", sid=0):
    return ShiftInstance(sid=sid, date=d, dow=dow, shift=shift, time="", rounds="", week="1")


# --------------------------------------------------------------------------- #
# The priority guarantee
# --------------------------------------------------------------------------- #

def test_fairness_scale_exceeds_every_possible_preference_cost():
    """One unit of unfairness must cost more than all preferences put together."""
    shifts = ([_shift(sid=i) for i in range(60)]
              + [_shift("Morning", dow="Saturday", sid=100 + i) for i in range(26)]
              + [_shift("Evening (Weekend)", dow="Sunday", sid=200 + i) for i in range(26)])
    worst = sum(s.seats * (MAX_RANK_COST if s.shift == "Evening (Weekday)"
                           else MAX_WEEKEND_COST) for s in shifts)
    assert _fairness_scale(shifts) > worst, "preferences could outweigh fairness"
    assert _fairness_scale(shifts) == worst + 1, "scale should be tight, not arbitrary"


def test_rank_cost_treats_first_and_second_choice_as_kept():
    """The form promises 'your first or second most preferred weekday'."""
    assert RANK_COST[1] == RANK_COST[2] == 0
    assert RANK_COST[3] < RANK_COST[4] < RANK_COST[5]
    assert RANK_COST[5] - RANK_COST[4] == RANK_COST[4] - RANK_COST[3], "steps stay gentle"


# --------------------------------------------------------------------------- #
# Cost calculation
# --------------------------------------------------------------------------- #

def _data(prefs):
    roster = [RA("A", "A", "new")]
    return AvailabilityData(roster=roster, available={}, preferences={"A": prefs})


def test_no_preferences_costs_nothing():
    d = AvailabilityData(roster=[RA("A", "A", "new")], available={})
    for s in (_shift(), _shift("Morning"), _shift("Evening (Weekend)")):
        assert _preference_cost(s, d, "A") == 0


def test_weekday_cost_follows_the_rank():
    d = _data(Preferences(weekday_rank={"Monday": 1, "Friday": 5}))
    assert _preference_cost(_shift(dow="Monday"), d, "A") == 0
    assert _preference_cost(_shift(dow="Friday"), d, "A") == RANK_COST[5]
    assert _preference_cost(_shift(dow="Tuesday"), d, "A") == 0   # unranked, no opinion


def test_weekend_cost_adds_wrong_day_and_wrong_time():
    d = _data(Preferences(weekend_days={"Saturday"}, weekend_times={"Morning"}))
    assert _preference_cost(_shift("Morning", dow="Saturday"), d, "A") == 0
    assert _preference_cost(_shift("Evening (Weekend)", dow="Saturday"), d, "A") == WRONG_WEEKEND_TIME
    assert _preference_cost(_shift("Morning", dow="Sunday"), d, "A") == WRONG_WEEKEND_DAY
    assert (_preference_cost(_shift("Evening (Weekend)", dow="Sunday"), d, "A")
            == WRONG_WEEKEND_DAY + WRONG_WEEKEND_TIME)


def test_priority_order_matches_the_ranking_shivam_gave():
    """1. weekday  2. weekend day  3. weekend time  4. desk location.

    Encoded so the worst miss in each category outranks the worst in the next.
    Desk is absent on purpose: roles.py settles it after the schedule exists, so
    it can never pull someone off the day or time they asked for.
    """
    assert MAX_RANK_COST > WRONG_WEEKEND_DAY > WRONG_WEEKEND_TIME > 0

    # right day / wrong time must beat wrong day / right time
    d = _data(Preferences(weekend_days={"Saturday"}, weekend_times={"Morning"}))
    right_day = _preference_cost(_shift("Evening (Weekend)", dow="Saturday"), d, "A")
    right_time = _preference_cost(_shift("Morning", dow="Sunday"), d, "A")
    assert right_day < right_time


def test_weekday_prefs_do_not_leak_into_weekend_shifts():
    d = _data(Preferences(weekday_rank={"Saturday": 5}))
    assert _preference_cost(_shift("Morning", dow="Saturday"), d, "A") == 0


# --------------------------------------------------------------------------- #
# Desk seating, which lives in roles.py and not the solver
# --------------------------------------------------------------------------- #

TIERS = {"E1": "returner", "E2": "LRA", "N1": "new", "N2": "new"}


def test_desk_preference_is_honoured_when_it_can_be():
    want = {"E1": FRONT_DESK, "N1": GAME_ROOM, "E2": FRONT_DESK, "N2": GAME_ROOM}
    s = _shift("Evening (Weekend)", d=NORMAL_DAY)
    for seed in range(50):
        t = assign_roles(s, ["E1", "E2", "N1", "N2"], TIERS, random.Random(seed), want)
        assert {t[FD_P], t[FD_S]} == {"E1", "E2"}, f"seed {seed}: {t}"
        assert {t[GR_P], t[GR_S]} == {"N1", "N2"}, f"seed {seed}: {t}"


def test_pairing_trains_on_the_walk_AND_the_desk():
    """Shivam 2026-08-26: both the walk and the desk shift are training.

    So all four pairings must be 1 experienced + 1 new: the two walk pairs
    (across desks) and the two desk pairs (across walks).
    """
    s = _shift("Evening (Weekend)", d=PAIRING_DAY)
    for seed in range(100):
        t = assign_roles(s, ["E1", "E2", "N1", "N2"], TIERS, random.Random(seed), {})
        checks = {"7:30 walk": (t[FD_P], t[GR_P]), "9:30 walk": (t[FD_S], t[GR_S]),
                  "front desk": (t[FD_P], t[FD_S]), "game room": (t[GR_P], t[GR_S])}
        for label, pair in checks.items():
            assert sum(1 for p in pair if TIERS[p] == "new") == 1, \
                f"seed {seed}: {label} not mixed in {t}"


def test_desk_preference_never_breaks_the_training_rule():
    """Everyone wanting the same desk must not bend the composition."""
    want = {p: FRONT_DESK for p in TIERS}
    s = _shift("Evening (Weekend)", d=PAIRING_DAY)
    for seed in range(50):
        t = assign_roles(s, ["E1", "E2", "N1", "N2"], TIERS, random.Random(seed), want)
        for pair in ((t[FD_P], t[GR_P]), (t[FD_S], t[GR_S]),
                     (t[FD_P], t[FD_S]), (t[GR_P], t[GR_S])):
            assert sum(1 for p in pair if TIERS[p] == "new") == 1, f"seed {seed}: {t}"


def test_all_eight_valid_arrangements_are_reachable():
    """Nothing is quietly pinned: the tie-break really does shuffle."""
    s = _shift("Evening (Weekend)", d=PAIRING_DAY)
    seen = {tuple(assign_roles(s, ["E1", "E2", "N1", "N2"], TIERS,
                               random.Random(seed), {})[r]
                  for r in (FD_P, FD_S, GR_P, GR_S))
            for seed in range(300)}
    assert len(seen) == 8, f"expected all 8 valid arrangements, saw {len(seen)}"


def test_everyone_is_still_seated_when_desks_are_contested():
    want = {"E1": GAME_ROOM, "E2": GAME_ROOM, "N1": GAME_ROOM, "N2": GAME_ROOM}
    s = _shift("Evening (Weekend)", d=NORMAL_DAY)
    for seed in range(50):
        t = assign_roles(s, ["E1", "E2", "N1", "N2"], TIERS, random.Random(seed), want)
        assert sorted(t.values()) == ["E1", "E2", "N1", "N2"], f"seed {seed}: {t}"


def test_no_desk_preference_still_fills_every_role():
    s = _shift("Evening (Weekend)", d=NORMAL_DAY)
    t = assign_roles(s, ["E1", "E2", "N1", "N2"], TIERS, random.Random(3), {})
    assert set(t) == {FD_P, FD_S, GR_P, GR_S}
    assert sorted(t.values()) == ["E1", "E2", "N1", "N2"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all tests passed")
