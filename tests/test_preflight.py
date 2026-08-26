"""Unit tests for the pre-solve arithmetic check.

Run:  python -m pytest tests/ -q     (or: python tests/test_preflight.py)

No ortools here: preflight reads counts, not a model, so these run anywhere.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ra_scheduler.models import RA, AvailabilityData, ShiftInstance
from ra_scheduler import preflight
from ra_scheduler.preflight import BLOCKING, NOTE, TIGHT

RETURNERS_DAY = date(2026, 9, 10)    # on or before Sep 13
PAIRING_DAY = date(2026, 10, 3)      # Sep 14 - Oct 18
NORMAL_DAY = date(2026, 11, 7)       # after Oct 18


def _shift(sid: int, d: date, shift: str) -> ShiftInstance:
    return ShiftInstance(sid=sid, date=d, dow="Saturday", shift=shift,
                         time="", rounds="", week="1")


def _data(roster, available, **kw):
    return AvailabilityData(roster=roster, available=available, **kw)


def _sev(findings, severity):
    return [f for f in findings if f.severity == severity]


def _roster(n_exp: int, n_new: int):
    return ([RA(f"E{i}", f"E{i}", "returner") for i in range(n_exp)]
            + [RA(f"N{i}", f"N{i}", "new") for i in range(n_new)])


def test_healthy_schedule_has_nothing_blocking_or_tight():
    shifts = [_shift(0, NORMAL_DAY, "Evening (Weekend)")]
    roster = _roster(4, 4)
    avail = {ra.ra_id: {shifts[0].key} for ra in roster}
    f = preflight.check(shifts, _data(roster, avail))
    assert _sev(f, BLOCKING) == []
    assert _sev(f, TIGHT) == []


def test_short_normal_shift_is_blocking_and_names_the_date():
    shifts = [_shift(0, NORMAL_DAY, "Evening (Weekend)")]   # 4 seats
    roster = _roster(2, 1)
    avail = {ra.ra_id: {shifts[0].key} for ra in roster}    # only 3 free
    blocking = _sev(preflight.check(shifts, _data(roster, avail)), BLOCKING)
    assert any(str(NORMAL_DAY) in f.where and "4 seats" in f.message for f in blocking)


def test_returners_only_shift_short_on_experienced():
    shifts = [_shift(0, RETURNERS_DAY, "Evening (Weekend)")]  # 4 seats, all experienced
    roster = _roster(3, 20)
    avail = {ra.ra_id: {shifts[0].key} for ra in roster}      # 20 new are ineligible here
    blocking = _sev(preflight.check(shifts, _data(roster, avail)), BLOCKING)
    assert any("needs 4 experienced, only 3 free" in f.message for f in blocking)


def test_pairing_shift_short_on_new_ras():
    shifts = [_shift(0, PAIRING_DAY, "Evening (Weekend)")]    # needs 2 exp + 2 new
    roster = _roster(6, 1)
    avail = {ra.ra_id: {shifts[0].key} for ra in roster}
    blocking = _sev(preflight.check(shifts, _data(roster, avail)), BLOCKING)
    assert any("needs 2 new, only 1 free" in f.message for f in blocking)


def test_exact_fit_is_tight_not_blocking():
    shifts = [_shift(0, NORMAL_DAY, "Morning")]               # 2 seats
    roster = _roster(1, 1)
    avail = {ra.ra_id: {shifts[0].key} for ra in roster}      # exactly 2 free
    f = preflight.check(shifts, _data(roster, avail))
    assert _sev(f, BLOCKING) == []
    assert any("0 spare" in x.message for x in _sev(f, TIGHT))


def test_pairing_block_short_on_experienced_though_every_shift_looks_fine():
    """The case a per-shift count cannot see, and the one most likely to be real.

    Two pairing dates, each carrying an Afternoon (2 seats, 1 experienced) and
    an Evening (4 seats, 2 experienced): 3 experienced seat-fills per date, 6
    across the block.

    Exactly 2 experienced RAs are free, both for both shifts. Per shift that
    clears: Afternoon wants 1 and has 2, Evening wants 2 and has 2. A per-shift
    count calls the whole thing fine. It is not, because Afternoon and Evening
    are a banned same-day pair, so each RA covers one shift per date and the
    two of them supply 4 seat-fills against a demand of 6.

    Narrow by construction. The blocking arm of the block check is a backstop;
    what it reports on a healthy run is the capacity number, not a failure.
    """
    dates = [date(2026, 9, 19), date(2026, 9, 26)]
    names = ["Afternoon", "Evening (Weekend)"]
    shifts = [_shift(i * 2 + j, d, n)
              for i, d in enumerate(dates) for j, n in enumerate(names)]
    roster = _roster(2, 20)
    avail = {ra.ra_id: {s.key for s in shifts} for ra in roster}

    f = preflight.check(shifts, _data(roster, avail))
    per_shift = [x for x in _sev(f, BLOCKING) if x.where != "pairing"]
    assert per_shift == [], f"no single shift should be short, got {per_shift}"
    block = [x for x in _sev(f, BLOCKING) if x.where == "pairing"]
    assert block, "the block-level experienced shortfall should be caught"
    assert "experienced RA" in block[0].message and "at most" in block[0].message


def test_block_check_stays_quiet_when_capacity_is_sufficient():
    dates = [date(2026, 9, 14 + i) for i in range(4)]
    shifts = [_shift(i, d, "Evening (Weekend)") for i, d in enumerate(dates)]
    roster = _roster(10, 10)
    avail = {ra.ra_id: {s.key for s in shifts} for ra in roster}
    assert _sev(preflight.check(shifts, _data(roster, avail)), BLOCKING) == []


def test_same_day_cap_counts_morning_plus_evening_but_not_afternoon():
    assert preflight._most_shifts_in_one_day({"Morning", "Evening (Weekend)"}) == 2
    assert preflight._most_shifts_in_one_day({"Morning", "Afternoon"}) == 1
    assert preflight._most_shifts_in_one_day({"Morning", "Afternoon", "Evening (Weekend)"}) == 2
    assert preflight._most_shifts_in_one_day({"Evening (Weekday)"}) == 1
    assert preflight._most_shifts_in_one_day(set()) == 0


def test_stray_availability_key_is_flagged():
    """The likeliest Aug 27 failure: parser emits keys the grid does not know."""
    shifts = [_shift(0, NORMAL_DAY, "Evening (Weekend)")]
    roster = _roster(4, 0)
    avail = {ra.ra_id: {shifts[0].key} for ra in roster}
    avail["E0"] = {"2026-11-07|Evening", "2026-13-40|Morning"}   # wrong shift name, bad date
    notes = _sev(preflight.check(shifts, _data(roster, avail)), NOTE)
    assert any("match no shift in the grid" in f.message and f.where == "E0" for f in notes)


def test_ra_available_for_nothing_is_flagged():
    shifts = [_shift(0, NORMAL_DAY, "Evening (Weekend)")]
    roster = _roster(4, 1)
    avail = {ra.ra_id: {shifts[0].key} for ra in roster}
    avail["N0"] = set()
    notes = _sev(preflight.check(shifts, _data(roster, avail)), NOTE)
    assert any("available for nothing" in f.message and f.where == "N0" for f in notes)


def test_findings_sort_blocking_first():
    shifts = [_shift(0, NORMAL_DAY, "Evening (Weekend)")]
    roster = _roster(1, 0)
    avail = {"E0": set()}
    f = preflight.check(shifts, _data(roster, avail))
    assert f[0].severity == BLOCKING


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all tests passed")


# --- output naming: a synthetic run must announce itself in the filename ---

def test_synthetic_path_stamps_the_name():
    from ra_scheduler.export import synthetic_path
    assert synthetic_path("filled.xlsx") == "filled_SYNTHETIC.xlsx"
    assert synthetic_path("out/fall_2026_final.xlsx") == "out/fall_2026_final_SYNTHETIC.xlsx"


def test_synthetic_path_is_idempotent():
    from ra_scheduler.export import synthetic_path
    once = synthetic_path("filled.xlsx")
    assert synthetic_path(once) == once
    assert synthetic_path("already_synthetic.xlsx") == "already_synthetic.xlsx"
    assert synthetic_path("MySynthetic.xlsx") == "MySynthetic.xlsx"  # case-insensitive
