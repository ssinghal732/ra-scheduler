"""Unit tests for role slotting (the trickiest pure logic) and target math.

Run:  python -m pytest tests/ -q     (or: python tests/test_roles.py)
"""
import random
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ra_scheduler.models import RA, ShiftInstance, compute_targets
from ra_scheduler.roles import FD_P, FD_S, GR_P, GR_S, RoleError, assign_roles

TIERS = {"E1": "returner", "E2": "LRA", "N1": "new", "N2": "new", "N3": "new"}


def _shift(d: date, shift: str) -> ShiftInstance:
    return ShiftInstance(sid=0, date=d, dow="Saturday", shift=shift,
                         time="", rounds="", week="1")


PAIRING_DAY = date(2026, 10, 3)      # inside Sep 14 - Oct 18
NORMAL_DAY = date(2026, 11, 7)       # after Oct 18


def test_pairing_4person_pairs_are_mixed_for_every_seed():
    s = _shift(PAIRING_DAY, "Evening (Weekend)")
    for seed in range(200):
        t = assign_roles(s, ["E1", "E2", "N1", "N2"], TIERS, random.Random(seed))
        assert set(t) == {FD_P, FD_S, GR_P, GR_S}
        for pair in ((t[FD_P], t[GR_P]), (t[FD_S], t[GR_S])):
            assert sum(1 for p in pair if TIERS[p] == "new") == 1, f"seed {seed}: {t}"


def test_pairing_2person_pair_is_mixed_and_labels_randomized():
    s = _shift(PAIRING_DAY, "Morning")
    primary_tiers = set()
    for seed in range(100):
        t = assign_roles(s, ["N1", "E1"], TIERS, random.Random(seed))
        assert {t[FD_P], t[FD_S]} == {"N1", "E1"}  # pair stays exp+new
        primary_tiers.add(TIERS[t[FD_P]])
    assert primary_tiers == {"new", "returner"}  # both orders occur across seeds


def test_pairing_rejects_wrong_composition():
    s = _shift(PAIRING_DAY, "Evening (Weekend)")
    try:
        assign_roles(s, ["N1", "N2", "N3", "E1"], TIERS, random.Random(0))
        assert False, "should have raised"
    except RoleError:
        pass


def test_normal_shift_fills_all_roles_with_all_people():
    s = _shift(NORMAL_DAY, "Evening (Weekend)")
    t = assign_roles(s, ["N1", "N2", "N3", "E1"], TIERS, random.Random(1))
    assert sorted(t.values()) == ["E1", "N1", "N2", "N3"]


def test_wrong_headcount_raises():
    s = _shift(NORMAL_DAY, "Morning")
    try:
        assign_roles(s, ["N1", "N2", "N3"], TIERS, random.Random(0))
        assert False, "should have raised"
    except RoleError:
        pass


def test_targets_match_locked_decisions():
    roster = ([RA(f"L{i}", f"L{i}", "LRA") for i in range(3)]
              + [RA(f"R{i}", f"R{i}", "returner") for i in range(14)]
              + [RA(f"N{i}", f"N{i}", "new") for i in range(26)])
    t = compute_targets(448, roster)  # this quarter's seat count
    assert t == {"new": 11, "returner": 10, "LRA": 5}  # D3 + F3


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all tests passed")
