"""Tests for the form parser, on the shapes seen in the first 7 real responses.

No real data here: every string is invented to match a shape that was observed.

Run:  python tests/test_parse_form.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ra_scheduler.parse_form import (
    FLAG, READ, STOP, ParseReport, _is_conflict, _parse_location, _parse_weekend,
    _rank, parse_dates,
)
from ra_scheduler.models import FRONT_DESK, GAME_ROOM


# --------------------------------------------------------------------------- #
# dates: the field where the real responses diverged most from the instructions
# --------------------------------------------------------------------------- #

def test_dates_read_off_the_front_whatever_follows():
    found, bad = parse_dates("12/09 (Final)\n12/9(Final)\n12/9 - Final\n12/9", 2026)
    assert found == {date(2026, 12, 9)}
    assert bad == []


def test_dates_split_on_newlines_and_commas():
    """The form asks for one per line; half the early responses used commas."""
    found, _ = parse_dates("10/02 (a), 10/03 (b)\n10/09 (c)", 2026)
    assert found == {date(2026, 10, 2), date(2026, 10, 3), date(2026, 10, 9)}


def test_single_digit_month_and_day():
    """A fixed five-character chop reads '9/10(' and fails. Anchored regex does not."""
    found, _ = parse_dates("9/10 (thing)", 2026)
    assert found == {date(2026, 9, 10)}


def test_month_name_is_reported_not_guessed():
    found, bad = parse_dates("Oct. 17 (Concert)", 2026)
    assert found == set()
    assert bad == ["Oct. 17 (Concert)"]


def test_trivial_answers_are_not_unreadable():
    for text in ("N/A", "no", "None", ""):
        found, bad = parse_dates(text, 2026)
        assert found == set() and bad == [], text


def test_impossible_date_is_reported():
    found, bad = parse_dates("13/40 (typo)", 2026)
    assert found == set()
    assert bad == ["13/40 (typo)"]


# --------------------------------------------------------------------------- #
# the ranking grid: floats and a string share one column
# --------------------------------------------------------------------------- #

def test_rank_reads_float_int_and_string():
    assert _rank(1.0) == 1
    assert _rank(3) == 3
    assert _rank("2") == 2
    assert _rank(None) is None
    assert _rank("Class Conflict/Unavailable") is None


def test_conflict_matches_case_insensitively_on_prefix():
    assert _is_conflict("Class Conflict/Unavailable")
    assert _is_conflict("class conflict")
    assert not _is_conflict(2.0)
    assert not _is_conflict("")


# --------------------------------------------------------------------------- #
# the multi-select checkbox and the location radio
# --------------------------------------------------------------------------- #

def test_weekend_checkbox_splits_days_from_times():
    raw = ("[Sundays]  I have a preference for Sunday Weekend Duty Shifts, "
           "[Morning] If scheduled ... morning shifts, "
           "[Evening] If scheduled ... evening shifts")
    days, times = _parse_weekend(raw)
    assert days == {"Sunday"}
    assert times == {"Morning", "Evening"}


def test_weekend_open_means_no_day_preference():
    days, times = _parse_weekend("[Open] I am open ..., [Morning] If scheduled ...")
    assert days == set()
    assert times == {"Morning"}


def test_weekend_all_three_times_means_no_time_preference():
    _, times = _parse_weekend("[Morning] a, [Afternoon] b, [Evening] c")
    assert times == set()


def test_location_by_keyword():
    assert _parse_location("I would prefer to be scheduled for Duty Shifts at the Front Desk") == FRONT_DESK
    assert _parse_location("I would prefer to be scheduled for Duty Shifts in the Game Room") == GAME_ROOM
    assert _parse_location("I am open to being scheduled ... at either the Front Desk or Game Room") == ""
    assert _parse_location(None) == ""


# --------------------------------------------------------------------------- #
# the report
# --------------------------------------------------------------------------- #

def test_report_stops_only_on_stop():
    r = ParseReport()
    r.add(FLAG, "x", "a"); r.add(READ, "y", "b")
    assert not r.must_stop
    r.add(STOP, "z", "c")
    assert r.must_stop
    assert r.summary() == "1 stop, 1 flag, 1 to read"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all tests passed")
