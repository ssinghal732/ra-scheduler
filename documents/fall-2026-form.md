# The form as shipped (Fall 2026, read 2026-08-26 from `DutyAvailForm_FA26.pdf`)

Moved out of CLAUDE.md on 2026-11-22. The Winter 2027 form replaces this one; see the parser notes in CLAUDE.md for what the parser matches on.

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

