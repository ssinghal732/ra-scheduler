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

# the real thing
python run_pipeline.py --grid <duty-schedule.xlsx> \
                       --roster <roster.xlsx> \
                       --availability <form-export.xlsx> --sheet "Fall Availability" \
                       --out <filled.xlsx>

# a dry run with invented people; the output is forced to carry SYNTHETIC in its name
python run_pipeline.py --grid <duty-schedule.xlsx> --out <filled.xlsx>

python run_pipeline.py ... --preflight-all     # every pre-solve finding, not the first 20
python run_pipeline.py ... --seed N            # role-slotting seed; same inputs + seed = same schedule
```

The roster is a three-column sheet, `Email | Name | Tier`, with tier one of LRA /
Returner / New. The form export is the Google Forms response sheet downloaded as xlsx.

The parser prints which column it matched to each field, then a findings report.
**STOP** findings halt the run (someone on the roster has not submitted, or marked all
five weekdays as conflicts). **FLAG** findings print and continue. **READ** findings
are the free-text concerns boxes, printed in full for a human to read before solving.

## Modules

| Module | Job |
|---|---|
| `ra_scheduler/models.py`    | all rule constants: tiers, block dates, staffing, targets |
| `ra_scheduler/grid.py`      | duty-grid xlsx -> shift instances (+ holiday rows) |
| `ra_scheduler/parse_form.py` | Google Form export + roster -> `AvailabilityData`, with a findings report |
| `ra_scheduler/synthetic.py` | invented availability and preferences, used when `--availability` is omitted |
| `ra_scheduler/preflight.py` | pre-solve arithmetic: says *why* a solve will fail, before it does |
| `ra_scheduler/solver.py`    | CP-SAT: picks who works each shift |
| `ra_scheduler/roles.py`     | slots people into named columns (walk pairs) |
| `ra_scheduler/validate.py`  | independent re-check of every rule (shares no solver code) |
| `ra_scheduler/export.py`    | writes the filled xlsx in the team's column shape |
| `tests/`                    | four suites, each runnable directly: `python tests/test_<name>.py` |

## Decisions encoded in the parser

- **Key on ucsd email, never on names.** Replaying last year, only 4 of 45 names
  matched exactly between the form and the schedule.
- **A blackout date is `M/D` or `MM/DD` read off the front of each entry**, entries
  split on newlines and commas. Anything with no leading date is reported, never
  guessed at.
- **Both "dates you cannot do" boxes are unioned.** They disagree for some people.
- **Duplicate submissions: latest timestamp wins**, flagged.
- **A roster member who has not submitted stops the run.** So does anyone who marked
  all five weekdays as class conflicts.
- **No NLP.** 43 rows a quarter, pre-checked by a human. A regex that fails says so.

## Status (2026-08-26)

Every module is built and tested. The solver honours fairness first (total shifts,
then weekday/weekend mix), then all four preferences the form collects (weekday
rank, weekend day, weekend time, desk), then randomises what is left. On the real
grid with synthetic availability: `OPTIMAL`, 0 violations, max deviation 1, 38 of 43
RAs on their ideal weekday/weekend mix, 99% of weekday shifts on a first or second
choice day.

The parser has been run on the first 7 real responses: every column matched, every
availability key it produced matches a real shift. The real run happens once the form
closes and everyone has submitted.

## Data

No real grid, availability export, or filled schedule belongs in this repo; they carry
real RA names. `.gitignore` blocks `*.xlsx`, `*.csv`, and `*.json` to make that hard
to do by accident.
