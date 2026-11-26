# The measured facts

Moved out of CLAUDE.md on 2026-11-22 so a session loads it only when tuning. Everything below is as it was written, newest grid first.

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

**Spread across the quarter, A/B measured 2026-08-27 on the current grid.** Without the term: 99 person-weeks carrying 2+ shifts, one person with 4 in a week, some RAs 80% done by week 4 and others not until the last week. With it: 13, 2, and everyone's 80% mark between weeks 5 and 12. Max deviation unchanged, weekday and weekend preferences unchanged, preference cost 0 -> 1.

**Weekday/weekend balance, A/B measured 2026-08-26 on the real grid, same inputs.** RAs on their ideal mix 12/43 -> 38/43; worst imbalance 4 shifts -> 1. Max deviation unchanged at 1, weekday preference unchanged at 99%, weekend unchanged at 100%. **It cost nothing.** The prediction that preferences would drop was wrong: the solver already had many equally-optimal schedules and was picking among them arbitrarily, so the balance term selected a better one from the same set. The 5 RAs left at +1 are forced arithmetic, not a miss: the ideals sum to 235 against 240 weekday seats.

**Watch out when A/B testing the objective:** the first comparison was invalid because the balance feature has TWO terms (a worst-case and a sum) and only one was being switched off. Both weights are now named constants (`W_MAXIMB`, `W_IMBSUM`) so an off switch is really off.

**Preferences, measured 2026-08-26 on the real grid with synthetic preferences.** 237 of 240 weekday shifts landed on a 1st or 2nd choice day (99%); 41 of 43 RAs got 100% of theirs. Every weekend shift matched both the day and time asked for (188/188). Desks 212/275 (77%), lower because a pairing shift puts one person at each desk and both may want the same one. Fairness unchanged: max deviation 1, LRA all 5. Total preference cost 3.

**Desk seating, examined 2026-08-26.** 78% overall (79% before desk-pair training was enforced), and the remaining misses are mostly not fixable in `roles.py`: 34 of 57 land on weekend Morning/Afternoon shifts that have no game room at all, so the person was already assigned there before slotting saw them. Pairing shifts run 90%, normal 4-person shifts 89%. The greedy split was measured and is already optimal; the win came from choosing WHICH experienced RA pairs with WHICH new RA, which was previously left to a shuffled index and is worth 8 seats.

**Shivam's read was right:** there is enough capacity that fairness and preferences barely conflict. Whether that holds on real rankings depends on how lopsided they are, which the synthetic distribution cannot tell us.

**Weekday concentration, measured 2026-08-26.** Last year by hand: median RA did 62% of their weekday evenings on their most-used day, 23 of 42 at 60%+, only 5 of 44 on a single weekday. Our solver: median 50%, which is what scattering across free days produces.

**62% is a benchmark, not a target** (Shivam pushed on this, correctly). The grid holds 48 weekday-evening seats on each of the five days, 240 total, 5.6 per RA across 43 RAs. Spread 43 people evenly over 5 days and each day's 48 seats hold exactly 5.6 shifts per person, so 100% concentration is mathematically possible with evenly-spread rankings. What actually caps it is how lopsided the real rankings are, plus availability and the differing tier loads. Tune the weight up against real data and measure where fairness starts to give; do not code a target number.


**Feasibility margin worth knowing:** the returners-only week is 32 seats over 17 experienced RAs, about 1.9 shifts each. Comfortable with generous availability; the first thing to re-check on real data.
