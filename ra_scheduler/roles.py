"""Role slotting: turn the solver's chosen PEOPLE into named COLUMNS.

Roles per shift:
  4-person: Front Desk Primary/Secondary + Game Room Primary/Secondary
  2-person: Front Desk Primary/Secondary

Rules (confirmed with Shivam 2026-08-24, extended 2026-08-26):
  - Primary / Secondary = FIRST walk (7:30 PM) / SECOND walk (9:30 PM).
    They are time slots, not seniority; the walk is done by the pair together.
  - Pairing period: BOTH the walk and the desk shift are training, so both
    pairings must be 1 experienced + 1 new. Laid out as a grid, rows are walks
    and columns are desks, and every row and every column needs one of each:

                     FRONT DESK     GAME ROOM
        7:30 walk        E      +       N        <- walk pair mixed
        9:30 walk        N      +       E        <- walk pair mixed
                         ^              ^
                       mixed          mixed

    8 of the 24 orderings satisfy that, and one always exists for 2 experienced
    plus 2 new, so this can never fail. 2-person shifts: the two FRAs are the
    experienced+new pair and they are both the walk pair and the desk pair, so
    it holds automatically; the label order is arbitrary and randomized.
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
from itertools import permutations

from .models import BLOCK_PAIRING, FRONT_DESK, GAME_ROOM, RA, AvailabilityData, ShiftInstance

FD_P, FD_S = "Front Desk Primary", "Front Desk Secondary"
GR_P, GR_S = "Game Room Primary", "Game Room Secondary"
ROLES_4 = (FD_P, FD_S, GR_P, GR_S)
ROLES_2 = (FD_P, FD_S)


class RoleError(ValueError):
    """Raised when the selected people cannot legally fill the roles."""


def _trains_everyone(table: dict[str, str], tier_of: dict[str, str]) -> bool:
    """True when both walk pairs AND both desk pairs are 1 experienced + 1 new."""
    pairs = ((FD_P, GR_P), (FD_S, GR_S),    # the two walks
             (FD_P, FD_S), (GR_P, GR_S))    # the two desks
    return all(sum(1 for r in pair if tier_of[table[r]] == "new") == 1 for pair in pairs)


def _desk_score(table: dict[str, str], want: dict[str, str]) -> int:
    """How many people are standing at the desk they asked for."""
    return sum(1 for role, rid in table.items()
               if want.get(rid) and (want[rid] == FRONT_DESK) == role.startswith("Front"))


def _pair_score(a: str, b: str, want: dict[str, str]) -> int:
    """How many of two people can get the desk they asked for, best orientation."""
    wa, wb = want.get(a, ""), want.get(b, "")
    return max((wa == FRONT_DESK) + (wb == GAME_ROOM),
               (wa == GAME_ROOM) + (wb == FRONT_DESK))


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
            # Every arrangement that trains everyone, then the one seating the
            # most people at the desk they asked for. Shuffled first so ties
            # break randomly: none of these labels carries meaning.
            valid = []
            for order in permutations(experienced + new):
                table = dict(zip(ROLES_4, order))
                if _trains_everyone(table, tier_of):
                    valid.append(table)
            rng.shuffle(valid)
            return max(valid, key=lambda tb: _desk_score(tb, want))

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
