# RA Scheduler — v1

Fills the Seventh College quarterly duty schedule from the duty grid plus availability
data. Implements `ra-scheduler-v1-spec.md` with all decisions locked 2026-08-24
(full quarter, 3 rule-blocks, minimax fairness, training floor, walk-pair rules).

New to the project? Start with
[documents/how-the-pipeline-works.md](documents/how-the-pipeline-works.md), a
plain-language walkthrough of every module.

## Run

```
pip install ortools openpyxl
python run_pipeline.py --grid <duty-schedule.xlsx> --out <filled.xlsx> [--seed N]
python run_pipeline.py ... --preflight-all     # every pre-solve finding, not the first 20
```

Same seed plus same inputs gives the same schedule; reruns are reproducible.

Availability is synthetic (`ra_scheduler/synthetic.py`) until the real form parser
lands. The parser replaces that one module and produces the same `AvailabilityData`,
so nothing downstream changes.

> **A run today uses invented people.** `run_pipeline.py` calls `synthetic.py`
> unconditionally, so it will happily produce a correct-looking schedule staffed by
> `R00`–`R42` on real dates. The only thing that says so is the `[avail] (synthetic)`
> line. Do not hand that output to anyone.

## Modules

| Module | Job |
|---|---|
| `ra_scheduler/models.py`    | all rule constants: tiers, block dates, staffing, targets |
| `ra_scheduler/grid.py`      | duty-grid xlsx -> shift instances (+ holiday rows) |
| `ra_scheduler/synthetic.py` | synthetic availability (stand-in for the form parser) |
| `ra_scheduler/preflight.py` | pre-solve arithmetic: says *why* a solve will fail, before it does |
| `ra_scheduler/solver.py`    | CP-SAT: picks who works each shift |
| `ra_scheduler/roles.py`     | slots people into named columns (walk pairs) |
| `ra_scheduler/validate.py`  | independent re-check of every rule (shares no solver code) |
| `ra_scheduler/export.py`    | writes the filled xlsx in the team's column shape |
| `tests/`                    | `python tests/test_roles.py`, `python tests/test_preflight.py` |

## The form parser (not built yet)

Decided 2026-08-24, so it doesn't get re-litigated:

- **Key on ucsd email, never on names.** Replaying last year, only 4 of 45 names
  matched exactly between the form and the schedule.
- **Blackout dates are `MM/DD` only**, read off the front of each comma-separated
  entry. Anything without a leading date is reported as unreadable, never guessed at.
- **Non-submitters stop the run and get listed.** Defaulting them to available or to
  unavailable both produce a plausible schedule built on someone the tool knows
  nothing about.
- **No NLP.** 43 hand-checked rows a quarter don't need it, and a regex that can't
  read something says so while a model returns a confident guess.

## Status (2026-08-24)

Proven end to end against the real grid with synthetic availability: `OPTIMAL`,
0 violations, max deviation 1 (LRA 5, returner 10-11, new 11-12), all new RAs at or
above the 2-shift training floor, 28 of 28 pairing-period evening shifts with mixed
walk pairs.

Every module is exercised against real input except availability. Remaining for real
data: the form parser and an `--availability` flag to point at it.

## Data

No real grid, availability export, or filled schedule belongs in this repo; they carry
real RA names. `.gitignore` blocks `*.xlsx`, `*.csv`, and `*.json` to make that hard
to do by accident.
