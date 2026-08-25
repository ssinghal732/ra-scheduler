"""Role slotting: turn the solver's chosen PEOPLE into named COLUMNS.

Roles per shift:
  4-person: Front Desk Primary/Secondary + Game Room Primary/Secondary
  2-person: Front Desk Primary/Secondary

Rules (confirmed with Shivam 2026-08-24):
  - Primary / Secondary = FIRST walk (7:30 PM) / SECOND walk (9:30 PM).
    They are time slots, not seniority; the walk is done by the pair together.
  - Pairing period: every walk pair must be 1 experienced + 1 new, so a trainee
    always walks with an experienced RA. 4-person shifts: Primary pair
    (FD-P + GR-P) and Secondary pair (FD-S + GR-S) each mixed. 2-person shifts:
    the two FRAs are the experienced+new pair; which one gets which label is
    arbitrary and randomized.
  - Outside the pairing period: fully randomized (seeded, so runs are reproducible).

FD vs GR is a soft preference and preferences are not in v1, so desk placement
is randomized within the constraints above.
"""
from __future__ import annotations

import random

from .models import BLOCK_PAIRING, RA, ShiftInstance

FD_P, FD_S = "Front Desk Primary", "Front Desk Secondary"
GR_P, GR_S = "Game Room Primary", "Game Room Secondary"
ROLES_4 = (FD_P, FD_S, GR_P, GR_S)
ROLES_2 = (FD_P, FD_S)


class RoleError(ValueError):
    """Raised when the selected people cannot legally fill the roles."""


def assign_roles(
    shift: ShiftInstance,
    people: list[str],
    tier_of: dict[str, str],
    rng: random.Random,
) -> dict[str, str]:
    """Map role name -> ra_id for one shift. Pure function; rng injected."""
    if len(people) != shift.seats:
        raise RoleError(f"{shift.key}: {len(people)} people for {shift.seats} seats")

    experienced = [p for p in people if tier_of[p] != "new"]
    new = [p for p in people if tier_of[p] == "new"]

    if shift.block == BLOCK_PAIRING:
        if len(experienced) != shift.seats // 2:
            raise RoleError(
                f"{shift.key}: pairing shift needs {shift.seats // 2} experienced, "
                f"got {len(experienced)}"
            )
        rng.shuffle(experienced)
        rng.shuffle(new)
        if shift.seats == 4:
            # Primary pair = exp+new, Secondary pair = exp+new; desks randomized within pairs.
            primary, secondary = [experienced[0], new[0]], [experienced[1], new[1]]
            rng.shuffle(primary)
            rng.shuffle(secondary)
            return {FD_P: primary[0], GR_P: primary[1], FD_S: secondary[0], GR_S: secondary[1]}
        # 2-person: the pair itself is exp+new; labels are just walk order.
        duo = [experienced[0], new[0]]
        rng.shuffle(duo)
        return {FD_P: duo[0], FD_S: duo[1]}

    order = people[:]
    rng.shuffle(order)
    roles = ROLES_4 if shift.seats == 4 else ROLES_2
    return dict(zip(roles, order))


def assign_all_roles(
    shifts: list[ShiftInstance],
    assignment: dict[int, list[str]],
    roster: list[RA],
    seed: int = 0,
) -> dict[int, dict[str, str]]:
    """Role tables for every shift. Deterministic for a given (assignment, seed)."""
    rng = random.Random(seed)
    tier_of = {ra.ra_id: ra.tier for ra in roster}
    return {
        s.sid: assign_roles(s, sorted(assignment.get(s.sid, [])), tier_of, rng)
        for s in shifts
    }
