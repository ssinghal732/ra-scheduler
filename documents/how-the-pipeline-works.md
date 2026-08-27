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

For Fall 2026 that means picking 448 names across 138 shifts from 43 RAs, so that
nobody is scheduled when they can't work, the special rules hold, and the workload
comes out fair.

Nine Python files do this. They work like an assembly line, each station handing
its work to the next.

```
grid.py ────┐
            ├──> preflight.py ──> solver.py ──> roles.py ──> validate.py ──> export.py
parse_form ─┘         (warn)        (who)        (where)       (check)        (write)
   .py
(or synthetic.py, for a dry run)
```

`models.py` sits underneath all of them. `run_pipeline.py` sits on top, running the line.

---

## `models.py` — the rulebook

**Plain version.** Every fact about how duty scheduling works is written down here,
once. What the tiers are. When the special periods start and end. How many people
each shift needs.

**Why it's separate.** If "the pairing period ends October 18" were typed into three
files, someone would eventually change two of them. Here it's written once and every
other file asks this one.

```python
RETURNERS_ONLY_END = date(2026, 9, 13)
PAIRING_END = date(2026, 10, 18)

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
- Try B = 1, 2, 3... until the implied total would overshoot the seat count
- The last B that fits is the answer

For this quarter that lands on 11 / 10 / 5. If the grid changes next year and there
are 500 seats, the numbers recompute on their own. Nothing silently goes stale.

---

## `grid.py` — reading the duty schedule template

**Plain version.** Opens the Excel file and turns each row into a shift the program
can work with.

**What it handles:**

- Excel stores dates as numbers counted from 1899. It converts those back to real dates.
- The grid writes the week label only on the first row of each week and leaves the
  rest blank, so it carries the last-seen label forward.
- Holidays aren't a flag column. Someone typed the word "Holiday" across the name
  cells. So it checks whether the "Front Desk Primary" cell literally reads
  `Holiday`, and if so the row needs nobody.

**Output:** two lists. Shifts that need staffing, and holiday rows kept aside so the
exporter can put them back in the right place.

---

## `parse_form.py` — reading the form

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
roster entry. Each fallback is flagged, because it means the roster has the wrong
email for someone and should be fixed. If nothing matches, the run stops. People turned
out to have more than one ucsd.edu address, which is why email alone was not enough.

**Availability is built by subtraction.** Start with every shift in the quarter. Take
away weekday evenings on any day marked "Class Conflict/Unavailable". Take away every
shift on any date in the blackout list. Whatever is left is what the person can work.

**Dates are read off the front of each entry.** `12/9 (Final)`, `12/09(Final)`, and
`12/9 - Final` all read as December 9. `Oct. 17 (Concert)` reads as nothing, and is
reported for a human to fix. The parser never guesses at a date.

**It flags what looks odd.** Three tiers. STOP halts before the solver runs: someone
on the roster has not submitted, or marked every weekday as a conflict. FLAG prints
and continues: a duplicate submission, more than ten blackout dates, a date it could
not read. READ prints every free-text concerns box in full, because last year about
one in eight of those held a real constraint that no parser could have seen.

---

## `synthetic.py` — stand-in availability

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

## `preflight.py` — the early warning

**Plain version.** Before the solver runs, count things. Are enough people free for
each shift? Is anyone available for nothing at all? Do the availability labels match
real shifts?

**Why it exists.** When a constraint solver can't satisfy the rules, it reports
`INFEASIBLE` and stops. That single word is all you get. The solver genuinely proved
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

## `solver.py` — the actual brain

**Plain version.** It considers every combination of who could work what, and finds
one that breaks no rules and spreads the work fairly.

### Variables as light switches

For every possible pairing of one RA and one shift, the program creates a switch
that's either on or off.

> Switch `x[R07, shift 42]` = ON means R07 works shift 42.

43 RAs across 138 shifts would be 5,934 switches. It's fewer, because of this:

```python
if s.key in data.available.get(ra.ra_id, ()):
    x[(ra.ra_id, s.sid)] = m.NewBoolVar(...)
```

A switch is only created if the RA is available. If R07 can't work Tuesdays, no
switch exists for R07 on any Tuesday shift. It isn't turned off, it doesn't exist.
Availability isn't enforced as a rule; it's enforced by the switch never being built.
That's the cleanest way to make something impossible.

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

The solver reports failure before it breaks any of these.

### Soft goals

Fairness is not a hard rule. A hard cap could declare the whole quarter impossible
over one extra shift. Instead the solver gets a score to minimize, and unfairness
adds to the score.

```python
m.Minimize(
    5000 * sum(training_shortfalls)   # priority 1
    + 1000 * max_deviation            # priority 2
    + sum(individual_deviations)      # priority 3
)
```

| Weight | What it costs |
|---|---|
| 5000 | Leaving one new RA short on training shifts |
| 1000 | Pushing the worst-off person one shift further from target |
| 1 | Any one person sitting off target |

Because 5000 beats 1000 beats 1, the solver accepts a slightly less balanced schedule
to get a new RA their training shifts. The priority order isn't code, it's the size
of the numbers.

**`max_deviation` is the minimax choice.** Rather than minimizing total unfairness,
it minimizes the *worst single person's* unfairness. A schedule where one person is
5 shifts off and everyone else is perfect scores worse than one where six people are
1 off. That matches how RAs actually compare with each other.

A result of `OPTIMAL` doesn't mean "good enough." It means the solver proved no
arrangement scores better.

---

## `roles.py` — sorting people into columns

**Plain version.** The solver said *who* works Tuesday. This decides which name goes
in which column.

**Why it's a separate step.** The solver picks sets of people and never thinks about
columns. That works because of one guarantee: if a pairing shift has 2 experienced
and 2 new people, a legal arrangement always exists. So this step can never fail, and
the solver never has to reason about it. Splitting "pick people" from "arrange
people" made the first problem much smaller.

**Primary and Secondary are times, not ranks.** They're the 7:30 walk and the 9:30
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
shuffle every time. Same inputs plus same seed gives the identical schedule. Reruns
are reproducible, not a fresh roll of the dice.

---

## `validate.py` — the independent referee

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

**The honest limit.** Two independent implementations catch a coding mistake. They
can't catch the same rule being misunderstood twice by the same author. Duty leads
reading real rows is still the verification that counts.

---

## `export.py` — writing the spreadsheet back

**Plain version.** Produces an Excel file in the leads' exact format, so it looks
like the file they already use.

- Duty rows and holiday rows are merged back together and sorted into calendar
  order, with Morning before Afternoon before Evening
- The week label is written only when the week changes
- Exceptions (RAs unavailable that day) appear once per date, not on every row
- Holiday rows get a peach fill; the header is dark blue with white bold text
- Dates are formatted `MM/DD/YYYY` rather than showing Excel's raw numbers

None of it is clever. It matches what the leads expect so the output needs no
reformatting by hand.

---

## `run_pipeline.py` — the conductor

Runs the stations in order and prints what happened.

```
[grid]      138 shifts, 448 seats, 4 holiday rows
[avail]     43 RAs
[preflight] 0 blocking, 0 tight, 4 notes
[solve]     OPTIMAL, max deviation 1
[validate]  0 hard-rule/role violations
[fairness]  LRA 5/5.0/5 · returner 10/10.1/11 · new 11/11.2/12
[export]    wrote filled.xlsx
```

It stops if the solve fails, and stops if the validator finds anything. It never
writes a file it knows is wrong.

---

## How this has been tested, and what that does not cover

The pipeline has been run end to end against a **generated stand-in grid**: an Excel
file built to the same dates, shift names, and column headers as the real one, with
no names in it.

That stand-in was written by reading `grid.py` and matching what it expects. So it
proves nothing about `grid.py` itself, which is circular. It does genuinely exercise
everything after `grid.py`, because the solver, role assignment, validator, and
exporter have no idea where the shift list came from. They receive a list of shifts
and behave identically whether that list came from a real file or a fake one.

An analogy: testing a coffee machine with beans ground to exactly the size the manual
specifies proves the machine brews. It doesn't prove it handles the beans the roaster
actually sells.

Results from that run: 138 shifts, 448 seats, 4 holiday rows, `OPTIMAL` in 27
seconds, 0 violations, max deviation 1. Checked by reading rows back out of the
output file rather than trusting the validator: 0 new RAs seated in the
returners-only week, 28 of 28 pairing-period evening shifts with both walk pairs
mixed, all 4 holiday rows preserved.

---

## The two ideas holding it together

**One place per fact.** Every rule lives in `models.py` and nowhere else. Changing
when the pairing period ends is one edit, and every module follows.

**The checker doesn't trust the maker.** The solver produces a schedule. A separately
written validator checks it. Then rows get read out of the finished file rather than
trusting either. Three layers, each less willing to take the previous one's word.
