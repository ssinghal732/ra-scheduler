# RA Scheduler

Builds the quarterly duty schedule for the Resident Assistants of Seventh College, UC San Diego. Each quarter about 43 RAs cover roughly 120 to 150 duty shifts, 2 to 4 people per shift, around 400 seats in all. Two or three RAs used to fill that grid by hand over about eight hours, juggling class conflicts, blackout dates, a returners-only opening week, a training period where every shift pairs an experienced RA with a new one, and the expectation that everyone ends up with a fair share. This tool does the assignment step in under a minute, honours every one of those rules, and writes the result back in the exact spreadsheet shape the duty leads already use.

Written by Shivam Singhal, an RA at Seventh College, for the duty leads who run the schedule. First real schedule shipped Fall 2026. Winter 2027 is the second quarter.

---

## For the people running it

You need three things from the duty leads' Google Drive, downloaded as `.xlsx`:

| File | What it is |
|---|---|
| The duty schedule workbook | The leads' grid: one row per shift with Week, Date, Day of the Week, Shift, Time, four name columns, Duty Round Location. The form responses live in another tab of the same workbook. |
| The roster | Three columns, `Email`, `Name`, `Tier`, where tier is LRA, Returner, or New. |
| The availability form responses | The Google Form's response sheet. Usually a tab in the workbook above. |

### Once per quarter: fill in `quarter.toml`

This is the only file you edit. It sits at the top of the repo and is mostly comments. You tell it the quarter's name, the two tab names, whether there is a returners-only week and a training period (and their last dates), and any dates the leads will staff themselves, like the first weekend back from a break.

```toml
quarter = "Winter 2027"
grid_sheet = "Winter Template"
form_sheet = "Winter Availability"

# returners_only_through = 2026-09-13      # delete or comment out = none this quarter
# pairing_through = 2026-10-18

[[leads_fill]]
dates = [2027-01-02, 2027-01-03]
label = "Volunteers"
```

Dates are written plain, no quotes. If something in the file is wrong, the run stops and the message says what to fix.

### Run it

```
pip install -r requirements.txt      # Python 3.11 or newer

python run_pipeline.py --grid "26-27 RA Duty Schedule.xlsx" \
                       --roster "RA Roster - Tiered.xlsx" \
                       --availability "26-27 RA Duty Schedule.xlsx" \
                       --out winter_2027.xlsx
```

The run prints what it read and what it found before it solves anything. Three kinds of findings:

- **STOP.** The run will not solve until this is fixed. Someone on the roster hasn't submitted the form. Someone ranked the same number twice. Someone marked every weekday as a class conflict. There is no override, on purpose: a schedule built on a guess about someone's availability looks exactly like a correct one.
- **FLAG.** Printed and the run continues. More than ten blackout dates, a date the parser couldn't read, a weekend slot marked unavailable (so the leads can ask for proof).
- **READ.** The free-text "concerns" boxes, printed per person. A human reads every one. The tool never interprets them.

If there's nothing to stop on, you get an `.xlsx` with the schedule in the leads' column layout, holiday and volunteer rows kept in place, an Exceptions column listing who's blacked out each day, and a second tab showing every RA's availability and preferences next to what they got, so a question like "why is this person on Friday" can be answered without rerunning anything.

A dry run with invented people needs only the grid: leave off `--roster` and `--availability`. The output file is forced to carry `SYNTHETIC` in its name so it can't be mistaken for a real schedule.

### What the solver promises

Hard rules, never broken:

- Nobody is scheduled on a date they blacked out or a weekday they have class.
- Every shift gets exactly the people it needs.
- No back-to-back weekend shifts for one person on the same day.
- Returners-only week: no new RAs. Training period: every 4-person shift is 2 experienced and 2 new, on both walks and both desks.

Soft goals, in this order of priority:

1. Everyone's shift count lands on their tier's target, and the worst-off person is protected first.
2. Each person's weekday/weekend mix matches the grid's own ratio.
3. Every new RA gets at least two shifts in the training period.
4. At most one shift per person per week, so nobody is done by week four while someone else works only the last three.
5. Preferences, as a strict tiebreaker under all of the above: the ranked weekday, the ranked weekend slot, and within that the worst-off person's misses are spread before the total is minimized.

Preferences can never buy a lighter load. The solver's math is arranged so that one unit of unfairness outweighs every preference in the quarter combined, so this holds by construction rather than by weighting.

---

## For anyone reading the code

Python, two dependencies: Google's OR-Tools CP-SAT solver and openpyxl. No pandas, no database, no web server. About 3,000 lines including tests.

### The pipeline

| Stage | Module | Job |
|---|---|---|
| Settings | `quarter.py` | Reads `quarter.toml`, validates it, hands the dates to the rulebook. |
| Rulebook | `models.py` | Every rule constant in one place: tiers, block logic, staffing shapes, target derivation, preference cost curves. |
| Grid | `grid.py` | Duty workbook to shift instances. Holiday rows and leads-fill rows are set aside for the export. |
| Form | `parse_form.py` | Form export plus roster to availability and preferences, with the STOP / FLAG / READ report. |
| Preflight | `preflight.py` | Counting arguments that turn a bare "infeasible" into a dated list of what's short, before the solver runs. |
| Solve | `solver.py` | CP-SAT: one boolean per (person, shift), the hard rules as constraints, the soft goals as a weighted objective. |
| Roles | `roles.py` | Slots the chosen people into the four named columns, honouring training pairs and desk preference. |
| Validate | `validate.py` | Re-checks every hard rule and role invariant. Shares no code with the solver, so a bug in one can't hide in the other. |
| Export | `export.py` | Writes the workbook back in the leads' shape. |
| Driver | `run_pipeline.py` | Runs the stages in order and prints the report. |

### Decisions that shaped it

**Fairness over preferences, strictly.** The objective is lexicographic in effect: a scaling factor derived from the grid (the worst possible total preference cost plus one) multiplies the fairness terms, so no combination of preference wins can offset one extra shift on one person. Then, among equally fair schedules, the solver minimizes the single worst person's preference misses before it minimizes the total. On Fall data that moved first-choice weekday seats from 49% to 72% without moving a single shift count, and cut people with zero first-choice shifts from 10 to 5.

**Targets are derived each run.** The seat count and roster set the per-tier loads each run (new = B, returner = B - 1, LRA = B / 2, picking the B closest to the seat count). A changed grid can't quietly invalidate the numbers.

**Soft goals, not hard caps, for anything that isn't availability.** A hard cap can declare a whole quarter impossible over one extra shift. Availability is the only thing the solver will not bend.

**The parser refuses, loudly, instead of guessing.** It handles every input shape that has been seen in real responses (`12/9 (Final)`, `12/09(Final)`, comma-joined dates) and reports everything else as unreadable for a human. No NLP, no language model. For a hard constraint, a flagged unreadable date beats a confident wrong one. Forty-three rows a quarter don't need a model.

**Validator and solver share nothing.** The validator reads the finished schedule and re-derives every rule from the raw inputs. When the two disagree, one of them has a bug, and you can tell which.

**Rules in code, dates in a settings file.** The returners-only and training rules live in `models.py`; which dates they apply to this quarter live in `quarter.toml`. Fall 2026 had both blocks. Winter 2027 has neither, and the solver knows that from two commented-out lines rather than from dates that happen to have passed.

### Results

Fall 2026, the first real run, 43 RAs, 440 seats across 136 shifts:

| | |
|---|---|
| Solve | OPTIMAL, 0 rule violations |
| Loads | every LRA at 5, returners and new RAs at 10 or 11, max deviation 1 |
| Weekday/weekend mix | 40 of 43 on their ideal split |
| Spread | busiest week for anyone: 3 shifts, 11 person-weeks over one |
| Training | 28 of 28 pairing-period shifts mixed on both walks and both desks |
| Preferences | 88% of weekday shifts on a 1st or 2nd choice day |

That 88% is the ceiling the real rankings allow. Tuesday was wanted nearly two to one and Friday by three people for 48 seats. The gap drove the preference changes now live for Winter 2027.

Every rule above was verified by reading rows out of the generated file, not by trusting the validator or a test the author also wrote.

### Tests

```
python tests/test_parse_form.py
python tests/test_preferences.py
python tests/test_preflight.py
python tests/test_quarter.py
python tests/test_roles.py
```

Each file runs on its own. The first test in `test_preferences.py` guards the fairness-over-preferences property; if it ever fails, the tool has started trading someone's fair share for someone else's convenience.

### More reading

- [documents/how-the-pipeline-works.md](documents/how-the-pipeline-works.md): a plain-language walkthrough of every module, written for a reader who has never seen a constraint solver.
- [documents/measured-facts.md](documents/measured-facts.md): every measurement behind the design decisions, including the A/B tests on the objective.
- [CLAUDE.md](CLAUDE.md): the standing decisions and why each was made, in a table. Reopen one at your peril.
- `documents/*.html`: the product vision, technical design, and design brief written for the duty leads.

---

## Data

No real grid, roster, form export, or finished schedule belongs in this repo. They carry real students' names. `.gitignore` blocks `*.xlsx`, `*.csv`, and `*.json` so it can't happen by accident, and the people involved are referred to by role in every tracked file.
