# NOW

## What this is

RA Scheduler: fills the Seventh College quarterly duty schedule (440 seats, 136 shifts, 43 RAs) from the duty leads' grid plus the availability form, honoring the returners-only week, four weeks of experienced+new walk pairs, and per-tier loads. Spec at `../ra-scheduler-v1-spec.md`. Project brief in [CLAUDE.md](CLAUDE.md).

Built end to end 2026-08-24, extended through 2026-08-26 (preferences, balance, parser, all verified on real partial data). Form closes 2026-08-27 at 11:59 pm; complete response set exists 2026-08-28. Product docs start 2026-08-27.

## Tomorrow, 2026-08-27 (set by Shivam the night before)

Two threads run in parallel. The real data arrives during the day.

**Thread 1, the real run.** The form closes 08-27 at 11:59 pm, so a complete set exists Friday morning; partials are useful all day. Steps, in order: export the response sheet, run the command in the README, read the `[parse]` STOPs (the chase list, by name and tier) and READs (the concerns boxes to hand-encode), fix what needs fixing, run again. When it solves: `[preflight]` returners-only first (17 experienced against 24 seats with real availability), then `[balance]`, then `[prefs]`. Then open the xlsx and read rows. Two off-roster respondents now join by name with a FLAG; fix the roster afterwards, not before.

**Thread 2, the three product docs.** AiCC task #5. Full headstart below under "The three product docs". Order that works: vision doc first (no dependencies, and writing it in plain English settles what the thing is), then the five forks, then the technical doc and the design brief together. The design brief goes to Claude Design, which produces a presentation; CC's job is the direction discussion beforehand, not the visuals.

**Standing answer to keep handy:** no LLM, no NLP. The parser handles every observed shape and flags the rest. A flagged unreadable date beats a confident wrong one. That sentence goes in the technical doc.

## Next session starts here (set 2026-08-28, late)

**Discuss, do not build: Google Sheets instead of a website for v2.** AiCC task #6 has the questions and one recommendation to bring. Shivam's reason: running a website will be hard (hosting, FERPA off campus, sign-in, succession, all of which the technical design already listed as open). The leads live in Sheets, the data already lives in UCSD's Workspace, the swap Apps Script exists, and there is no server to own. The solver stays Python on a laptop; the question is what reads and writes the sheet and what Apps Script does. Both the technical design and the design brief assume a website and will need a Sheets-first pass after the discussion. The vision doc's "Where this is going" needs a lighter touch.

Also queued for Shivam: read the 43 concerns boxes and rerun; fix the 25 stale roster emails; hand the schedule to the leads.

## The first real run happened (2026-08-28)

All 43 responses in, the leads' file `26-27 RA Duty Schedule (3).xlsx`, roster `RA Roster - Tiered.xlsx`. Output at `~/Downloads/fall_2026.xlsx` (real names; never enters the repo). `OPTIMAL`, 0 violations, 0 STOPs, 68 flags (grouped by kind), 43 concerns boxes to read (printed per person, wrapped).

| | |
|---|---|
| Fairness | LRA all 5; returners 10-11; new 10-11; max deviation 1 (targets 11/10/5 after the rounding fix) |
| Balance | 40/43 on their ideal weekday/weekend mix; worst 1 |
| Spread | 11 person-weeks over one shift; busiest week 3 |
| Weekday 1st/2nd choice | **203/232 (88%)**, down from 99% on synthetic |
| Weekend day+time | 183/198 (92%) |
| Desk | 210/269 (78%) |
| Rules, read from the file | 0 new RAs in the returners-only week; 28/28 pairing evenings mixed on both walks and both desks; 4 holiday rows; 440 names, all matched to a roster tier |

**Why 88% and not 99%: the real rankings are lopsided, as predicted.** First choices: Monday 13, Tuesday 15, Wednesday 6, Thursday 9, Friday 3, against 48 seats a day (room for about 8.6 first choices each). Tuesday is oversubscribed almost 2:1; Wednesday has 12 class conflicts. 88% is what the grid allows before fairness gives, not a tuning miss. Task #4's question is answered by data.

**25 of 43 roster emails are stale.** More than half of respondents joined by name fallback because the form recorded a different ucsd.edu address. Every one is flagged with the roster's current email. Fix the roster before winter.

**Shivam must read the 43 READ lines himself** (the concerns boxes; they hold the things no form captures) and then read the schedule rows. CC has not read the concerns text into this chat.

## Active

**The whole v1 pipeline works (2026-08-24).** Grid reader, solver, role slotting, independent validator, xlsx exporter, CLI, 17 unit tests. On the real grid with synthetic availability: OPTIMAL in under 60s, 0 violations, max deviation 1 (LRA all 5, returners 10-11, new 11-12), every new RA at or above the 2-shift training floor, all 28 pairing-period evening shifts with mixed walk pairs. Committed to AICC as `6f792fc`.

**One rule was corrected mid-build (2026-08-24).** Primary/Secondary means first walk / second walk, not seniority. Claude had invented "experienced must be Primary" on 2-person shifts; Shivam corrected it, the label order is now randomized, and the wrong reading is scrubbed from code, docstrings, and tests.

**The code has its own repo now (2026-08-24).** `ssinghal732/ra-scheduler`, private, commit `28959ca`, 15 files. Operator docs and data files are held out two different ways: these three docs through `.git/info/exclude` so their names never appear on GitHub, and `*.xlsx` / `*.csv` / `*.json` through `.gitignore` so a real grid or a filled schedule can't slip into a commit.

**Full pipeline verified against the REAL grid (2026-08-24).** `ortools` 9.15.6755 and `openpyxl` 3.1.5 installed into `(base)`. `grid.py` reads `~/Downloads/26-27 RA Duty Schedule.xlsx` with no errors and every documented number matches: 138 shifts, 448 seats, 4 holiday rows, 86 duty dates, blocks at 6/32, 28/144, 52/272, holidays Nov 11/17/26/27. Full run on it: OPTIMAL in under 30s, 0 violations, max deviation 1, LRA all 5. Rules checked by reading rows back out of the output rather than trusting the validator: 0 new RAs in the returners-only week, 28 of 28 pairing-period evening shifts with both walk pairs mixed, all 4 holiday rows preserved. Every module is now exercised against real input except availability.

**Pairing-period training rule corrected (2026-08-26).** Only the walk pairs had been constrained to 1 experienced + 1 new. Shivam asked whether the desk pairs were checked too; they were not, and 10 of 28 pairing shifts had two new RAs staffing a desk together for the whole evening. Both the walk and the desk shift are training, so all four pairings are now mixed, verified independently in `validate.py`. 56 of 56 on both.

**Spread across the quarter shipped (2026-08-27).** The leads' rule that nobody should be done by week four while someone else only works the last few weeks, encoded as a soft cap of one shift per person per calendar week. A/B on the current grid: person-weeks with 2+ shifts 99 -> 13, busiest week 4 -> 2, fairness and preferences untouched. Also from the conversation with last year's leads (now in `references/`, local only): two more habits the solver does not enforce on their own, one weekday per week and no weekday-plus-weekend in one week. The per-week cap covers both wherever it holds, and Shivam kept the cap knowing that.

**The join is a fallback chain now (2026-08-26, `592367f`).** Email, then exact full name, then a first name matching exactly one roster entry; FLAG at every fallback, STOP if all fail or a first name is ambiguous. Two of the first seven real respondents had a different ucsd.edu address from the roster (people have more than one), and both now join with a flag saying the roster email is stale. Shivam set the chain after asking why everything hinged on email.

**The parser is built and verified on real data (2026-08-26, `ccbbf80`).** `parse_form.py` reads the Google Form export and the roster into the same `AvailabilityData` that `synthetic.py` produces. Built against the first 7 real responses: every column matched, 5 of 7 joined to the roster, every availability key it produced matches a real shift. Three-tier findings: STOP halts before the solver (roster member with no submission, all five weekdays conflicted, missing column), FLAG prints and continues (duplicates, >10 blackouts, unreadable dates, off-roster respondent, repeated ranks), READ prints every non-trivial concerns box. Wired in as `--roster` and `--availability`; omit both and the run stays synthetic and stamped.

**The grid changed (2026-08-26).** The leads' current file drops the Sept 8 and 9 evenings: now 136 shifts / 440 seats, starting Sept 10. Returners-only block is 4 dates / 24 seats. Targets and the weekday share re-derive automatically. Always run against their latest file.

**Weekday/weekend balance shipped (2026-08-26).** Reverses the old "total shift count only" decision at Shivam's call. Each RA's mix is pulled toward the grid's own 53.6% weekday share: LRA 3/2, returner 5/5, new 6/5, derived not hardcoded. Soft, because an RA with five weekday class conflicts can only work weekends. Sits above preferences. A/B on the real grid: RAs on their ideal mix went 12/43 to 38/43 and worst imbalance 4 to 1, with fairness and both preference numbers completely unchanged.

**All four soft preferences now honoured (2026-08-26).** Weekday rank, weekend day, and weekend time are solver objective terms; desk preference is handled in `roles.py`. Fairness stays strictly first: the fairness terms are scaled past the worst possible preference cost, derived from the grid. On the real grid with synthetic preferences: 237/240 weekday shifts on a 1st or 2nd choice day, 41 of 43 RAs at 100%, 188/188 weekend matches, 215/275 desks (78%), fairness unchanged at max deviation 1. `synthetic.py` now emits every field the form collects, so Thursday's parser has an exact target shape.

**A pre-solve check shipped with it (2026-08-24).** `preflight.py` runs after parsing and before the solve, and prints the arithmetic in plain numbers so an `INFEASIBLE` comes with a date attached instead of arriving as one word. On synthetic data the returners-only week reads: 32 seats, 17 experienced RAs available, 1.9 each, ceiling of 108. Its most useful check on 08-27 is probably not the seat math at all but the stray-key one, since a parser emitting keys the grid doesn't recognize produces empty availability that looks exactly like a real conflict.

## Next

1. ~~Wait for the rest of the responses.~~ Done: 43 of 43 by 08-28 morning.
2. **Fix the roster emails the parser flags.** 25 of 43 joined by name fallback. Each flag names the person and the roster's stale email. Update the roster so next quarter matches on email directly.
3. ~~First real run, Friday 08-28.~~ Done, see above. Preflight: 0 blocking, 0 tight; the returners-only week was never in danger. Second check: every RA in the form matches a roster row keyed by ucsd email, and non-submitters are chased, not silently dropped.
4. **Show the schedule, not the test results.** Before anyone trusts it, the supervising ADRL and the duty leads eyeball a real filled schedule. The validator saying zero violations is Claude grading homework Claude wrote; the leads reading actual rows is the evidence that counts. Lesson imported from the colony counter.
5. **Tune the preference weights against real rankings.** The layer is built and passing; what is untested is how it behaves when rankings are lopsided. Synthetic rankings spread almost evenly (10/6/7/9/11 people per first-choice day) and produced 99%. If 20 real RAs all rank Friday first, the number falls and the interesting question becomes whether that is acceptable or whether the cost curve needs adjusting. Measure first, change nothing until then.
6. **Desk seating is done being tuned.** 78%, examined 2026-08-26. The greedy split was already optimal; pair selection added 8 seats. What remains is structural: 34 misses are people who want a game room seated on weekend Morning/Afternoon shifts, which have none. Fixing that means letting a desk wish override a day or time wish, which Shivam ruled against. Closed unless he reopens it.

## The three product docs (starting 2026-08-27, AiCC task #5)

Shivam wants three documents. Headstart notes below so tomorrow starts with decisions, not blank pages.

### What already exists that feeds them

- **The decisions table in CLAUDE.md** is the seed of the decisions document: about 20 choices, each with the reason, each dated. The technical design doc can lift it nearly whole.
- **`documents/how-the-pipeline-works.md`** is the non-technical backend walkthrough. The "couple of slides on the backend" in the design brief are a compression of it.
- **Last year's sheet shows two features already expected by the RAs**, not invented for v2: a swap form ("Cover Shifts here: RA Duty Swap Form - Changes are reflected in Yellow", 355 records in one quarter) and calendar export ("ICS Calendar Files of Shifts (Courtesy of Shivam!) ... these dont sync up with swaps so keep track of your swaps yourself!"). That second parenthetical is a product requirement in disguise: **swaps and the calendar must stay in sync**, which the current process cannot do.
- **The ADRLs and duty leads will operate the tool** (confirmed 08-26). Two user types are already implied: the leads (build and publish the schedule, approve swaps) and RAs (see their shifts, request swaps, export to calendar).

### Doc 1, product vision (1-2 pages, plain English)

Structure that fits what is known: the problem (2-3 RAs, ~8 hours a quarter, rules fumbled by hand, 355 swaps then tracked by hand); who it is for (leads and RAs); what it does in one paragraph with no technical words; what changes for each group; what it does NOT do (it does not decide the rules, people do; it does not replace the leads, it removes the tedious part). The measured numbers are the evidence: 448 seats in under 10 seconds, 0 rule violations, 38 of 43 RAs on their ideal weekday/weekend mix, 99% on a 1st or 2nd choice day.

Open question for Shivam: is this for the duty leads and ADRLs only, or is it also a portfolio piece? The answer changes the tone.

### Doc 2, technical design and architecture

**Forks answered by Shivam 2026-08-27.** These are the v2 decisions; doc 2 is the canonical record once approved.

| Question | Answer |
|---|---|
| Roles | Three groups on the admin side (duty leads, ADRLs, lead RAs), all with the same admin powers; every other RA is a member. Two permission levels, three groups. |
| What RAs see | The whole schedule, read only. |
| Login | UCSD login if it can be had; otherwise a private link or key. CC's read: "sign in with Google, ucsd.edu only" is the practical path, UCSD SSO the upgrade. |
| Where it runs | A website, always up, with swaps and calendars. Not a laptop tool. |
| Cost | Free if possible; a few dollars a month out of pocket is acceptable. **Google Sites cannot host this** (static pages, no server); flagged. |
| Who maintains it | Unknown. Hoped to be a legacy project the duty leads keep using after Shivam graduates. Pushes hard toward the simplest possible stack. |
| Availability in | Google Form for the first web quarter, imported; maybe built into the site later. |
| Roster | Stays a spreadsheet the site reads. Shivam cited FERPA; CC flagged that exposure follows where names-plus-schedules live, not the roster file, so privacy is its own section and "does UCSD allow an outside host" is question one for the ADRL. |
| Swaps | One-for-one trades only, no "cover me." A lead approves every swap: one click when no rule breaks, a flag and an alert first when one would. Finding the trade partner stays on the GroupMe. |
| On approval | The RA's calendar updates, the schedule updates, and they get an email. |
| Calendars | One subscribable feed per RA that updates itself, plus a downloadable file; and one calendar with every shift, visible to everyone. |
| Settings leads can change | All of them: rule-block dates, tier loads, preference priority, which soft rules are on. Per quarter, current values shown. |
| Hand edits | Yes, leads can move a person after the build, and the rules get re-checked when they do. |
| Metrics | Swaps per week (must). Weekday/weekend split, first/second-choice rate, fairness split (nice to have). |
| Stack in the doc | Describe the pieces; name the stack as "likely." |
| Audience for doc 2 | Portfolio. Needs framing: problem, constraints, architecture, decisions with reasons. |

### Status of the three docs (2026-08-27)

| Doc | File | State |
|---|---|---|
| 1. Product vision | `documents/product-vision.html` | Drafted, reviewed twice, committed. For the ADRL and duty leads. |
| 2. Technical design | `documents/technical-design.html` | Drafted from Shivam's 18 answers, reviewed once, committed. Portfolio audience. |
| 3. Design brief | `documents/design-brief.html` | Drafted after a design discussion, reworked so only product facts are fixed and every UI choice is a leaning with a reason. Committed. **On hold with doc 2:** both assume a website, and the v2 direction moved to Google Sheets on 08-28 (task #6). Revisit after that discussion, before anything goes to Claude Design. |

All three name Shivam as author. All three are .html; Shivam does not read .md.

### Doc 3, design brief for Claude Design

The brief should say what the product is for and who uses it, and leave the visual design open. Direction to settle with Shivam first:
- **Two roles, two views.** Lead: build a schedule, review flags, publish, approve swaps. RA: my shifts, request a swap, export my calendar. Which is the primary screen for each?
- **The schedule as a calendar, not a spreadsheet.** The xlsx stays as an export; the UI should show a month with shifts on it.
- **Swaps as a workflow**: RA proposes, counterpart accepts, lead approves, schedule and calendars update. Three states, visible to all three people.
- **The flags from the parser and preflight are a UI feature**, not just terminal output: "these 6 people have not submitted", "this person marked every weekday as a conflict", shown before the lead hits build.
- Tone: this is an operations tool for student staff. Calm, fast, no dashboard theatre.
- Constraint for Claude Design: real names never appear in mockups; use the R00-R42 style or invented names.

Presentation content Shivam specified: a couple of non-technical backend slides (compress the walkthrough), then the UI: admin vs user, swaps, calendar export.

## Blocked

- **Real data:** 7 of 43 responses in. Form closes 2026-08-27 at 11:59 pm. The parser is built and tested on the 7; the real run is Friday morning.


## Open questions

None that block the real run. Every design decision v1 needs has been made.


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

- **Who operates the tool.** Answered by Shivam 2026-08-26: the ADRLs and the duty leads will run it themselves. That makes the v2 UI a real item rather than a maybe, still gated on the solver being trusted on real data first.
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
