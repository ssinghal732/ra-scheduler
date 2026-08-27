# RA Scheduler

Fills the Seventh College quarterly RA duty schedule: 440 seats across 136 shifts and 43 RAs, from the duty leads' grid plus the availability form. A CP-SAT solver replaces the assignment step that currently takes 2-3 RAs roughly 8 hours per quarter by hand, and it has to honor rules a hand process routinely fumbles: a returners-only opening week, four weeks of experienced+new walk pairs, and per-tier shift loads.

This file covers what this project is and how it's wired. How we work together lives in `~/.claude/CLAUDE.md`, which loads automatically in every session. Read that first.

Update this file when the project changes shape. A stale CLAUDE.md is worse than none.

---

## Boot

AiCC area: `technical-projects`. Boot it explicitly, since the default area is `personal`.

The build is Technical Projects work. The duty-scheduling domain facts (what a duty walk is, who the duty leads are, RA training dates) belong to the `resident-assistant` lane, but this project stays here. Same routing as the colony counter: role-grown context lives in its lane, big builds live here.

Then NOW.md, then a skim of CHANGELOG.md, then `git log --oneline -10`, then ask Shivam what he wants to work on. **If it is 2026-08-27 or soon after: NOW.md has a "Tomorrow" section at the top with the plan Shivam set. Start there.**

---

## How we work in this repo

Earned on 2026-08-24, the day the whole v1 was built. Everything in `~/.claude/CLAUDE.md` applies on top.

**Every design and strategy decision is Shivam's.** He said this in as many words. Surface the decision, give one recommendation with its tradeoff, and wait. The v1 decision log (D1-D6, F1-F3, Q1-Q2) all went through him and every one of them is in the code.

**Flag judgment calls out loud, separately from the work.** The one invented rule of the build ("experienced RA must be Primary on 2-person shifts") got caught within a message because it was flagged as a judgment call instead of buried. When a rule came from you and not from Shivam or the data, say so.

**Prove rule claims from the output file, not from tests.** Shivam verifies by asking pointed "did you implement X" questions. The answer that lands is rows pulled from the generated schedule showing the rule holding, not "yes" and not a passing test Claude wrote and also scored. `validate.py` shares zero code with the solver for the same reason.

**Shivam can code. He is newer to constraint solving.** Python and R are fine, don't explain a for loop. Do slow down on CP-SAT concepts: the on/off-switch framing of decision variables, why hard constraints never break, how a weighted objective encodes priorities. The plain-language explanation of the solver was explicitly requested and landed well.

**Plainer and more organized beats thorough.** He pushed twice in one session for cleaner structure: where we are, what we want, how we get there, decisions in labeled blocks. Tables for status, short sections, one question at a time.

---

## Standing decisions, do not reopen

Each was decided by Shivam with a reason, 2026-08-24 unless noted. Reopening them wastes a session.

| Decision | Why |
|---|---|
| Full quarter in one solve, rules date-gated (D1) | The pairing block forces experienced RAs front-heavy; only whole-quarter balancing nets out to fair totals. Same model work either way. |
| Friday is a weekday | The form contradicts itself three ways; the grid settles it. Every Friday is "Evening (Weekday)" with 4 seats, identical to Mon-Thu. |
| LRA = experienced tier for eligibility and pairing, half load for fairness (D5, D6) | An LRA is an experienced returning RA. No other LRA restriction exists (Q2). |
| Fairness targets are soft goals, never hard caps (F1) | A hard cap can declare the whole schedule impossible over one extra shift. Availability is the only unbreakable thing. |
| Minimax objective (F2) | RAs compare counts with each other. Protecting the worst-off person is what "fair" feels like; a few people slightly off beats one person slammed. |
| LRA target 5, 6 only if forced (F3) | Half of the new-RA baseline is 5.5; Shivam chose the low side, implemented as a heavier deviation weight. |
| Pairing period is training, so every new RA gets >= 2 pairing shifts (Q1) | Quarter-total fairness alone left 3 new RAs with zero pairing shifts, perfect counts, and no training. Soft floor, weight above the fairness terms, flags anyone it cannot seat. |
| The pairing period trains the DESK SHIFT as well as the walk (2026-08-26) | Shivam, when he asked whether desk pairs were being checked and they were not. All four pairings on a 4-person pairing shift must be 1 experienced + 1 new: both walk pairs (across desks) and both desk pairs (across walks). Before this, 20 of 56 desk pairs were same-tier and 10 of 28 shifts had two new RAs staffing a desk together all evening. As a grid, every row and column needs one of each; 8 of 24 orderings qualify and one always exists, so slotting still cannot fail. Cost was 1 point of desk preference. |
| Primary / Secondary = first walk (7:30) / second walk (9:30), not seniority | Corrected by Shivam after Claude invented a leadership reading. The walk is done by the pair together; during the pairing period every walk pair is 1 experienced + 1 new. On 2-person shifts the label order is randomized because it carries no meaning. |
| Solver picks people; roles are a post-step | FRA/GRA is a soft preference, not eligibility. 2 experienced + 2 new selected guarantees a legal pair arrangement always exists, so slotting never fails. |
| Parser joins on email, then full name, then unique first name, flagging every fallback and stopping if all fail (revised 2026-08-26) | Was "email only, never names", from last year's 4-of-45 name match rate. Then two of the first seven real respondents had a **different ucsd.edu address** from the roster: people have more than one. Shivam set the chain. Name matching is exact (trimmed, lowercased), never fuzzy, and a fallback match FLAGs so the roster gets corrected. |
| Non-submitters stop the run and get listed (2026-08-24) | Treating them as fully available or fully unavailable both produce a plausible-looking schedule built on someone the tool knows nothing about. Shivam chases them, or decides explicitly, before solving. |
| Blackout dates are MM/DD only, chopped at position 5 (2026-08-24) | The new form specifies `MM/DD (Reason)` and Shivam hand-checks responses before the parser sees them. Anything without a leading date is reported as unreadable, never guessed at. |
| No NLP or LLM anywhere in the parser (2026-08-24, reaffirmed 2026-08-26) | 43 rows once a quarter, pre-checked by a human. **The parser handles every shape that has been observed and refuses everything else, loudly.** On the first 7 real responses it read `12/9 (Final)`, `12/09(Final)`, and comma-joined entries, and flagged `Oct. 17 (Concert)` rather than guessing. An LLM would have read `Oct. 17` correctly and would also have turned "entire thanksgiving break" into some set of dates, confidently, with no way to know which. For a hard constraint, a flagged unreadable date beats a confident wrong one. If real data shows a new common shape, the regex gets one line wider; a rare strange one stays a flag. Shivam asked "then how do we parse weird regex?" on 08-26; this is the answer, and it is the sentence for the technical doc. |
| Preferences are a strict TIEBREAKER under fairness, never a trade against it (2026-08-26) | Shivam: "solve for fairness." Implemented exactly, not approximately: `_fairness_scale()` derives a multiplier from the grid that exceeds the worst possible total preference cost (1137 vs 1136 on this quarter), so one unit of deviation outweighs every preference combined. Among equally fair schedules the solver picks the one people asked for. Built and passing. |
| Preference priority: weekday > weekend day > weekend time > desk (2026-08-26) | Shivam's ranking of what he would want as an RA. Encoded so the worst miss in each category outranks the worst in the next: 5th-choice weekday 3, wrong weekend day 2, wrong weekend time 1. Right-day-wrong-time therefore beats wrong-day-right-time. |
| Desk preference is never priced in the solver at all (2026-08-26) | Not "weighted last", absent. Shivam: honour day and time over location. Someone asking for Game Room AND Morning wants something that does not exist, since morning shifts have no game room; leaving desk out of the model means the day/time wish wins by construction rather than by weight. Cost: 34 of 62 seats on game-room-less shifts go to people who wanted a game room, and that is accepted. |
| Rank cost curve is 0 / 0 / 1 / 2 / 3 (2026-08-26) | The form promises "your first or second most preferred weekday", so ranks 1 and 2 both cost nothing. Shivam asked for stepped but gentle, so each step past that adds one rather than escalating. |
| Desk preference lives in `roles.py`, not the solver (2026-08-26) | The solver never learns desks exist; it picks people and `roles.py` seats them. Putting FD/GR in the model would mean splitting every shift's seats and roughly doubling it, for a preference that cannot affect fairness or feasibility either way. |
| Weekday preferences are a SOFT pull toward the ranked day, never a hard recurring assignment (2026-08-26) | Shivam's call. The 08-24 checkpoint recorded "each RA gets ONE recurring weekday" as confirmed; the solver never implemented it, and last year's real schedule shows the leads do not work that way either. Only 5 of 44 RAs had a single weekday; the median RA did 62% of their weekday shifts on their most-used day. A hard constraint would be less like their real schedule and could make a quarter infeasible. **Built 2026-08-26.** |
| Targets derived from seat count each run, never hardcoded | `compute_targets()` re-derives 11/10/5 from the grid and roster, so a changed grid cannot silently invalidate the numbers. |
| Solver first, UI is v2 | From the spec. Confirmed 2026-08-26: the ADRLs and duty leads WILL operate the tool themselves, so a UI is a real v2 item. Still gated on the solver being trusted on real data first. |
| CP-SAT over a hand-rolled greedy loop | The hard rules (availability, composition, pairing, back-to-back) are what a CP solver enforces natively, in less code than a greedy loop that backtracks. |
| ~~Fairness = total shift count only~~ **REVERSED 2026-08-26** | Was: no weekend-load term, because an RA who can do no weekdays legitimately ends up weekend-heavy. Shivam reversed it: the weekday/weekend MIX should be equitable too. The original reason still holds and is why the new term is soft, not hard. |
| Weekday/weekend balance is a soft goal, derived from the grid (2026-08-26) | Ideal split = tier target x the grid's weekday share. This quarter is 240 of 448 seats = 53.6%, giving LRA 3/2, returner 5/5, new 6/5. Shivam's own example ("10 shifts should be 5 and 5") is exactly what falls out for a returner. Sits ABOVE preferences: equity outranks preference. Measured cost on the real grid: none. |
| Weekday end-times ignored in v1 | From the spec. Redundant with the ranking matrix, and they are the messiest free text on the form. |

---

## The measured facts

All measured 2026-08-24 against the real grid (`26-27_RA_Duty_Schedule.xlsx`) and the confirmed roster. Re-verify against the real availability data when it lands.

**The grid changed on 2026-08-26.** The leads' current file (`26-27 RA Duty Schedule (1).xlsx`, the one carrying the form responses in its `Fall Availability` tab) drops the Sept 8 and Sept 9 weekday evenings. **Now: 136 shifts, 440 seats, 84 duty dates, 2026-09-10 to 2026-12-13.** Returners-only block is 4 dates / 24 seats instead of 6 / 32. Pairing and normal blocks unchanged. `compute_targets()` re-derives from 440, and `_weekday_share()` from the new 232/440. Every figure below that says 448 or 138 was measured on the earlier file and is left as history. **Always run against the leads' latest file, never a cached copy.**

**The grid, as first measured 2026-08-24,** was the full quarter, 2026-09-08 to 2026-12-13: 138 shift instances, 448 seats, 86 duty dates. Holidays (Nov 11, 17, 26, 27) are written as the literal word "Holiday" across the slot cells, not a flag column. The week of Sept 21-27 has no duty at all.

**Rule blocks:** returners-only Sept 8-13 (6 dates, 32 seats), pairing Sept 14-Oct 18 (28 dates, 144 seats), normal Oct 19-Dec 13 (52 dates, 272 seats). The pairing block is exactly 4 duty weeks once the gap week is skipped, matching Shivam's "4 week period."

**Roster:** 43 RAs = 3 LRA + 14 returners + 26 new, so 17 experienced. Loads: new = baseline, returner = baseline - 1, LRA = half. At 448 seats that derives to targets of 11 / 10 / 5.

**Staffing per shift:** weekday evening 2 FD + 2 GR; weekend morning and afternoon 2 FD; weekend evening 2 FD + 2 GR. Duty-round location alternates per date and is carried from the grid, never chosen.

**The proven run** (synthetic availability, real everything else): OPTIMAL in under 60s, ~5,900 boolean variables, 0 violations from the independent validator, max deviation 1 (LRA all 5, returners 10-11, new 11-12), all 26 new RAs at or above the training floor, all 28 pairing-period evening shifts with mixed Primary and Secondary pairs.

**Last year's schedule, replayed 2026-08-24** (`25-26 RA Duty Schedule.xlsx`, Fall sheet, 148 shifts / 480 seats / 45 names). Every shift carried exactly the right headcount. `validate.py` returned 6 findings: 5 of them come from one date, 2025-12-14, where a single name is written into all 8 slots and appears nowhere else in the quarter; the sixth is a genuine Morning-to-Afternoon back-to-back on 2025-09-20.

**The replay's own limit, and it is a real one:** that workbook has an `RA Duty Swaps` sheet with 355 records. The schedule sheet is the PLAN, not the record of what happened. 2025-09-20 alone saw 7 swaps. So a row that looks like a violation may have been fixed, and a clean row may have been swapped into a problem. Validating against last year's sheet validates a plan that was amended 355 times; treat "replay last year" as weak evidence, not proof.

**Availability replay** (last year's `RA Duty Availability (FALL)`, 42 responses): 44 weekday Class-Conflict marks across 31 people, 168 blackout dates across 38. After joining, 406 of 480 assignments were checkable. The plan contained 5 people scheduled on a weekday they marked unavailable and 3 on a date they listed as an exception, four of those inside finals week, the most-swapped week of the quarter. Same caveat applies.

**Weekday/weekend balance, A/B measured 2026-08-26 on the real grid, same inputs.** RAs on their ideal mix 12/43 -> 38/43; worst imbalance 4 shifts -> 1. Max deviation unchanged at 1, weekday preference unchanged at 99%, weekend unchanged at 100%. **It cost nothing.** The prediction that preferences would drop was wrong: the solver already had many equally-optimal schedules and was picking among them arbitrarily, so the balance term selected a better one from the same set. The 5 RAs left at +1 are forced arithmetic, not a miss: the ideals sum to 235 against 240 weekday seats.

**Watch out when A/B testing the objective:** the first comparison was invalid because the balance feature has TWO terms (a worst-case and a sum) and only one was being switched off. Both weights are now named constants (`W_MAXIMB`, `W_IMBSUM`) so an off switch is really off.

**Preferences, measured 2026-08-26 on the real grid with synthetic preferences.** 237 of 240 weekday shifts landed on a 1st or 2nd choice day (99%); 41 of 43 RAs got 100% of theirs. Every weekend shift matched both the day and time asked for (188/188). Desks 212/275 (77%), lower because a pairing shift puts one person at each desk and both may want the same one. Fairness unchanged: max deviation 1, LRA all 5. Total preference cost 3.

**Desk seating, examined 2026-08-26.** 78% overall (79% before desk-pair training was enforced), and the remaining misses are mostly not fixable in `roles.py`: 34 of 57 land on weekend Morning/Afternoon shifts that have no game room at all, so the person was already assigned there before slotting saw them. Pairing shifts run 90%, normal 4-person shifts 89%. The greedy split was measured and is already optimal; the win came from choosing WHICH experienced RA pairs with WHICH new RA, which was previously left to a shuffled index and is worth 8 seats.

**Shivam's read was right:** there is enough capacity that fairness and preferences barely conflict. Whether that holds on real rankings depends on how lopsided they are, which the synthetic distribution cannot tell us.

**Weekday concentration, measured 2026-08-26.** Last year by hand: median RA did 62% of their weekday evenings on their most-used day, 23 of 42 at 60%+, only 5 of 44 on a single weekday. Our solver: median 50%, which is what scattering across free days produces.

**62% is a benchmark, not a target** (Shivam pushed on this, correctly). The grid holds 48 weekday-evening seats on each of the five days, 240 total, 5.6 per RA across 43 RAs. Spread 43 people evenly over 5 days and each day's 48 seats hold exactly 5.6 shifts per person, so 100% concentration is mathematically possible with evenly-spread rankings. What actually caps it is how lopsided the real rankings are, plus availability and the differing tier loads. Tune the weight up against real data and measure where fairness starts to give; do not code a target number.

---

## The form as shipped (read 2026-08-26 from `DutyAvailForm_FA26.pdf`)

**Deadline: Thursday 08/27, 11:59 pm.** Building the parser Thursday daytime means working against a partial response set. The complete set exists Friday morning.

**Fixes that landed:** the weekday ranking is now 1-5 across five rows Monday-Friday (this was the data-corrupting defect; it is fixed). Weekday and weekend definitions are consistent on every page, and Friday is nowhere called a weekend. Shivam fixed the page-3 header contradiction himself on 08-26.

**Fixes that did not land, and do not matter:** the weekend checkbox still mixes day and time in one multi-select. It needs no fix, because every option is self-identifying: `[Saturdays]` / `[Sundays]` / `[Open]` are days, `[Morning]` / `[Afternoon]` / `[Evening]` are times. The parser splits them.

**Date instructions got much stricter, aimed squarely at last year's failures:**
`**FORMAT: MM/DD (Reason)**`, no year, no month names, ranges written out one date per line. `NOT: 10/10/26`. `DO NOT say: Mar 12 OR March 12`.

**What the parser must handle, per question:**

| Form question | Signal | Parser note |
|---|---|---|
| Email (auto-recorded) | the join key | The only stable key. Never join on names. |
| RA Name | display only | Free text, inconsistent. Do not key on it. |
| "What time do your weekdays end?" | ignored in v1 | Standing decision. Messiest free text on the form. |
| Weekday ranking 1-5 + Class Conflict | **hard** (Conflict) and **soft** (the rank) | The rank is what task #4 needs. **Capture it even though the solver ignores it today**, or Thursday's work gets redone. |
| "Weekday DATES you CANNOT do" (page 4) | hard | Weekday-only subset. |
| "ALL DATES you CANNOT do" (page 6) | hard | Superset, weekdays AND weekends. **Union both columns**; both are required and people will half-fill one. |
| Weekend day/time checkbox | soft | One multi-select, split by bracketed label. |
| Shift location (FD / GR / either) | soft | Single choice, three options. |
| Two "additional concerns" free-text boxes | manual | Weekend hard can't-dos hide here. Hand-encoded in v1. |

**What the first 7 real responses showed (2026-08-26), which the PDF could not:**
- The ranking grid exports as five columns whose headers end `[Monday]` .. `[Friday]`. Values are **floats** (`1.0`) mixed with the string `Class Conflict/Unavailable` in the same column.
- The weekend checkbox exports as one comma-joined string with the bracket labels intact.
- **People wrote `12/9` and `9/10`, not `12/09` and `09/10`.** A fixed five-character chop fails. The parser reads `M/D` or `MM/DD` off the front of each entry instead. Same decision, wider front.
- **About half used commas, not newlines**, despite the instruction. Split on both.
- **The two date boxes are not the subset the form implies.** One person put 15 dates in the weekday box and a different 7 in the all-dates box. Unioned, disagreement flagged.
- One person wrote `Oct. 17`. Reported, not guessed.
- 2 of 7 respondents' emails were not on the roster.

**The form makes a promise the solver currently cannot keep.** Twice it tells RAs: "Seventh College RAs will be assigned a week day per their availability each quarter," and "We will do our best to ensure you have your first or second most preferred weekday." The solver reads the ranking only for its Class Conflict marker and throws the ranks away. See AiCC task #4.

---

**Feasibility margin worth knowing:** the returners-only week is 32 seats over 17 experienced RAs, about 1.9 shifts each. Comfortable with generous availability; the first thing to re-check on real data.

---

## Stack

```
Python 3.12
ortools              CP-SAT, the solver
openpyxl             reads the grid, writes the filled schedule

NOT USED: pandas (nothing needs it), no database (CSV/xlsx throughout),
no web framework (UI is v2, gated on the solver being trusted)
```

Install only what the code in front of you imports.

---

## Layout

| Path | What lives there |
|---|---|
| `ra_scheduler/models.py` | Every rule constant: tiers, block dates, staffing shapes, target math. Nothing is defined twice. |
| `ra_scheduler/grid.py` | Duty-grid xlsx to shift instances, holiday rows kept separately for export. |
| `ra_scheduler/synthetic.py` | Synthetic availability and preferences, in the exact `AvailabilityData` shape. Used when `--availability` is omitted; the output is then stamped SYNTHETIC. |
| `ra_scheduler/parse_form.py` | **The real thing.** Reads the Google Form export plus the roster into `AvailabilityData`. Keyword column matching with a printed match report, three-tier findings (STOP / FLAG / READ), every 08-26 parser decision encoded. |
| `ra_scheduler/preflight.py` | Pre-solve arithmetic. Turns a bare `INFEASIBLE` into a dated list of what is short, and catches the parser faults that look like scheduling conflicts. Necessary conditions only; the solver stays the authority. |
| `ra_scheduler/solver.py` | CP-SAT selection: who works each shift. All hard rules and the soft objective. |
| `ra_scheduler/roles.py` | Slots the chosen people into named columns. Training-pair rules (walks AND desks) and desk preference live here. |
| `ra_scheduler/validate.py` | Independent re-check of every hard rule and role invariant. Shares no logic with solver or roles, on purpose. |
| `ra_scheduler/export.py` | Writes the filled xlsx in the duty leads' exact column shape. |
| `run_pipeline.py` | End to end: grid, availability, solve, roles, validate, export. |
| `tests/test_roles.py` | Unit tests on the trickiest pure logic. `python tests/test_roles.py`. |
| `tests/test_parse_form.py` | Parser tests on the shapes seen in the first real responses. No real data in them. |
| `tests/test_preferences.py` | Unit tests on the preference layer. The first one guards the fairness-beats-preferences property. |
| `tests/test_preflight.py` | Unit tests on the pre-solve check. No ortools needed, so they run anywhere. |
| `documents/how-the-pipeline-works.md` | Plain-language walkthrough of every module, written for a non-technical reader. Published as an artifact too; keep the two in step. |

---

## Repo-specific notes

- **Where the code lives:** `ssinghal732/ra-scheduler` (private), created 2026-08-24, first commit `28959ca`. This working copy at `~/src/Technical-Projects/RA-Scheduler/` is the repo, not a mirror. The earlier copy under `ssinghal732/AICC` at `technical-projects/ra-scheduler/code/` (`6f792fc`) is now history; the v1 spec still sits beside it at `../ra-scheduler-v1-spec.md` (`06e5cde`, 2026-07-12).
- **Private was chosen because it is the reversible direction.** Private can become public later; the reverse leaves the history exposed. Flipping it is Shivam's call.
- **Code yes, docs yes, data never.** Changed 2026-08-26 by Shivam, overriding the global rule that operator docs stay out of a repo. CLAUDE.md, NOW.md, and CHANGELOG.md are now tracked and pushed, so this repo carries its own context and a fresh session finds everything in one place. The condition attached: **no real names in any of them.** People are referred to by role, because `git push` is permanent and stripping a name later means rewriting history, not editing a file.
- **Data still never enters the repo.** The real grid, the availability export, and any filled schedule carry real RA names. `.gitignore` blocks `*.xlsx` / `*.csv` / `*.json` so that cannot happen by accident.
- **People:** the ADRL supervising this project is also a duty lead; two RA duty leads run the schedule day to day. All of them will operate the tool themselves (confirmed 2026-08-26), which is what makes the v2 UI real. Names are deliberately kept out of this repo.
- **The parser is built** (`ccbbf80`, 2026-08-26) and verified on the first 7 real responses: every column matched, every availability key it produced matches a real shift. Run: `python run_pipeline.py --grid <grid> --roster <roster> --availability <export> --sheet "Fall Availability" --out <out>`. It STOPs until every roster member has submitted.
- **The form-fix thread is closed.** Read the shipped form 2026-08-26 (`~/Downloads/DutyAvailForm_FA26.pdf`, 7 pages). See "The form as shipped" below for what landed and what the parser faces. **The real deadline is Thursday 08/27 at 11:59 pm**, not 08/28: responses are still arriving through Thursday evening, so a complete set does not exist until Friday morning.
- **Time category:** `RA_Scheduler`, short code `RAS`, in `technical-projects`. Created 2026-08-26. Log with `time_log(category='RAS', ...)`. Ask Shivam for the hours; never guess them.

---

## Tracking docs

| File | What lives there |
|---|---|
| [NOW.md](NOW.md) | Active, next, blocked, open questions. Update when priorities shift. |
| [CHANGELOG.md](CHANGELOG.md) | Dated record of what shipped. |
| `../ra-scheduler-v1-spec.md` | The v1 spec: problem, domain model, constraints, build order. Update when a decision changes it. |
