# How the pipeline works

A walkthrough of the RA duty scheduler, written to be readable by someone with no
technical background and still useful to someone who has to maintain the code.

Each section names the file it describes, so you can read this beside the source.

---

## The problem in one table

| | |
|---|---|
| **Input 1** | The duty leads' grid: which dates and shifts need staffing |
| **Input 2** | Each RA's availability: which shifts they physically can work |
| **Input 3** | The roster: who is an LRA, who is a returner, who is new |
| **Output** | The same grid, with names filled into every slot |

For Fall 2026 that meant picking 440 names across 136 shifts from 43 RAs, so that
nobody is scheduled when they can't work, the special rules hold, and the workload
comes out fair. Winter 2027 is 388 names across 119 shifts.

Ten Python files do this. They work like an assembly line, each station handing
its work to the next.

```
grid.py ────┐
            ├──> preflight.py ──> solver.py ──> roles.py ──> validate.py ──> export.py
parse_form ─┘         (warn)        (who)        (where)       (check)        (write)
   .py
(or synthetic.py, for a dry run)
```

`models.py` sits underneath all of them, and `quarter.py` feeds it this quarter's dates
from `quarter.toml`. `run_pipeline.py` sits on top, running the line.

---

## `models.py`: the rulebook

**Plain version.** Every fact about how duty scheduling works is written down here,
once. What the tiers are. When the special periods start and end. How many people
each shift needs.

**Why it's separate.** If "the pairing period ends October 18" were typed into three
files, someone would eventually change two of them. Here it's written once and every
other file asks this one.

**The dates come from `quarter.toml`.** The rules live in `models.py`; the dates they
apply to this quarter live in a small text file at the top of the repo, the one file
an operator edits between quarters. It names the two workbook tabs, the last day of
the returners-only week, the last day of the training period, and any dates the leads
staff themselves (volunteers after a break, say). A line left out means "this quarter
has none," and the solver skips every rule that hangs off it.

```toml
quarter = "Winter 2027"
grid_sheet = "Winter Template"
form_sheet = "Winter Availability"
# returners_only_through = 2026-09-13     (Fall had one; Winter does not)
# pairing_through = 2026-10-18

[[leads_fill]]
dates = [2027-01-02, 2027-01-03]
label = "Volunteers"
```

```python
STAFFING = {
    "Evening (Weekday)":  (2, 2),   # 2 front desk, 2 game room
    "Morning":            (2, 0),
    "Afternoon":          (2, 0),
    "Evening (Weekend)":  (2, 2),
}
```

**The derived targets.** `compute_targets()` works out how many shifts each tier
should get. Rather than hardcoding "new RAs get 11," it counts seats and derives it:

- Start with a baseline number B
- New RAs get B, returners get B-1, LRAs get half
- Try B = 1, 2, 3... and keep the B whose implied total lands closest to the seat
  count, over or under

Fall 2026 landed on 11 / 10 / 5; Winter 2027 on 10 / 9 / 5. If the grid changes and
there are 500 seats, the numbers recompute on their own. Nothing silently goes stale.

---

## `grid.py`: reading the duty schedule template

**Plain version.** Opens the Excel file and turns each row into a shift the program
can work with.

**What it handles:**

- Excel stores dates as numbers counted from 1899. It converts those back to real dates.
- The grid writes the week label only on the first row of each week and leaves the
  rest blank, so it carries the last-seen label forward.
- Holidays aren't a flag column. Someone typed the word "Holiday" across the name
  cells. So it checks whether the "Front Desk Primary" cell literally reads
  `Holiday`, and if so the row needs nobody.
- Some dates the leads staff themselves, by volunteers, like the first weekend back
  from a break. Those dates are listed in `quarter.toml`, and their rows are set aside
  the same way holiday rows are, with the label ("Volunteers") carried along.

**Output:** two lists. Shifts that need staffing, and the rows the solver skips, kept
aside so the exporter can put them back in the right place.

---

## `parse_form.py`: reading the form

**Plain version.** Opens the Google Form response sheet and the roster, and turns
them into the one object everything downstream consumes.

Two inputs. The roster is three columns: email, name, tier. The form export is one
row per submission, one column per question.

**How it finds columns.** Google Forms uses the entire question text as the column
header, a paragraph long. Matching that exactly would break the moment anyone edited
a word. So each field is found by a short distinctive keyword instead, and the parser
prints what it matched:

```
[parse]  email           <- Email Address
[parse]  weekday ranks   <- 5 columns ending [Monday] .. [Friday]
[parse]  all_dates       <- Please identify ALL of the DATES you CANNOT do...
```

If it matched the wrong thing you see it here, not three steps later as empty
availability.

**How it matches a person to the roster.** By email first. If the email is not on the
roster, by exact full name; if that fails, by a first name that matches exactly one
roster entry. If nothing matches, the run stops. People turned out to have more than
one ucsd.edu address, which is why email alone wasn't enough. The report says how
many people joined by name rather than email, without listing them.

**Availability is built by subtraction.** Start with every shift in the quarter. Take
away weekday evenings on any day marked "Class Conflict/Unavailable". Take away any
weekend slot marked unavailable in the weekend grid (Saturday Morning, Sunday Evening,
and so on). Take away every shift on any date in the blackout list. Whatever is left
is what the person can work.

**Two ranking grids.** Weekdays are ranked 1 to 5, Monday to Friday. From Winter 2027
the six weekend slots are ranked 1 to 6 too. The parser finds the grid columns by
the `[Monday]` or `[Saturday Morning]` ending on each header, so the question text
can change without breaking anything. The Fall form had a checkbox instead of the
weekend grid; the parser still reads that shape, so Fall data can be replayed.

**Dates are read off the front of each entry.** `12/9 (Final)`, `12/09(Final)`, and
`12/9 - Final` all read as December 9. `Oct. 17 (Concert)` reads as nothing, and is
reported for a human to fix. The parser never guesses at a date.

**It flags what looks odd.** Three tiers. STOP halts before the solver runs: someone
on the roster hasn't submitted, ranked the same number twice in a grid, marked every
weekday as a conflict, or marked every weekend slot unavailable. FLAG prints and
continues: a weekend slot marked unavailable (the leads ask for proof), a duplicate
submission, more than ten blackout dates, a date it couldn't read. READ prints every
free-text concerns box in full, because last year about one in eight of those held a
constraint no parser could have seen.

---

## `synthetic.py`: stand-in availability

**Plain version.** Invents 43 RAs and randomly decides what each can work, so the
rest of the pipeline had something to run on before real form data existed.

**The design point.** This is a placeholder built so its replacement drops in
cleanly. The real form parser reads the Google Form export and produces the exact
same shape of data. Nothing else in the pipeline changes. One module gets swapped;
the other seven don't notice.

```python
AvailabilityData(
    roster = [list of RAs with their tier],
    available = {"R07": {"2026-10-14|Evening (Weekday)", ...}},
    blackout_dates = {"R07": {date(2026, 11, 3), ...}},
)
```

That `"2026-10-14|Evening (Weekday)"` string is a **key**: a date and a shift name
glued together, used as the label for one specific shift. The parser and the grid
have to spell it identically or nothing matches.

---

## `preflight.py`: the early warning

**Plain version.** Before the solver runs, count things. Are enough people free for
each shift? Is anyone available for nothing at all? Do the availability labels match
real shifts?

**Why it exists.** When a constraint solver can't satisfy the rules, it reports
`INFEASIBLE` and stops. That single word is all you get. The solver did prove that
no valid schedule exists, but the proof is a search tree, and there's no way to turn
"I exhausted the search space" back into "September 9 is one person short."

Preflight does plain arithmetic first, and prints problems with dates attached.

**Three kinds of check:**

1. **Per shift.** Eligible people free, versus seats to fill.
2. **Per block, split by tier.** The pairing period needs 72 seats filled
   specifically by experienced RAs. Counting the whole pool would hide a shortage
   inside one tier.
3. **Data faults.** An RA available for nothing all quarter. Availability keys
   matching no shift in the grid.

**What it can and can't claim.** It tests *necessary* conditions: if a check fails,
the solve definitely fails. Passing does not guarantee the solve succeeds, because
counting per shift misses interaction. If one RA is the only person free for two
different shifts, each shift looks fine alone and the solve still fails.

It never blocks the run. The solver stays the authority.

---

## `solver.py`: the actual brain

**Plain version.** It considers every combination of who could work what, and finds
one that breaks no rules and spreads the work fairly.

### Variables as light switches

For every possible pairing of one RA and one shift, the program creates a switch
that's either on or off.

> Switch `x[R07, shift 42]` = ON means R07 works shift 42.

43 RAs across 136 shifts would be 5,848 switches. It's fewer, because of this:

```python
if s.key in data.available.get(ra.ra_id, ()):
    x[(ra.ra_id, s.sid)] = m.NewBoolVar(...)
```

A switch is only created if the RA is available. If R07 can't work Tuesdays, no
switch exists for R07 on any Tuesday shift. There's nothing to turn off. Availability
is enforced by the switch never being built, which is the cleanest way to make
something impossible.

### Hard rules

Facts the solver isn't allowed to break. Each is arithmetic on the switches.

**Every shift gets exactly the right number of people:**
```python
m.Add(sum(vars_for(s)) == s.seats)
```
Add up every switch for this shift. That total must equal the seats.

**No new RAs during the returners-only week:**
```python
m.Add(sum(vars_for(s, lambda rid: tier[rid] == TIER_NEW)) == 0)
```
Add up only the switches belonging to new RAs. That total must be zero.

**Pairing shifts are half experienced:**
```python
m.Add(sum(vars_for(s, lambda rid: rid in experienced)) == s.seats // 2)
```

**Nobody works two shifts back to back on the same day:**
```python
m.Add(day_shifts[a] + day_shifts[b] <= 1)
```
Two switches, at most one on. Morning and Afternoon can't both be on. Morning and
Evening can, since there's a gap between them.

The returners-only and pairing rules only exist for shifts inside those blocks, and
the blocks come from the dates in `quarter.toml`. Winter 2027 has neither, so for
Winter those two rules are never written down at all.

The solver reports failure before it breaks any of these.

### Soft goals

Fairness is not a hard rule. A hard cap could declare the whole quarter impossible
over one extra shift. Instead the solver gets a score to minimize, and unfairness
adds to the score.

```python
m.Minimize(
    scale * (
        5000 * sum(training_shortfalls)       # new RAs short on training shifts
        + 1000 * max_deviation                # the worst-off person's distance from target
        + 100 * max_imbalance                 # the worst weekday/weekend mix
        + sum(individual_deviations)          # everyone's distance from target (LRAs x3)
        + sum(mix_imbalances)                 # everyone's weekday/weekend mix
        + 3 * sum(shifts_beyond_one_per_week) # spread across the quarter
    )
    + preference_misses                       # the tiebreaker
)
```

| Weight | What it costs |
|---|---|
| 5000 | Leaving one new RA short on training shifts |
| 1000 | Pushing the worst-off person one shift further from target |
| 100 | Pushing the worst weekday/weekend mix one shift further off |
| 3 | One person working twice in the same week |
| 1 | Any one person sitting off target, or off their ideal mix |

Because 5000 beats 1000 beats 100 beats 3 beats 1, the solver accepts a slightly less
balanced schedule to get a new RA their training shifts. The priority order is the
size of the numbers.

**Preferences come last, by construction.** `scale` is worked out from the grid each
run: the largest preference total any schedule could possibly have, plus one. So one
unit of unfairness always costs more than every preference in the quarter combined.
Among schedules that are equally fair, the solver picks the one people asked for.
Inside that tiebreaker, the single worst person's misses are minimized before the
total, so nobody ends up carrying everyone else's bad shifts. A 1st choice costs 0,
a 2nd costs 1, and each step further costs one more, on both the weekday and the
weekend grid.

**`max_deviation` is the minimax choice.** Before minimizing total unfairness,
it minimizes the *worst single person's* unfairness. A schedule where one person is
5 shifts off and everyone else is perfect scores worse than one where six people are
1 off. That matches how RAs actually compare with each other.

A result of `OPTIMAL` doesn't mean "good enough." It means the solver proved no
arrangement scores better.

---

## `roles.py`: sorting people into columns

**Plain version.** The solver said *who* works Tuesday. This decides which name goes
in which column.

**Why it's a separate step.** The solver picks sets of people and never thinks about
columns. That works because of one guarantee: if a pairing shift has 2 experienced
and 2 new people, a legal arrangement always exists. So this step can never fail, and
the solver never has to reason about it. Splitting "pick people" from "arrange
people" made the first problem much smaller.

**Primary and Secondary are walk times.** They're the 7:30 walk and the 9:30
walk. During the pairing period each walk pair is one experienced and one new RA, so
a trainee always walks with somebody who knows the route.

```python
primary, secondary = [experienced[0], new[0]], [experienced[1], new[1]]
```

On 2-person shifts the two labels carry no meaning at all, so the order is shuffled
deliberately:

```python
duo = [experienced[0], new[0]]
rng.shuffle(duo)
```

**Seeded randomness.** `random.Random(seed)` with the same seed produces the same
shuffle every time. Same inputs plus same seed gives the identical schedule, so a rerun
is reproducible.

---

## `validate.py`: the independent referee

**Plain version.** Re-checks every rule from scratch and lists anything wrong.

**Why it matters more than it looks.** It shares no code with the solver. It
re-derives everything from the finished assignment:

```python
for rid in who:
    if s.key not in data.available.get(rid, ()):
        errors.append(f"{s.key}: {rid} is not available")
```

If the solver had a bug and the validator reused the solver's logic, both would carry
the same bug and both would report success. Written separately, a solver bug surfaces
here as an error. It's the same reason you don't proofread your own writing by
rereading your own notes.

**The limit.** Two independent implementations catch a coding mistake. They
can't catch the same rule being misunderstood twice by the same author. Duty leads
reading real rows is still the verification that counts.

---

## `export.py`: writing the spreadsheet back

**Plain version.** Produces an Excel file in the leads' exact format, so it looks
like the file they already use.

- Duty rows, holiday rows, and leads-fill rows ("Volunteers") are merged back together
  and sorted into calendar order, with Morning before Afternoon before Evening
- The week label is written only when the week changes
- Exceptions (RAs unavailable that day) appear once per date, not on every row
- Holiday rows get a peach fill; the header is dark blue with white bold text
- Dates are formatted `MM/DD/YYYY` rather than showing Excel's raw numbers
- A second tab lists every RA's availability and preferences beside what they got,
  so "why is this person on Friday" can be answered without a rerun

None of it is clever. It matches what the leads expect so the output needs no
reformatting by hand.

---

## `run_pipeline.py`: the conductor

Runs the stations in order and prints what happened.

```
[quarter]   Winter 2027: grid tab 'Winter Template', form tab 'Winter Availability'; no returners-only week; no pairing period; 2 leads-fill date(s)
[grid]      119 shifts, 388 seats, 8 rows the solver skips (2 holiday, 6 volunteers), 2027-01-04 -> 2027-03-21
[avail]     43 RAs
[preflight] 0 blocking, 0 tight, 1 notes
[solve]     OPTIMAL, max deviation 1
[validate]  0 hard-rule/role violations
[balance]   worst weekday/weekend imbalance 1 shift(s); 40/43 RAs on their ideal mix
[spread]    0 shift(s) beyond one-per-person-per-week; busiest anyone gets in a single week: 1
[fairness]  LRA       target  5 -> min 5 / mean 5.0 / max 5
[prefs]     weekday shifts on a 1st or 2nd choice day: 210/212 (99%)
[export]    wrote winter_2027.xlsx
```

It stops if the parser finds a STOP, if the solve fails, and if the validator finds
anything. It never writes a file it knows is wrong.

---

## How this has been tested, and what that does not cover

Three layers, each less willing to take the previous one's word.

**Unit tests**, five files, one per tricky module. The first test in the preferences
file guards the property that fairness beats every preference combined; if it ever
fails, the tool has started trading someone's fair share for someone else's
convenience.

**The validator**, on every run, re-checking every rule against the finished schedule
with code the solver never touches.

**Rows read out of the file.** The Fall 2026 schedule was checked by opening the
output and looking: 0 new RAs in the returners-only week, 28 of 28 pairing-period
shifts mixed on both walks and both desks, all 4 holiday rows in place, 440 names
each matching a roster tier. That run was `OPTIMAL`, 0 violations, max deviation 1,
40 of 43 people on their ideal weekday/weekend mix, 88% of weekday shifts on a 1st or
2nd choice day.

What none of this covers: the same rule misunderstood the same way by the same
author, in the solver and the validator both. Duty leads reading real rows is still
the check that counts.

---

## The two ideas holding it together

**One place per fact.** Every rule lives in `models.py` and nowhere else, and every
date a rule applies to lives in `quarter.toml` and nowhere else. Changing when the
pairing period ends is one edit, and every module follows.

**The checker doesn't trust the maker.** The solver produces a schedule. A separately
written validator checks it. Then rows get read out of the finished file rather than
trusting either. Three layers, each less willing to take the previous one's word.
