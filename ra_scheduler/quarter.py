"""The per-quarter settings file, quarter.toml, read once at startup.

Everything that changes from quarter to quarter and is not in the grid or the
form lives there: the tab names, the two rule-block end dates, and the dates
the duty leads staff themselves. It is the file an operator edits; nothing
else in the repo should need touching between quarters.

models.py takes its block dates and leads-fill dates from here, so every rule
still has one home: the rule lives in models.py, the date it applies to lives
in quarter.toml.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "quarter.toml"

KNOWN_KEYS = {"quarter", "grid_sheet", "form_sheet", "returners_only_through",
              "pairing_through", "leads_fill"}


class QuarterError(ValueError):
    """quarter.toml could not be read. The message says what to fix."""


@dataclass(frozen=True)
class Quarter:
    name: str
    grid_sheet: str
    form_sheet: str
    returners_only_through: date | None = None
    pairing_through: date | None = None
    leads_fill: dict[date, str] = field(default_factory=dict)   # date -> label

    def describe(self) -> str:
        """One line for the run log."""
        parts = [f"{self.name}: grid tab {self.grid_sheet!r}, form tab {self.form_sheet!r}"]
        parts.append(f"returners-only through {self.returners_only_through}"
                     if self.returners_only_through else "no returners-only week")
        parts.append(f"pairing through {self.pairing_through}"
                     if self.pairing_through else "no pairing period")
        if self.leads_fill:
            parts.append(f"{len(self.leads_fill)} leads-fill date(s)")
        return "; ".join(parts)


def _date_or_none(raw: dict, key: str) -> date | None:
    v = raw.get(key)
    if v is None:
        return None
    if isinstance(v, date):
        return v
    raise QuarterError(f"{key} must be a plain date like 2026-09-13 (no quotes), got {v!r}")


def parse_quarter(text: str) -> Quarter:
    """Parse the file's text. Separate from the file read so tests need no disk."""
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise QuarterError(f"quarter.toml does not parse: {e}") from e

    unknown = sorted(set(raw) - KNOWN_KEYS)
    if unknown:
        raise QuarterError(f"quarter.toml has keys the scheduler does not know: {unknown}. "
                           f"Known: {sorted(KNOWN_KEYS)}")
    for key in ("quarter", "grid_sheet", "form_sheet"):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise QuarterError(f"quarter.toml needs {key} = \"...\" (a non-empty name in quotes)")

    ro = _date_or_none(raw, "returners_only_through")
    pe = _date_or_none(raw, "pairing_through")
    if ro and pe and pe < ro:
        raise QuarterError(f"pairing_through ({pe}) is before returners_only_through ({ro}); "
                           f"the pairing period follows the returners-only week")

    fill: dict[date, str] = {}
    for i, block in enumerate(raw.get("leads_fill", []), 1):
        if not isinstance(block, dict):
            raise QuarterError(f"leads_fill #{i} should be a [[leads_fill]] block with dates and label")
        label = block.get("label")
        dates = block.get("dates")
        if not isinstance(label, str) or not label.strip():
            raise QuarterError(f"leads_fill #{i} needs label = \"...\"")
        if not isinstance(dates, list) or not dates or not all(isinstance(d, date) for d in dates):
            raise QuarterError(f"leads_fill #{i} ({label}) needs dates = [2027-01-02, ...], plain dates")
        for d in dates:
            if d in fill:
                raise QuarterError(f"{d} appears in more than one leads_fill block")
            fill[d] = label.strip()

    return Quarter(name=raw["quarter"].strip(), grid_sheet=raw["grid_sheet"].strip(),
                   form_sheet=raw["form_sheet"].strip(), returners_only_through=ro,
                   pairing_through=pe, leads_fill=fill)


def load_quarter(path: Path | str = DEFAULT_PATH) -> Quarter:
    p = Path(path)
    if not p.exists():
        raise QuarterError(f"no quarter file at {p}. Copy quarter.toml from the repo and fill it in.")
    return parse_quarter(p.read_text())


QUARTER = load_quarter()
