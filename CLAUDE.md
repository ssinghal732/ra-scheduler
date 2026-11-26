# RA Scheduler

Fills the Seventh College quarterly RA duty schedule: 440 seats across 136 shifts and 43 RAs, from the duty leads' grid plus the availability form. A CP-SAT solver replaces the assignment step that currently takes 2-3 RAs roughly 8 hours per quarter by hand, and it has to honor rules a hand process routinely fumbles: a returners-only opening week, four weeks of experienced+new walk pairs, and per-tier shift loads.

This file covers what this project is and how it's wired. How we work together lives in `~/.claude/CLAUDE.md`, which loads automatically in every session. Read that first.

Update this file when the project changes shape. A stale CLAUDE.md is worse than none.

---

## Boot

AiCC area: `technical-projects`. Boot it explicitly, since the default area is `personal`.

The build is Technical Projects work. The duty-scheduling domain facts (what a duty walk is, who the duty leads are, RA training dates) belong to the `resident-assistant` lane, but this project stays here. Same routing as the colony counter: role-grown context lives in its lane, big builds live here.

Then NOW.md, then a skim of CHANGELOG.md, then `git log --oneline -10`, then ask Shivam what he wants to work on. **NOW.md opens with a "Next session starts here" block. Start there.**

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
| Parser joins on email, then full name, then unique first name, flagging every fallback and stopping if all fail (revised 2026-08-26) | Was "email only, never names", from last year's 4-of-45 name match rate. Then two of the first seven real respondents had a **different ucsd.edu address** from the roster: people have more than one. Shivam set the chain. Name matching is exact (trimmed, lowercased), never fuzzy. A fallback match FLAGged so the roster got corrected, until 2026-11-25 when Shivam dropped the flag as noise; the match report now carries a count of people joined by name instead. |
| Parser findings: grouped by severity then kind, names not emails, concerns per person (2026-08-28) | Shivam reading the first real run. STOP, then FLAG in order of how actionable, then READ. **Duplicate ranks moved from the bottom FLAG to a STOP on 2026-11-22**: the leads said duplicates gamed the system, so the person resubmits; Google Forms' "Limit to one response per column" prevents it at the source. Dropped as not actionable (2026-08-28/31): date-boxes-disagree, outside-quarter dates, no-duty dates, email lowercasing. The kinds table in `parse_form.py` is the single place to reorder. |
| Non-submitters stop the run and get listed, and there is NO override (2026-08-24, reaffirmed 2026-08-27) | Treating them as fully available or fully unavailable both produce a plausible-looking schedule built on someone the tool knows nothing about. A command-line override (`--missing x=available/skip`) was proposed and Shivam declined it: the run does not happen until everyone has submitted. Chase, don't guess. |
| Blackout dates are MM/DD only, chopped at position 5 (2026-08-24) | The new form specifies `MM/DD (Reason)` and Shivam hand-checks responses before the parser sees them. Anything without a leading date is reported as unreadable, never guessed at. |
| No NLP or LLM anywhere in the parser (2026-08-24, reaffirmed 2026-08-26; boundary set 2026-08-31) | The boundary: Claude reading the concerns boxes in-session as a one-off triage for Shivam is fine and useful; a model inside the pipeline is not. The parser stays deterministic. |
| No NLP or LLM in the pipeline, details | 43 rows once a quarter, pre-checked by a human. **The parser handles every shape that has been observed and refuses everything else, loudly.** On the first 7 real responses it read `12/9 (Final)`, `12/09(Final)`, and comma-joined entries, and flagged `Oct. 17 (Concert)` rather than guessing. An LLM would have read `Oct. 17` correctly and would also have turned "entire thanksgiving break" into some set of dates, confidently, with no way to know which. For a hard constraint, a flagged unreadable date beats a confident wrong one. If real data shows a new common shape, the regex gets one line wider; a rare strange one stays a flag. Shivam asked "then how do we parse weird regex?" on 08-26; this is the answer, and it is the sentence for the technical doc. |
| Preferences are a strict TIEBREAKER under fairness, never a trade against it (2026-08-26) | Shivam: "solve for fairness." Implemented exactly, not approximately: `_fairness_scale()` derives a multiplier from the grid that exceeds the worst possible total preference cost (1137 vs 1136 on this quarter), so one unit of deviation outweighs every preference combined. Among equally fair schedules the solver picks the one people asked for. Built and passing. |
| Preference priority: weekday > weekend day > weekend time > desk (2026-08-26) | Shivam's ranking of what he would want as an RA. Encoded so the worst miss in each category outranks the worst in the next: 5th-choice weekday 3, wrong weekend day 2, wrong weekend time 1. Right-day-wrong-time therefore beats wrong-day-right-time. **Fall checkbox only.** From Winter 2027 the form ranks the six weekend slots 1-6 and the cost is steps from the asked-for slot on either grid (2026-11-25); a 6th weekend choice (5) costs one more than a 5th weekday choice (4). |
| Desk preference is never priced in the solver at all (2026-08-26) | Not "weighted last", absent. Shivam: honour day and time over location. Someone asking for Game Room AND Morning wants something that does not exist, since morning shifts have no game room; leaving desk out of the model means the day/time wish wins by construction rather than by weight. Cost: 34 of 62 seats on game-room-less shifts go to people who wanted a game room, and that is accepted. |
| ~~Rank cost curve is 0 / 0 / 1 / 2 / 3 (2026-08-26)~~ **REVERSED 2026-11-22: 0 / 1 / 2 / 3 / 4, one point per step from 1st** | Was: the form's "first or second" promise read as indifference. On Fall data the solver handed out 2nd choices freely (49% of weekday seats were 1st choice). Making 2nd cost one point lifted that to 77% with fairness unchanged. The old curve is kept as `RANK_COST_TODAY` for replays. Weekend ranks (Winter grid, 1-6) mirror it: 0/1/2/3/4/5. |
| Desk preference lives in `roles.py`, not the solver (2026-08-26) | The solver never learns desks exist; it picks people and `roles.py` seats them. Putting FD/GR in the model would mean splitting every shift's seats and roughly doubling it, for a preference that cannot affect fairness or feasibility either way. |
| Weekday preferences are a SOFT pull toward the ranked day, never a hard recurring assignment (2026-08-26) | Shivam's call. The 08-24 checkpoint recorded "each RA gets ONE recurring weekday" as confirmed; the solver never implemented it, and last year's real schedule shows the leads do not work that way either. Only 5 of 44 RAs had a single weekday; the median RA did 62% of their weekday shifts on their most-used day. A hard constraint would be less like their real schedule and could make a quarter infeasible. **Built 2026-08-26.** |
| Targets derived from seat count each run, never hardcoded | `compute_targets()` re-derives 11/10/5 from the grid and roster, so a changed grid cannot silently invalidate the numbers. |
| Solver first, UI is v2, and the UI is probably a Google Sheet (direction changed 2026-08-28, not yet decided) | From the spec. Confirmed 2026-08-26: the ADRLs and duty leads WILL operate the tool themselves. On 08-28 Shivam said a website will be hard to run (hosting, FERPA, sign-in, succession) and wants v2 integrated with Google Sheets instead. Discussion first, task #6. The solver stays Python on a laptop either way. |
| CP-SAT over a hand-rolled greedy loop | The hard rules (availability, composition, pairing, back-to-back) are what a CP solver enforces natively, in less code than a greedy loop that backtracks. |
| ~~Fairness = total shift count only~~ **REVERSED 2026-08-26** | Was: no weekend-load term, because an RA who can do no weekdays legitimately ends up weekend-heavy. Shivam reversed it: the weekday/weekend MIX should be equitable too. The original reason still holds and is why the new term is soft, not hard. |
| Spread across the quarter: at most one shift per person per calendar week, soft (2026-08-27) | One of last year's leads' unwritten rules, from the conversation in `references/`: nobody done by week four while someone else only works the last few weeks. Shivam asked for it by name. Soft, because the pairing block front-loads experienced RAs by rule. Sits under balance, above preferences. A/B on the real grid: person-weeks with 2+ shifts 99 -> 13, busiest week 4 -> 2, fairness unchanged, preference cost 0 -> 1. **Side effect, accepted by Shivam 2026-08-27:** a one-per-week cap also delivers the leads' other two habits (one weekday per week; no weekday plus weekend in the same week) wherever it holds. He kept the cap over a per-period spread that would have left those two alone. |
| Weekday/weekend balance is a soft goal, derived from the grid (2026-08-26) | Ideal split = tier target x the grid's weekday share. This quarter is 240 of 448 seats = 53.6%, giving LRA 3/2, returner 5/5, new 6/5. Shivam's own example ("10 shifts should be 5 and 5") is exactly what falls out for a returner. Sits ABOVE preferences: equity outranks preference. Measured cost on the real grid: none. |
| Weekday end-times ignored in v1 | From the spec. Redundant with the ranking matrix, and they are the messiest free text on the form. |

---

## The measured facts

**Current grid (Winter 2027, "Winter Template" tab, read 2026-11-25): 119 shifts, 388 seats, 2027-01-04 to 2027-03-21**, after 2 holiday rows and the 6 volunteer shifts on Jan 2-3 leave the solver. No returners-only or pairing block. Targets 10 / 9 / 5. Fall 2026 was 136 shifts / 440 seats (later 148 / 480 in the leads' file (4)). `compute_targets()` and `_weekday_share()` re-derive from whatever grid is loaded. **Always run against the leads' latest file, never a cached copy.**

**Watch out when A/B testing the objective:** the first comparison was invalid because the balance feature has TWO terms (a worst-case and a sum) and only one was being switched off. Both weights are now named constants (`W_MAXIMB`, `W_IMBSUM`) so an off switch is really off.

Every measurement behind the standing decisions (grid as first measured, roster, proven runs, last year's replay, the A/B tests for spread, balance, preferences, desk seating, weekday concentration, feasibility margin) lives in [documents/measured-facts.md](documents/measured-facts.md). Read it before tuning a weight or reopening a number.

---

## The form as shipped

The Fall 2026 form, page by page, with what the first real responses showed: [documents/fall-2026-form.md](documents/fall-2026-form.md). What the parser needs from any version of the form is the keyword table in `parse_form.py` (`COLUMN_KEYS`) plus five ranking columns ending `[Monday]`..`[Friday]`, and for the weekend either six columns ending `[Saturday Morning]`..`[Sunday Evening]` (Winter 2027 grid) or the Fall checkbox column. Verified against the live Winter export 2026-11-25.

---

## Stack

```
Python 3.11+        (3.13 on Shivam's machine; tomllib for quarter.toml needs 3.11)
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
| `quarter.toml` | **The one file an operator edits between quarters** (2026-11-25): quarter name, the two workbook tab names, the returners-only and pairing end dates (a line left out = no such block), and the dates the leads staff themselves. Plain dates, no quotes. |
| `ra_scheduler/quarter.py` | Reads `quarter.toml` once at import, validates it with plain-English errors (unknown key, quoted date, pairing before returners-only, duplicate leads-fill date). `models.py` takes its dates from here. |
| `ra_scheduler/models.py` | Every rule constant: tiers, block logic, staffing shapes, target math. Nothing is defined twice. The per-quarter dates come from `quarter.toml`. |
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
| `tests/test_quarter.py` | Unit tests on `quarter.toml` parsing and its refusals. No disk, no ortools. |
| `references/` | **Local only, gitignored.** Source material with real names in it: the conversation with last year's duty leads about how they built the schedule by hand, and the Apps Script they used for swaps. Read it, quote it by role, never commit it. |
| `documents/how-the-pipeline-works.md` | Plain-language walkthrough of every module, written for a non-technical reader. Published as an artifact too; keep the two in step. |

---

## Repo-specific notes

- **Where the code lives:** `ssinghal732/ra-scheduler` (private), created 2026-08-24, first commit `28959ca`. This working copy at `~/src/Technical-Projects/RA-Scheduler/` is the repo, not a mirror. The earlier copy under `ssinghal732/AICC` at `technical-projects/ra-scheduler/code/` (`6f792fc`) is now history; the v1 spec still sits beside it at `../ra-scheduler-v1-spec.md` (`06e5cde`, 2026-07-12).
- **Private was chosen because it is the reversible direction.** Private can become public later; the reverse leaves the history exposed. Flipping it is Shivam's call.
- **Code yes, docs yes, data never.** Changed 2026-08-26 by Shivam, overriding the global rule that operator docs stay out of a repo. CLAUDE.md, NOW.md, and CHANGELOG.md are now tracked and pushed, so this repo carries its own context and a fresh session finds everything in one place. The condition attached: **no real names of other people in any of them.** Shivam's own name is fine and he wants it on the product documents as author (2026-08-27). Everyone else is referred to by role, because `git push` is permanent and stripping a name later means rewriting history, not editing a file.
- **Data still never enters the repo.** The real grid, the availability export, and any filled schedule carry real RA names. `.gitignore` blocks `*.xlsx` / `*.csv` / `*.json` so that cannot happen by accident.
- **People:** the ADRL supervising this project is also a duty lead; two RA duty leads run the schedule day to day. All of them will operate the tool themselves (confirmed 2026-08-26), which is what makes the v2 UI real. Names are deliberately kept out of this repo.
- **The parser is built** (`ccbbf80`, 2026-08-26) and has now run on all 43 real responses (2026-08-28): 0 stops, OPTIMAL, 0 violations, `fall_2026.xlsx` written. Run: `python run_pipeline.py --grid <grid> --roster <roster> --availability <export> --out <out>`; the two tab names default from `quarter.toml` (`--grid-sheet` / `--sheet` override them). It STOPs until every roster member has submitted. **The leads' exports land as `(2)`, `(3)` in Downloads; `ls -t` before running.**
- **The form-fix thread is closed.** Read the shipped form 2026-08-26 (`~/Downloads/DutyAvailForm_FA26.pdf`, 7 pages). See "The form as shipped" below for what landed and what the parser faces. **The real deadline is Thursday 08/27 at 11:59 pm**, not 08/28: responses are still arriving through Thursday evening, so a complete set does not exist until Friday morning.
- **Time category:** `RA_Scheduler`, short code `RAS`, in `technical-projects`. Created 2026-08-26. Log with `time_log(category='RAS', ...)`. Ask Shivam for the hours; never guess them.

---

## Tracking docs

| File | What lives there |
|---|---|
| [NOW.md](NOW.md) | Active, next, blocked, open questions. Update when priorities shift. |
| [CHANGELOG.md](CHANGELOG.md) | Dated record of what shipped. |
| `../ra-scheduler-v1-spec.md` | The v1 spec: problem, domain model, constraints, build order. Update when a decision changes it. |
