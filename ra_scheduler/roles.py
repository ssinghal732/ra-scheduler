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

Desk placement (Front Desk vs Game Room) is the one preference handled HERE
rather than in the solver: the solver never learns that desks exist, it just
picks people. Within whatever people it picked, this module seats those who
asked for a desk at that desk where it can, and randomizes the rest. It can
never change WHO works, only where they stand, so it cannot affect fairness or
feasibility. Ties and impossible cases fall back to random.
"""
from __future__ import annotations

import random

from .models import BLOCK_PAIRING, FRONT_DESK, GAME_ROOM, RA, AvailabilityData, ShiftInstance

FD_P, FD_S = "Front Desk Primary", "Front Desk Secondary"
GR_P, GR_S = "Game Room Primary", "Game Room Secondary"
ROLES_4 = (FD_P, FD_S, GR_P, GR_S)
ROLES_2 = (FD_P, FD_S)


class RoleError(ValueError):
    """Raised when the selected people cannot legally fill the roles."""


def _seat_pair(pair: list[str], want: dict[str, str], rng: random.Random) -> list[str]:
    """Order a two-person pair as [front desk, game room], honouring desks asked for.

    Both wanting the same desk, or neither caring, falls through to random: there
    is no signal to break the tie with and inventing one would be a lie.
    """
    a, b = pair
    wa, wb = want.get(a, ""), want.get(b, "")
    if wa == FRONT_DESK and wb != FRONT_DESK: return [a, b]
    if wb == FRONT_DESK and wa != FRONT_DESK: return [b, a]
    if wa == GAME_ROOM and wb != GAME_ROOM:   return [b, a]
    if wb == GAME_ROOM and wa != GAME_ROOM:   return [a, b]
    out = [a, b]
    rng.shuffle(out)
    return out


def _split_desks(people: list[str], want: dict[str, str], rng: random.Random
                 ) -> tuple[list[str], list[str]]:
    """Split four people into two front-desk and two game-room, honouring asks."""
    order = people[:]
    rng.shuffle(order)                      # random baseline, then pull by preference
    fd = [p for p in order if want.get(p) == FRONT_DESK]
    gr = [p for p in order if want.get(p) == GAME_ROOM]
    spare = [p for p in order if p not in fd and p not in gr]
    while len(fd) > 2: spare.append(fd.pop())
    while len(gr) > 2: spare.append(gr.pop())
    while len(fd) < 2: fd.append(spare.pop())
    while len(gr) < 2: gr.append(spare.pop())
    return fd, gr


def assign_roles(
    shift: ShiftInstance,
    people: list[str],
    tier_of: dict[str, str],
    rng: random.Random,
    want_desk: dict[str, str] | None = None,
) -> dict[str, str]:
    """Map role name -> ra_id for one shift. Pure function; rng injected."""
    want = want_desk or {}
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
            # Primary pair = exp+new, Secondary pair = exp+new. Each pair puts one
            # person at each desk, so the only choice is which way round.
            primary = _seat_pair([experienced[0], new[0]], want, rng)
            secondary = _seat_pair([experienced[1], new[1]], want, rng)
            return {FD_P: primary[0], GR_P: primary[1], FD_S: secondary[0], GR_S: secondary[1]}
        # 2-person: the pair itself is exp+new; labels are just walk order.
        duo = [experienced[0], new[0]]
        rng.shuffle(duo)
        return {FD_P: duo[0], FD_S: duo[1]}

    if shift.seats == 4:
        fd, gr = _split_desks(people, want, rng)
        return {FD_P: fd[0], FD_S: fd[1], GR_P: gr[0], GR_S: gr[1]}
    order = people[:]
    rng.shuffle(order)                       # 2-person shifts are both front desk
    return dict(zip(ROLES_2, order))


def assign_all_roles(
    shifts: list[ShiftInstance],
    assignment: dict[int, list[str]],
    roster: list[RA],
    seed: int = 0,
    data: AvailabilityData | None = None,
) -> dict[int, dict[str, str]]:
    """Role tables for every shift. Deterministic for a given (assignment, seed)."""
    rng = random.Random(seed)
    tier_of = {ra.ra_id: ra.tier for ra in roster}
    want_desk = {ra.ra_id: data.prefs(ra.ra_id).location for ra in roster} if data else {}
    return {
        s.sid: assign_roles(s, sorted(assignment.get(s.sid, [])), tier_of, rng, want_desk)
        for s in shifts
    }
