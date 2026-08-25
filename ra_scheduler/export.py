"""Write the filled schedule to xlsx in the team's exact column shape.

Matches the grid the duty leads already use: same headers, holiday rows kept in
place, week label written once per week, Exceptions listing date-blackout RAs.
Values only (no formulas), Arial throughout.
"""
from __future__ import annotations

from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .models import RA, AvailabilityData, ShiftInstance
from .grid import HolidayRow
from .roles import FD_P, FD_S, GR_P, GR_S

HEADERS = (
    "Week", "Date", "Day of the Week", "Shift", "Time",
    "Front Desk Primary", "Front Desk Secondary",
    "Game Room Primary", "Game Room Secondary",
    "Duty Round Location", "Exceptions",
)
_SHIFT_ORDER = {"Evening (Weekday)": 0, "Morning": 0, "Afternoon": 1, "Evening (Weekend)": 2}


def _exceptions_by_date(data: AvailabilityData) -> dict[date, str]:
    name_of = {ra.ra_id: ra.name for ra in data.roster}
    out: dict[date, list[str]] = {}
    for rid, days in data.blackout_dates.items():
        for d in days:
            out.setdefault(d, []).append(name_of[rid])
    return {d: ", ".join(sorted(names)) for d, names in out.items()}


def write_schedule(
    path: str,
    shifts: list[ShiftInstance],
    holidays: list[HolidayRow],
    roles: dict[int, dict[str, str]],
    data: AvailabilityData,
    sheet_name: str = "Fall Duty Schedule",
) -> None:
    name_of = {ra.ra_id: ra.name for ra in data.roster}
    exceptions = _exceptions_by_date(data)

    # interleave duty rows and holiday rows in calendar order
    rows: list[tuple] = []
    for s in shifts:
        t = roles[s.sid]
        rows.append((s.date, _SHIFT_ORDER[s.shift], s.week, s.dow, s.shift, s.time,
                     name_of[t[FD_P]], name_of[t[FD_S]],
                     name_of.get(t.get(GR_P, ""), ""), name_of.get(t.get(GR_S, ""), ""),
                     s.rounds))
    for h in holidays:
        rows.append((h.date, _SHIFT_ORDER[h.shift], h.week, h.dow, h.shift, h.time,
                     "Holiday", "Holiday",
                     "Holiday" if h.shift.startswith("Evening") else "",
                     "Holiday" if h.shift.startswith("Evening") else "",
                     h.rounds))
    rows.sort(key=lambda r: (r[0], r[1]))

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name

    header_font = Font(name="Arial", bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F4E79")
    body_font = Font(name="Arial")
    holiday_fill = PatternFill("solid", fgColor="FCE4D6")

    ws.append(HEADERS)
    for c in ws[1]:
        c.font, c.fill = header_font, header_fill
        c.alignment = Alignment(horizontal="center")

    prev_week, prev_date = None, None
    for (d, _, week, dow, shift, time, fdp, fds, grp, grs, rounds) in rows:
        ws.append((
            week if week != prev_week else "",
            d, dow, shift, time, fdp, fds, grp, grs, rounds,
            exceptions.get(d, "") if d != prev_date else "",  # once per date
        ))
        for c in ws[ws.max_row]:
            c.font = body_font
        ws.cell(ws.max_row, 2).number_format = "MM/DD/YYYY"
        if fdp == "Holiday":
            for c in ws[ws.max_row]:
                c.fill = holiday_fill
        prev_week, prev_date = week, d

    for col_cells, width in zip(ws.columns, (6, 12, 14, 18, 11, 17, 17, 17, 17, 26, 40)):
        ws.column_dimensions[col_cells[0].column_letter].width = width
    ws.freeze_panes = "A2"
    wb.save(path)
