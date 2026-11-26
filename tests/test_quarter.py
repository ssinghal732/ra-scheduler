"""Tests for quarter.toml parsing. No disk, no ortools.

Run:  python tests/test_quarter.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ra_scheduler.quarter import DEFAULT_PATH, QuarterError, load_quarter, parse_quarter

GOOD = '''
quarter = "Fall 2026"
grid_sheet = "Fall Duty Schedule"
form_sheet = "Fall Availability"
returners_only_through = 2026-09-13
pairing_through = 2026-10-18
[[leads_fill]]
dates = [2026-11-28, 2026-11-29]
label = "Volunteers"
'''


def _fails(text, needle):
    try:
        parse_quarter(text)
    except QuarterError as e:
        assert needle in str(e), f"wanted {needle!r} in {e}"
        return
    raise AssertionError(f"expected a QuarterError mentioning {needle!r}")


def test_full_file_parses():
    q = parse_quarter(GOOD)
    assert q.name == "Fall 2026"
    assert q.returners_only_through == date(2026, 9, 13)
    assert q.pairing_through == date(2026, 10, 18)
    assert q.leads_fill == {date(2026, 11, 28): "Volunteers", date(2026, 11, 29): "Volunteers"}


def test_missing_dates_mean_no_such_block():
    q = parse_quarter('quarter = "W"\ngrid_sheet = "g"\nform_sheet = "f"\n')
    assert q.returners_only_through is None and q.pairing_through is None
    assert q.leads_fill == {}
    assert "no returners-only week" in q.describe() and "no pairing period" in q.describe()


def test_quoted_date_is_refused_with_a_plain_message():
    _fails('quarter = "W"\ngrid_sheet = "g"\nform_sheet = "f"\npairing_through = "2026-10-18"\n',
           "plain date like 2026-09-13 (no quotes)")


def test_unknown_key_is_refused():
    _fails('quarter = "W"\ngrid_sheet = "g"\nform_sheet = "f"\nreturner_weeks = 1\n',
           "does not know: ['returner_weeks']")


def test_pairing_before_returners_only_is_refused():
    _fails('quarter = "W"\ngrid_sheet = "g"\nform_sheet = "f"\n'
           'returners_only_through = 2026-10-18\npairing_through = 2026-09-13\n',
           "is before returners_only_through")


def test_leads_fill_needs_label_and_dates():
    _fails('quarter = "W"\ngrid_sheet = "g"\nform_sheet = "f"\n[[leads_fill]]\ndates = [2027-01-02]\n',
           "needs label")
    _fails('quarter = "W"\ngrid_sheet = "g"\nform_sheet = "f"\n[[leads_fill]]\nlabel = "V"\ndates = []\n',
           "needs dates")


def test_same_date_in_two_blocks_is_refused():
    _fails('quarter = "W"\ngrid_sheet = "g"\nform_sheet = "f"\n'
           '[[leads_fill]]\ndates = [2027-01-02]\nlabel = "A"\n'
           '[[leads_fill]]\ndates = [2027-01-02]\nlabel = "B"\n',
           "more than one leads_fill block")


def test_the_repo_quarter_file_loads():
    q = load_quarter(DEFAULT_PATH)
    assert q.name and q.grid_sheet and q.form_sheet


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all tests passed")
