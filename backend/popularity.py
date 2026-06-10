"""Deterministic match popularity — tier and short rationale string.

Tiers: "popular" / "moderate" / "standard". Triggered by phase, FIFA top-10
membership, host-nation membership, or membership in a curated set of
global-TV-draw brands. TBD knockout slots use phase-only popularity until
a feeder distribution's leader passes a 60% threshold.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, TypedDict

from backend.schema import Popularity
from backend.schema import PopularityTier as PopularityTier


class TeamInfo(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def fifa_rank(self) -> int: ...


TeamLookup = Mapping[str, TeamInfo]


HOST_NATIONS: frozenset[str] = frozenset({"USA", "MEX", "CAN"})
GLOBAL_DRAW_BRANDS: frozenset[str] = frozenset(
    {"BRA", "ARG", "FRA", "ENG", "GER", "ESP", "POR", "NED", "BEL"}
)
FEEDER_LEADER_THRESHOLD: float = 0.60

_TOP10_MAX_RANK: int = 10
_TOP25_MAX_RANK: int = 25


class FeederLeader(TypedDict):
    label: str
    leader_code: str
    leader_prob: float


_PHASE_LABEL: dict[str, str] = {
    "final": "Final",
    "semi_final": "Semi-final",
    "bronze_final": "Bronze final",
    "quarter_final": "Quarter-final",
    "round_of_16": "Round of 16",
    "round_of_32": "Round of 32",
    "group_stage": "Group stage",
    "friendly": "Friendly",
}


def _phase_inherent_popular(phase: str) -> bool:
    return phase in {"final", "semi_final", "bronze_final"}


def _phase_inherent_moderate(phase: str) -> bool:
    return phase in {"quarter_final", "round_of_16", "round_of_32"}


def _team_rank(code: str, lookup: TeamLookup) -> int | None:
    team = lookup.get(code)
    return team.fifa_rank if team else None


def _team_name(code: str, lookup: TeamLookup) -> str:
    team = lookup.get(code)
    return team.name if team else code


def _top10_codes(codes: tuple[str, ...], lookup: TeamLookup) -> list[str]:
    out: list[str] = []
    for c in codes:
        rank = _team_rank(c, lookup)
        if rank is not None and rank <= _TOP10_MAX_RANK:
            out.append(c)
    return out


def _top25_codes(codes: tuple[str, ...], lookup: TeamLookup) -> list[str]:
    out: list[str] = []
    for c in codes:
        rank = _team_rank(c, lookup)
        if rank is not None and rank <= _TOP25_MAX_RANK:
            out.append(c)
    return out


def _effective_team_codes(
    *,
    status: str,
    confirmed_team_codes: tuple[str, ...] | None,
    feeder_distributions: list[FeederLeader] | None,
) -> tuple[str, ...]:
    if status == "confirmed" and confirmed_team_codes:
        return tuple(confirmed_team_codes)
    if status == "tbd" and feeder_distributions:
        leaders: list[str] = []
        for fd in feeder_distributions:
            if fd["leader_prob"] >= FEEDER_LEADER_THRESHOLD:
                leaders.append(fd["leader_code"])
        return tuple(leaders)
    return ()


def compute_popularity(
    *,
    phase: str,
    status: str,
    confirmed_team_codes: tuple[str, ...] | None,
    feeder_distributions: list[FeederLeader] | None,
    team_lookup: TeamLookup,
) -> Popularity:
    codes = _effective_team_codes(
        status=status,
        confirmed_team_codes=confirmed_team_codes,
        feeder_distributions=feeder_distributions,
    )
    code_set = set(codes)

    if _phase_inherent_popular(phase):
        return Popularity(
            tier="popular",
            rationale=f"{_PHASE_LABEL[phase]} — knockout intensity.",
        )

    top10 = _top10_codes(codes, team_lookup)
    if top10:
        names = ", ".join(
            f"{_team_name(c, team_lookup)} (FIFA #{_team_rank(c, team_lookup)})"
            for c in top10
        )
        return Popularity(tier="popular", rationale=f"{names} draws a global audience.")

    # Host-nation and global-brand triggers fire only in group_stage. In
    # practice, all group-stage matches are confirmed (the draw is set before
    # the tournament), so TBD-status matches never reach this branch via the
    # feeder-leader path — TBD leaders only flow into the top-10 / top-25 checks.
    if phase == "group_stage":
        host_present = code_set & HOST_NATIONS
        if host_present:
            host = sorted(host_present)[0]
            return Popularity(
                tier="popular",
                rationale=f"Host-nation match ({_team_name(host, team_lookup)}).",
            )

        brand_present = code_set & GLOBAL_DRAW_BRANDS
        if brand_present:
            brand = sorted(brand_present)[0]
            return Popularity(
                tier="popular",
                rationale=f"{_team_name(brand, team_lookup)} is a global TV draw.",
            )

    if _phase_inherent_moderate(phase):
        return Popularity(
            tier="moderate",
            rationale=f"{_PHASE_LABEL[phase]} — knockout round.",
        )

    if phase == "group_stage":
        top25 = _top25_codes(codes, team_lookup)
        if top25:
            return Popularity(
                tier="moderate",
                rationale="Group stage; at least one team inside the top 25 FIFA.",
            )
        return Popularity(
            tier="standard",
            rationale="Group stage; teams outside the top 25 FIFA.",
        )

    return Popularity(tier="standard", rationale=f"{_PHASE_LABEL.get(phase, phase)}.")
