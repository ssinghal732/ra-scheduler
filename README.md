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

The parser prints which column it matched to each field, then a findings report
grouped by severity and kind, people named not emailed. **STOP** findings halt the run
(someone on the roster has not submitted, or marked all five weekdays as conflicts;
there is deliberately no override). **FLAG** findings print and continue, most
actionable kind first. **READ** findings are the free-text concerns boxes, printed per
person and wrapped, for a human to read before solving.

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

- **Join on email, then exact full name, then a first name matching exactly one
  roster entry.** Every fallback is flagged; if all fail the run stops. People turned
  out to have more than one ucsd.edu address, so email alone was not enough. Name
  matching is exact after trimming, never fuzzy.
- **A blackout date is `M/D` or `MM/DD` read off the front of each entry**, entries
  split on newlines and commas. Anything with no leading date is reported, never
  guessed at.
- **Both "dates you cannot do" boxes are unioned.** They disagree for some people.
- **Duplicate submissions: latest timestamp wins**, flagged.
- **A roster member who has not submitted stops the run.** So does anyone who marked
  all five weekdays as class conflicts.
- **No NLP, no LLM.** The parser handles every input shape that has been observed and
  flags everything else for a human. A flagged unreadable date beats a confident
  wrong one, and 43 rows a quarter do not need a model.

## Status (2026-08-28)

The first real schedule is built. All 43 responses parsed with 0 stops; preflight
clean; `OPTIMAL`; 0 violations; every lead RA at 5, returners and new RAs at 10 or 11;
40 of 43 on their ideal weekday/weekend split; 88% of weekday shifts on a first or
second choice day, which is the ceiling the real rankings allow (Tuesday was wanted
nearly two to one). Rules verified by reading the output file, not by trusting the
validator.

Three product documents are in `documents/`: a vision doc for the duty leads, a
technical design, and a design brief. The v2 direction is being reconsidered in favour
of Google Sheets integration over a hosted website.

## Data

No real grid, availability export, or filled schedule belongs in this repo; they carry
real RA names. `.gitignore` blocks `*.xlsx`, `*.csv`, and `*.json` to make that hard
to do by accident.
