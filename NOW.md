# NOW

## What this is

RA Scheduler: fills the Seventh College quarterly duty schedule (448 seats, 138 shifts, 43 RAs) from the duty leads' grid plus the availability form, honoring the returners-only week, four weeks of experienced+new walk pairs, and per-tier loads. Spec at `../ra-scheduler-v1-spec.md`. Project brief in [CLAUDE.md](CLAUDE.md).

Built end to end and proven on synthetic availability in one day, 2026-08-24. Form closes 2026-08-27 at 11:59 pm, so a complete response set exists 2026-08-28.

## Active

**The whole v1 pipeline works (2026-08-24).** Grid reader, solver, role slotting, independent validator, xlsx exporter, CLI, 17 unit tests. On the real grid with synthetic availability: OPTIMAL in under 60s, 0 violations, max deviation 1 (LRA all 5, returners 10-11, new 11-12), every new RA at or above the 2-shift training floor, all 28 pairing-period evening shifts with mixed walk pairs. Committed to AICC as `6f792fc`.

**One rule was corrected mid-build (2026-08-24).** Primary/Secondary means first walk / second walk, not seniority. Claude had invented "experienced must be Primary" on 2-person shifts; Shivam corrected it, the label order is now randomized, and the wrong reading is scrubbed from code, docstrings, and tests.

**The code has its own repo now (2026-08-24).** `ssinghal732/ra-scheduler`, private, commit `28959ca`, 15 files. Operator docs and data files are held out two different ways: these three docs through `.git/info/exclude` so their names never appear on GitHub, and `*.xlsx` / `*.csv` / `*.json` through `.gitignore` so a real grid or a filled schedule can't slip into a commit.

**Full pipeline verified against the REAL grid (2026-08-24).** `ortools` 9.15.6755 and `openpyxl` 3.1.5 installed into `(base)`. `grid.py` reads `~/Downloads/26-27 RA Duty Schedule.xlsx` with no errors and every documented number matches: 138 shifts, 448 seats, 4 holiday rows, 86 duty dates, blocks at 6/32, 28/144, 52/272, holidays Nov 11/17/26/27. Full run on it: OPTIMAL in under 30s, 0 violations, max deviation 1, LRA all 5. Rules checked by reading rows back out of the output rather than trusting the validator: 0 new RAs in the returners-only week, 28 of 28 pairing-period evening shifts with both walk pairs mixed, all 4 holiday rows preserved. Every module is now exercised against real input except availability.

**All four soft preferences now honoured (2026-08-26).** Weekday rank, weekend day, and weekend time are solver objective terms; desk preference is handled in `roles.py`. Fairness stays strictly first: the fairness terms are scaled past the worst possible preference cost, derived from the grid. On the real grid with synthetic preferences: 237/240 weekday shifts on a 1st or 2nd choice day, 41 of 43 RAs at 100%, 188/188 weekend matches, 216/275 desks (79%), fairness unchanged at max deviation 1. `synthetic.py` now emits every field the form collects, so Thursday's parser has an exact target shape.

**A pre-solve check shipped with it (2026-08-24).** `preflight.py` runs after parsing and before the solve, and prints the arithmetic in plain numbers so an `INFEASIBLE` comes with a date attached instead of arriving as one word. On synthetic data the returners-only week reads: 32 seats, 17 experienced RAs available, 1.9 each, ceiling of 108. Its most useful check on 08-27 is probably not the seat math at all but the stray-key one, since a parser emitting keys the grid doesn't recognize produces empty availability that looks exactly like a real conflict.

## Next

1. **The form-export parser, 2026-08-27, when the data lands.** Reads the Google Form sheet export into the same `AvailabilityData` that `synthetic.py` produces, then the identical pipeline runs. It has to produce BOTH halves: the roster (who, and which tier) and the availability. `synthetic.py` currently invents both. Four things are decided and need no further discussion:
   - **Key on ucsd email, never on names.** Replaying last year, only 4 of 45 names matched exactly.
   - **Blackout dates: MM/DD only, chopped at position 5.** The new form specifies `MM/DD (Reason)` and Shivam hand-checks responses before the parser runs. Anything with no leading date is reported as unreadable, never guessed.
   - **Non-submitters stop the run and get listed.** No silent default either way.
   - **No NLP.** Plain string matching and a regex.

   Settled 2026-08-26 by reading the shipped form (see CLAUDE.md, "The form as shipped"): ranking is a clean 1-5, dates are NEWLINE-separated not comma-separated, and there are TWO date columns (weekday-only and all-dates) that must be unioned. **Capture the 1-5 ranks even though the solver ignores them**, or task #4 means parsing twice. Still hand-encoded in v1: weekend hard can't-dos hiding in the two free-text concerns boxes.
2. **The `--availability` wiring, same session.** Line 39 of `run_pipeline.py` hardcodes `make_availability(shifts)`, so a run against the real grid today produces a correct-looking schedule staffed by R00-R42 and nothing in the output says so except one `(synthetic)` label. Shivam is building parser and wiring together on 08-27. Open design question raised and not yet decided: whether the pipeline should refuse to write a file at all when availability is synthetic, or force SYNTHETIC into the filename.
3. **First real run.** Fix real conflicts as they surface. First check: can 17 experienced RAs actually cover the 32 returners-only seats given their real availability. Second check: every RA in the form matches a roster row keyed by ucsd email, and non-submitters are chased, not silently dropped.
4. **Show the schedule, not the test results.** Before anyone trusts it, the supervising ADRL and the duty leads eyeball a real filled schedule. The validator saying zero violations is Claude grading homework Claude wrote; the leads reading actual rows is the evidence that counts. Lesson imported from the colony counter.
5. **Tune the preference weights against real rankings.** The layer is built and passing; what is untested is how it behaves when rankings are lopsided. Synthetic rankings spread almost evenly (10/6/7/9/11 people per first-choice day) and produced 99%. If 20 real RAs all rank Friday first, the number falls and the interesting question becomes whether that is acceptable or whether the cost curve needs adjusting. Measure first, change nothing until then.
6. **Desk seating is done being tuned.** 79%, examined 2026-08-26. The greedy split was already optimal; pair selection added 8 seats. What remains is structural: 34 misses are people who want a game room seated on weekend Morning/Afternoon shifts, which have none. Fixing that means letting a desk wish override a day or time wish, which Shivam ruled against. Closed unless he reopens it.

## Blocked

- **Real data:** the form closes 2026-08-27 at 11:59 pm. Partial responses are parseable Thursday daytime; the complete set is Friday morning. Build and debug the parser against partials, run the real schedule Friday.


## Open questions

- **Does the supervising ADRL expect to operate the tool themselves?** They probably do, per Shivam. That answer decides whether a v2 UI ever gets built. Parked until the solver is trusted on real data.
- **What should the Exceptions column list?** Currently: RAs with blackout dates, written once per date. That was Claude's reading of the leads' convention, not a confirmed rule. Check against how they actually used the column last year.
- **How messy is the free-text availability in practice?** Partly answered by the 25-26 replay: of 42 respondents, about 5 wrote a hard constraint with no date in it ("entire thanksgiving break", "I usually go home every weekend"). Shivam's hand-check before the parser runs is the mitigation.
- **Real experienced availability in the returners-only week.** 32 seats over 17 experienced is comfortable only if they are actually available Sept 8-13. Training runs through Sept 11 so they are on campus, but availability is not attendance.

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
