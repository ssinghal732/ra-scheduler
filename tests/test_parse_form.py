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

def test_grouped_orders_stop_then_flag_then_read_and_names_kinds():
    r = ParseReport()
    r.add(READ, "zed", "weekday concerns: x")
    r.add(FLAG, "amy", "12 blackout dates (over 10)")
    r.add(STOP, "bob", "on the roster (new) but has not submitted the form")
    r.add(FLAG, "cal", "13 blackout dates (over 10)")
    g = r.grouped()
    assert [sev for sev, _, _ in g] == [STOP, FLAG, READ]
    assert g[1][1] == "more than 10 blackout dates" and len(g[1][2]) == 2
    assert [f.who for f in g[1][2]] == ["amy", "cal"]          # by name within a kind


def test_report_stops_only_on_stop():
    r = ParseReport()
    r.add(FLAG, "x", "a"); r.add(READ, "y", "b")
    assert not r.must_stop
    r.add(STOP, "z", "c")
    assert r.must_stop
    assert r.summary() == "1 stop, 1 flag, 1 to read"



# --------------------------------------------------------------------------- #
# the join: email, then full name, then unique first name, flagging each step
# --------------------------------------------------------------------------- #

def _fixture(tmpdir, roster_rows, form_rows):
    from openpyxl import Workbook
    ro = Workbook(); ws = ro.active
    ws.append(["Email", "Name", "Tier"])
    for r in roster_rows: ws.append(list(r))
    ro.save(f"{tmpdir}/roster.xlsx")
    fo = Workbook(); ws = fo.active
    Q = "Duty Weekdays ... [%s]"
    ws.append(["Timestamp", "Email Address", "RA Name", "What time do your weekdays end?",
               Q % "Monday", Q % "Tuesday", Q % "Wednesday", Q % "Thursday", Q % "Friday",
               "Please identify ALL of the Weekday DATES you CANNOT do.",
               "Any additional concerns related to Weekday Duty Scheduling",
               "Duty Preferences - Weekend Shift Time Preferences",
               "Please identify ALL of the DATES you CANNOT do. This includes weekdays AND weekends",
               "Any additional concerns related to Weekend Duty Scheduling",
               "Duty Preferences - Shift Location"])
    for r in form_rows: ws.append(list(r))
    fo.save(f"{tmpdir}/form.xlsx")
    return f"{tmpdir}/roster.xlsx", f"{tmpdir}/form.xlsx"


def _row(email, name):
    from datetime import datetime
    return (datetime(2026, 8, 26, 9), email, name, "free", 1.0, 2.0, 3.0, 4.0, 5.0,
            "N/A", "No", "[Open] x", "N/A", "no", "I am open ... either")


def _shifts():
    from ra_scheduler.models import ShiftInstance
    return [ShiftInstance(sid=0, date=date(2026, 10, 5), dow="Monday",
                          shift="Evening (Weekday)", time="", rounds="", week="1")]


def test_join_falls_back_to_full_name_without_a_finding():
    """Shivam 2026-11-25: a name match is not a finding any more, just a count."""
    import tempfile
    from ra_scheduler import parse_form
    ro, fo = _fixture(tempfile.mkdtemp(),
                      [("alias@ucsd.edu", "Pat Rivera", "New")],
                      [_row("privera@ucsd.edu", "Pat Rivera")])
    data, rep = parse_form.load(ro, fo, _shifts())
    assert "alias@ucsd.edu" in data.available, "should key on the ROSTER id after matching"
    assert not any("matched by" in f.message for f in rep.findings)
    assert "1 joined by name" in rep.matched["responses used"]
    assert not rep.must_stop


def test_join_falls_back_to_unique_first_name():
    import tempfile
    from ra_scheduler import parse_form
    ro, fo = _fixture(tempfile.mkdtemp(),
                      [("alias@ucsd.edu", "Pat Rivera", "New"), ("x@ucsd.edu", "Sam Lee", "New")],
                      [_row("privera@ucsd.edu", "Pat"), _row("x@ucsd.edu", "Sam Lee")])
    data, rep = parse_form.load(ro, fo, _shifts())
    assert "alias@ucsd.edu" in data.available
    assert not any("matched by" in f.message for f in rep.findings)
    assert not rep.must_stop


def test_join_stops_when_first_name_is_ambiguous():
    import tempfile
    from ra_scheduler import parse_form
    ro, fo = _fixture(tempfile.mkdtemp(),
                      [("a@ucsd.edu", "Pat Rivera", "New"), ("b@ucsd.edu", "Pat Chen", "New")],
                      [_row("other@ucsd.edu", "Pat"), _row("a@ucsd.edu", "Pat Rivera"), _row("b@ucsd.edu", "Pat Chen")])
    _, rep = parse_form.load(ro, fo, _shifts())
    assert rep.must_stop
    assert any("matches 2 roster entries" in f.message for f in rep.findings)


def test_join_stops_when_nothing_matches():
    import tempfile
    from ra_scheduler import parse_form
    ro, fo = _fixture(tempfile.mkdtemp(),
                      [("a@ucsd.edu", "Pat Rivera", "New")],
                      [_row("a@ucsd.edu", "Pat Rivera"), _row("ghost@ucsd.edu", "Nobody Here")])
    _, rep = parse_form.load(ro, fo, _shifts())
    assert rep.must_stop
    assert any("not on the roster by email, full name, or first name" in f.message for f in rep.findings)


def test_two_submissions_resolving_to_one_person_stops():
    import tempfile
    from ra_scheduler import parse_form
    ro, fo = _fixture(tempfile.mkdtemp(),
                      [("a@ucsd.edu", "Pat Rivera", "New")],
                      [_row("a@ucsd.edu", "Pat Rivera"), _row("alias@ucsd.edu", "Pat Rivera")])
    _, rep = parse_form.load(ro, fo, _shifts())
    assert rep.must_stop
    assert any("two different form submissions resolved" in f.message for f in rep.findings)


# --------------------------------------------------------------------------- #
# the Winter 2027 shape: six-slot weekend ranking grid, no weekday-dates box
# --------------------------------------------------------------------------- #

WINTER_HDR = (["Timestamp", "Email Address", "RA Name", "What time do your weekdays end?"]
              + ["Duty Weekdays: ... [%s]" % d for d in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")]
              + ["Any additional concerns related to Weekday Duty Scheduling"]
              + ["Duty Weekends: ... [%s]" % s for s in
                 ("Saturday Morning", "Saturday Afternoon", "Saturday Evening",
                  "Sunday Morning", "Sunday Afternoon", "Sunday Evening")]
              + ["If you have indicated you are unavailable ... Please also indicate any additional "
                 "concerns related to Weekend Duty Scheduling",
                 "Please identify ALL of the DATES you CANNOT do. This includes weekdays AND weekends",
                 "Duty Preferences - Shift Location", "Column 19"])

UNAVAIL = "Unavaliable (MUST EXPLAIN WHY)"      # the draft's spelling; the parser does not match the word


def _winter_fixture(tmpdir, form_rows, roster_rows=(("a@ucsd.edu", "Pat Rivera", "New"),)):
    from openpyxl import Workbook
    ro = Workbook(); ws = ro.active
    ws.append(["Email", "Name", "Tier"])
    for r in roster_rows: ws.append(list(r))
    ro.save(f"{tmpdir}/roster.xlsx")
    fo = Workbook(); ws = fo.active
    ws.append(WINTER_HDR)
    for r in form_rows: ws.append(list(r))
    fo.save(f"{tmpdir}/form.xlsx")
    return f"{tmpdir}/roster.xlsx", f"{tmpdir}/form.xlsx"


def _winter_row(weekday=(1.0, 2.0, 3.0, 4.0, 5.0), weekend=(1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
                email="a@ucsd.edu", name="Pat Rivera", dates="N/A"):
    from datetime import datetime
    return ((datetime(2026, 11, 23, 9), email, name, "free") + tuple(weekday) + ("no",)
            + tuple(weekend) + ("na", dates, "I am open ... either", None))


def _winter_shifts():
    from ra_scheduler.models import ShiftInstance
    mk = lambda i, d, dow, sh: ShiftInstance(sid=i, date=d, dow=dow, shift=sh, time="", rounds="", week="1")
    return [mk(0, date(2027, 1, 4), "Monday", "Evening (Weekday)"),
            mk(1, date(2027, 1, 9), "Saturday", "Morning"),
            mk(2, date(2027, 1, 9), "Saturday", "Afternoon"),
            mk(3, date(2027, 1, 9), "Saturday", "Evening (Weekend)"),
            mk(4, date(2027, 1, 10), "Sunday", "Morning"),
            mk(5, date(2027, 1, 10), "Sunday", "Afternoon"),
            mk(6, date(2027, 1, 10), "Sunday", "Evening (Weekend)")]


def test_winter_grid_is_read_into_weekend_ranks_and_dates_box_is_optional():
    import tempfile
    from ra_scheduler import parse_form
    with tempfile.TemporaryDirectory() as td:
        ro, fo = _winter_fixture(td, [_winter_row(weekend=(2.0, 1.0, 6.0, 3.0, 4.0, 5.0), dates="1/9 (trip)")])
        data, rep = parse_form.load(ro, fo, _winter_shifts())
    assert not rep.must_stop, [str(f) for f in rep.findings]
    assert rep.matched["weekday_dates"] == "(absent, optional)"
    assert rep.matched["weekend_pref"] == "(absent, optional)"
    assert "6 columns" in rep.matched["weekend ranks"]
    p = data.prefs("a@ucsd.edu")
    assert p.weekend_rank == {"Saturday Morning": 2, "Saturday Afternoon": 1, "Saturday Evening": 6,
                              "Sunday Morning": 3, "Sunday Afternoon": 4, "Sunday Evening": 5}
    assert p.weekend_days == set() and p.weekend_times == set()
    assert date(2027, 1, 9) in data.blackout_dates["a@ucsd.edu"]       # the one remaining dates box still counts
    assert len(data.available["a@ucsd.edu"]) == 4                        # 7 shifts minus the 3 on Jan 9


def test_winter_unavailable_slot_leaves_availability_and_flags_for_proof():
    import tempfile
    from ra_scheduler import parse_form
    with tempfile.TemporaryDirectory() as td:
        ro, fo = _winter_fixture(td, [_winter_row(weekend=(1.0, 2.0, UNAVAIL, 3.0, 4.0, "unavailable"))])
        data, rep = parse_form.load(ro, fo, _winter_shifts())
    assert not rep.must_stop, [str(f) for f in rep.findings]
    ok = data.available["a@ucsd.edu"]
    assert len(ok) == 5
    assert not any("Saturday" in k and "Evening" in k for k in ok)
    assert not any("Sunday" in k and "Evening" in k for k in ok)
    flags = [f for f in rep.findings if f.severity == FLAG and "proof required" in f.message]
    assert len(flags) == 1 and "Saturday Evening, Sunday Evening" in flags[0].message
    assert data.prefs("a@ucsd.edu").weekend_rank == {"Saturday Morning": 1, "Saturday Afternoon": 2,
                                                     "Sunday Morning": 3, "Sunday Afternoon": 4}


def test_winter_all_six_unavailable_stops():
    import tempfile
    from ra_scheduler import parse_form
    with tempfile.TemporaryDirectory() as td:
        ro, fo = _winter_fixture(td, [_winter_row(weekend=(UNAVAIL,) * 6)])
        _, rep = parse_form.load(ro, fo, _winter_shifts())
    assert rep.must_stop
    assert any("ALL SIX weekend" in f.message for f in rep.findings)


def test_duplicate_rank_stops_in_either_grid():
    import tempfile
    from ra_scheduler import parse_form
    with tempfile.TemporaryDirectory() as td:
        ro, fo = _winter_fixture(td, [_winter_row(weekday=(1.0, 2.0, 3.0, 4.0, 4.0))])
        _, rep = parse_form.load(ro, fo, _winter_shifts())
    assert rep.must_stop
    assert any("weekday rank(s) [4] used more than once" in f.message for f in rep.findings)
    with tempfile.TemporaryDirectory() as td:
        ro, fo = _winter_fixture(td, [_winter_row(weekend=(1.0, 1.0, 3.0, 4.0, 5.0, 6.0))])
        _, rep = parse_form.load(ro, fo, _winter_shifts())
    assert rep.must_stop
    assert any("weekend rank(s) [1] used more than once" in f.message for f in rep.findings)


def test_winter_blank_grid_cell_is_flagged_not_unavailable():
    import tempfile
    from ra_scheduler import parse_form
    with tempfile.TemporaryDirectory() as td:
        ro, fo = _winter_fixture(td, [_winter_row(weekend=(1.0, 2.0, 3.0, 4.0, 5.0, None))])
        data, rep = parse_form.load(ro, fo, _winter_shifts())
    assert not rep.must_stop
    assert any("Sunday Evening: not answered" in f.message for f in rep.findings)
    assert len(data.available["a@ucsd.edu"]) == 7


def test_fall_checkbox_shape_still_parses():
    """Fall data must stay replayable for tuning."""
    import tempfile
    from ra_scheduler import parse_form
    with tempfile.TemporaryDirectory() as td:
        ro, fo = _fixture(td, [("a@ucsd.edu", "Pat Rivera", "New")], [_row("a@ucsd.edu", "Pat Rivera")])
        data, rep = parse_form.load(ro, fo, _shifts())
    assert not rep.must_stop
    assert "weekend ranks" not in rep.matched
    assert data.prefs("a@ucsd.edu").weekend_rank == {}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all tests passed")
