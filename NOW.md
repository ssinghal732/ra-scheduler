# NOW

## What this is

RA Scheduler: fills the Seventh College quarterly duty schedule (440 seats, 136 shifts, 43 RAs) from the duty leads' grid plus the availability form, honoring the returners-only week, four weeks of experienced+new walk pairs, and per-tier loads. Spec at `../ra-scheduler-v1-spec.md`. Project brief in [CLAUDE.md](CLAUDE.md).

Built end to end and proven on synthetic availability in one day, 2026-08-24. Form closes 2026-08-27 at 11:59 pm, so a complete response set exists 2026-08-28.

## Active

**The whole v1 pipeline works (2026-08-24).** Grid reader, solver, role slotting, independent validator, xlsx exporter, CLI, 17 unit tests. On the real grid with synthetic availability: OPTIMAL in under 60s, 0 violations, max deviation 1 (LRA all 5, returners 10-11, new 11-12), every new RA at or above the 2-shift training floor, all 28 pairing-period evening shifts with mixed walk pairs. Committed to AICC as `6f792fc`.

**One rule was corrected mid-build (2026-08-24).** Primary/Secondary means first walk / second walk, not seniority. Claude had invented "experienced must be Primary" on 2-person shifts; Shivam corrected it, the label order is now randomized, and the wrong reading is scrubbed from code, docstrings, and tests.

**The code has its own repo now (2026-08-24).** `ssinghal732/ra-scheduler`, private, commit `28959ca`, 15 files. Operator docs and data files are held out two different ways: these three docs through `.git/info/exclude` so their names never appear on GitHub, and `*.xlsx` / `*.csv` / `*.json` through `.gitignore` so a real grid or a filled schedule can't slip into a commit.

**Full pipeline verified against the REAL grid (2026-08-24).** `ortools` 9.15.6755 and `openpyxl` 3.1.5 installed into `(base)`. `grid.py` reads `~/Downloads/26-27 RA Duty Schedule.xlsx` with no errors and every documented number matches: 138 shifts, 448 seats, 4 holiday rows, 86 duty dates, blocks at 6/32, 28/144, 52/272, holidays Nov 11/17/26/27. Full run on it: OPTIMAL in under 30s, 0 violations, max deviation 1, LRA all 5. Rules checked by reading rows back out of the output rather than trusting the validator: 0 new RAs in the returners-only week, 28 of 28 pairing-period evening shifts with both walk pairs mixed, all 4 holiday rows preserved. Every module is now exercised against real input except availability.

**Pairing-period training rule corrected (2026-08-26).** Only the walk pairs had been constrained to 1 experienced + 1 new. Shivam asked whether the desk pairs were checked too; they were not, and 10 of 28 pairing shifts had two new RAs staffing a desk together for the whole evening. Both the walk and the desk shift are training, so all four pairings are now mixed, verified independently in `validate.py`. 56 of 56 on both.

**The parser is built and verified on real data (2026-08-26, `ccbbf80`).** `parse_form.py` reads the Google Form export and the roster into the same `AvailabilityData` that `synthetic.py` produces. Built against the first 7 real responses: every column matched, 5 of 7 joined to the roster, every availability key it produced matches a real shift. Three-tier findings: STOP halts before the solver (roster member with no submission, all five weekdays conflicted, missing column), FLAG prints and continues (duplicates, >10 blackouts, unreadable dates, off-roster respondent, repeated ranks), READ prints every non-trivial concerns box. Wired in as `--roster` and `--availability`; omit both and the run stays synthetic and stamped.

**The grid changed (2026-08-26).** The leads' current file drops the Sept 8 and 9 evenings: now 136 shifts / 440 seats, starting Sept 10. Returners-only block is 4 dates / 24 seats. Targets and the weekday share re-derive automatically. Always run against their latest file.

**Weekday/weekend balance shipped (2026-08-26).** Reverses the old "total shift count only" decision at Shivam's call. Each RA's mix is pulled toward the grid's own 53.6% weekday share: LRA 3/2, returner 5/5, new 6/5, derived not hardcoded. Soft, because an RA with five weekday class conflicts can only work weekends. Sits above preferences. A/B on the real grid: RAs on their ideal mix went 12/43 to 38/43 and worst imbalance 4 to 1, with fairness and both preference numbers completely unchanged.

**All four soft preferences now honoured (2026-08-26).** Weekday rank, weekend day, and weekend time are solver objective terms; desk preference is handled in `roles.py`. Fairness stays strictly first: the fairness terms are scaled past the worst possible preference cost, derived from the grid. On the real grid with synthetic preferences: 237/240 weekday shifts on a 1st or 2nd choice day, 41 of 43 RAs at 100%, 188/188 weekend matches, 215/275 desks (78%), fairness unchanged at max deviation 1. `synthetic.py` now emits every field the form collects, so Thursday's parser has an exact target shape.

**A pre-solve check shipped with it (2026-08-24).** `preflight.py` runs after parsing and before the solve, and prints the arithmetic in plain numbers so an `INFEASIBLE` comes with a date attached instead of arriving as one word. On synthetic data the returners-only week reads: 32 seats, 17 experienced RAs available, 1.9 each, ceiling of 108. Its most useful check on 08-27 is probably not the seat math at all but the stray-key one, since a parser emitting keys the grid doesn't recognize produces empty availability that looks exactly like a real conflict.

## Next

1. **Wait for the rest of the responses.** 7 of 43 are in as of 08-26 evening; the form closes 08-27 at 11:59 pm. The parser STOPs on every missing person by name, so the chase list is one run away at any point.
2. **Resolve the 2 off-roster respondents.** Two people submitted with an email that is not on `RA Roster - Tiered.xlsx`. Either the roster email is wrong for them or they are not on it. Fix the roster, not the parser.
3. **First real run, Friday 08-28.** Fix real conflicts as they surface. First check: can 17 experienced RAs cover the 24 returners-only seats given their real availability. Second check: every RA in the form matches a roster row keyed by ucsd email, and non-submitters are chased, not silently dropped.
4. **Show the schedule, not the test results.** Before anyone trusts it, the supervising ADRL and the duty leads eyeball a real filled schedule. The validator saying zero violations is Claude grading homework Claude wrote; the leads reading actual rows is the evidence that counts. Lesson imported from the colony counter.
5. **Tune the preference weights against real rankings.** The layer is built and passing; what is untested is how it behaves when rankings are lopsided. Synthetic rankings spread almost evenly (10/6/7/9/11 people per first-choice day) and produced 99%. If 20 real RAs all rank Friday first, the number falls and the interesting question becomes whether that is acceptable or whether the cost curve needs adjusting. Measure first, change nothing until then.
6. **Desk seating is done being tuned.** 78%, examined 2026-08-26. The greedy split was already optimal; pair selection added 8 seats. What remains is structural: 34 misses are people who want a game room seated on weekend Morning/Afternoon shifts, which have none. Fixing that means letting a desk wish override a day or time wish, which Shivam ruled against. Closed unless he reopens it.

## Blocked

- **Real data:** 7 of 43 responses in. Form closes 2026-08-27 at 11:59 pm. The parser is built and tested on the 7; the real run is Friday morning.


## Open questions

None that block the real run. Every design decision v1 needs has been made.

- **Does the supervising ADRL expect to operate the tool themselves?** Decides whether a v2 UI gets built. Not a v1 question; parked until the solver is trusted on real data.
- **Real experienced availability in the returners-only week.** 24 seats over 17 experienced RAs (the grid changed 08-26; it was 32). Only the data answers this. Friday's `[preflight]` line for `returners_only` is where to look.
- **How lopsided are the real weekday rankings?** Decides whether task #4's cost curve needs tuning. Synthetic rankings spread nearly evenly; real ones may not. Measure after the first clean run, change nothing before.

## Known issues, accepted

- **Weekend hard can't-dos live in free text.** The form fix that would structure them was proposed and not required; v1 encodes them by hand before solving. Cost: minutes per run, plus the risk of missing one, which the leads' eyeball pass is the backstop for.
- **"Replay last year" is weaker evidence than the spec assumed.** The 25-26 workbook carries 355 swap records, so its schedule sheet is the plan, not what happened. 2025-09-20 alone saw 7 swaps. A row that looks like a violation may have been fixed; a clean row may have been swapped into a problem. Useful for shaking out the parser, not for proving the rules.
- **All verification so far is Claude-written and Claude-scored.** Mitigated by `validate.py` sharing zero code with the solver, and properly closed by item 3 in Next.
- **The "one recurring weekday" model was recorded as confirmed and never built as such.** Resolved 2026-08-26: built as a soft rank pull instead, which is what the data supported. Kept here because the original discrepancy is the lesson, not the outcome.
- **`preflight.py`'s blocking arm is narrow.** The per-shift and stray-key checks do the real work. The block-level one only fires when a date pairs Afternoon with Evening, the combination H3 forbids; it stays as a backstop and the docstring says so. Its everyday value is the capacity numbers it prints, not a failure it catches.
- **The synthetic filled schedule looks real.** `filled_schedule_SYNTHETIC.xlsx` carries fake RA ids on the real grid. The filename is the guard; do not let it near the duty leads.

## How to run things

```
pip install ortools openpyxl
python run_pipeline.py --grid <duty-schedule.xlsx> --out filled.xlsx [--seed N]
python run_pipeline.py ... --preflight-all      # every pre-solve finding, not the first 20
python tests/test_roles.py
python tests/test_preflight.py                  # no ortools needed, runs anywhere
```

Same seed plus same inputs gives the same schedule; reruns are reproducible, not a dice roll.

## Dropped, with reasons

- **"Experienced RA is always Primary" on 2-person pairing shifts.** Invented by Claude from a leadership misreading of Primary, corrected by Shivam 2026-08-24. Primary is a time slot.
- **Capping the run at Oct 18.** Full quarter chosen (D1) because pairing front-loads experienced RAs and only whole-quarter balancing nets out fair.
- **Hard fairness caps.** Rejected with F1: a cap can declare the schedule impossible over one extra shift.

## Closed

- **The Exceptions column.** Settled by Shivam 2026-08-26: it lists who cannot work that date, meaning a blackout date OR a class conflict. It stays as it is. The exporter had been writing blackout dates only; class conflicts are now included, read off availability so the column cannot disagree with the solver.
- **Pairing-period length.** Was [TBD, ask ADRLs] in the spec since July. Settled: Sept 8-13 returners only, Sept 14-Oct 18 experienced+new pairing, which is exactly 4 duty weeks around the Sept 21-27 gap.
- **Duty-date calendar.** Was an outstanding external input. Delivered as the grid xlsx, holidays included. Confirmed 2026-08-24 as the file the build uses: `~/Downloads/26-27 RA Duty Schedule.xlsx`, read cleanly by `grid.py`.
- **Friday's status.** A weekday. The grid settles what the form contradicts.
- **Where the code lives.** Its own private repo, `ssinghal732/ra-scheduler`. Public or private was the open call; private, because that direction is the reversible one.

## Shipped

- Last year replayed (2026-08-24): 25-26 Fall schedule through `validate.py`, plus a throwaway parser over last year's real form responses. Confirmed every shift carried the right headcount, surfaced one genuine back-to-back, and turned up the 355-row swaps sheet that limits what the replay can prove. Four parser decisions locked off the back of it.
- Documents (2026-08-24): `documents/how-the-pipeline-works.md`, commit `94e8fd6`, plus an artifact at claude.ai/code/artifact/78189a02-eb34-4722-912b-5777c5860f9a.
- Repo plus pre-flight (2026-08-24): `ssinghal732/ra-scheduler` private at `28959ca`, `preflight.py` and its 11 tests, ignore rules that keep operator docs and real data out.
- v1 end to end (2026-08-24): package restructure, formatter, exporter, tests, walk-pair correction, commit `6f792fc`. Details in [CHANGELOG.md](CHANGELOG.md).
- v1 spec (2026-07-12): `../ra-scheduler-v1-spec.md`, commit `06e5cde`.
