# RA Scheduler — v1 code

Fills the Seventh College quarterly duty schedule from the duty grid + availability
data. Implements `../ra-scheduler-v1-spec.md` with all decisions locked 2026-08-24
(full quarter, 3 rule-blocks, minimax fairness, training floor, walk-pair rules).

## Run

```
pip install ortools openpyxl
python run_pipeline.py --grid <duty-schedule.xlsx> --out <filled.xlsx> [--seed N]
```

Availability is synthetic (`ra_scheduler/synthetic.py`) until the real form parser
lands; the parser replaces that one module and produces the same `AvailabilityData`.

## Modules

| Module | Job |
|---|---|
| `ra_scheduler/models.py`   | all rule constants: tiers, block dates, staffing, targets |
| `ra_scheduler/grid.py`     | duty-grid xlsx -> shift instances (+ holiday rows) |
| `ra_scheduler/synthetic.py`| synthetic availability (stand-in for the form parser) |
| `ra_scheduler/solver.py`   | CP-SAT: picks who works each shift |
| `ra_scheduler/roles.py`    | slots people into named columns (walk pairs) |
| `ra_scheduler/validate.py` | independent re-check of every rule (shares no solver code) |
| `ra_scheduler/export.py`   | writes the filled xlsx in the team's column shape |
| `tests/`                   | unit tests: `python tests/test_roles.py` |

## Status (2026-08-24)

Proven end-to-end on synthetic availability with the real grid: OPTIMAL,
0 violations, max deviation 1 (LRA 5, returner 10-11, new 11-12), all new RAs
>= 2 pairing-period shifts. Remaining for real data (Aug 27): form-export parser.
