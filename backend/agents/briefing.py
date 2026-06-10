"""Briefing agent — produces a Brief JSON for one match."""

from __future__ import annotations

from pathlib import Path

from backend.agents.client import AgentClient
from backend.agents.prompts import build_briefing_prefix
from backend.schema import Brief, MatchObject, Status


def build_match_user_message(match: MatchObject) -> str:
    """Construct the variable per-match suffix for the briefing prompt."""
    lines: list[str] = []
    lines.append(f"MATCH ID: {match.id}")
    lines.append(f"KICKOFF: {match.kickoff_local} (local) / {match.kickoff_utc} (UTC)")
    lines.append(f"HOST CITY: {match.host_city}")
    lines.append(f"VENUE: {match.venue}")
    lines.append(f"PHASE: {match.phase.value}")
    lines.append(f"STATUS: {match.status.value}")
    lines.append(f"POPULARITY (deterministic): {match.popularity.tier}")
    lines.append(f"POPULARITY RATIONALE: {match.popularity.rationale}")
    lines.append(f"CONFIDENCE: {match.confidence}")
    if match.decision_date:
        lines.append(f"DECISION DATE: {match.decision_date} (in {match.days_to_decision} days)")

    if match.status == Status.CONFIRMED and match.teams.confirmed:
        lines.append("")
        lines.append("CONFIRMED TEAMS:")
        for t in match.teams.confirmed:
            lines.append(f"  - {t.code} ({t.name}, FIFA rank {t.fifa_rank})")

    if match.status == Status.TBD and match.teams.feeder_distributions:
        lines.append("")
        lines.append("PER-FEEDER TEAM DISTRIBUTIONS (primary scenario signal):")
        for fd in match.teams.feeder_distributions:
            lines.append(f"  {fd.label}:")
            for team in fd.teams[:6]:
                lines.append(f"    - {team.code} ({team.name}): {team.probability:.1%}")

    if match.status == Status.TBD and match.teams.tbd_scenarios:
        lines.append("")
        lines.append("TOP-3 CROSS-PRODUCT MATCHUPS (supporting detail):")
        for s in match.teams.tbd_scenarios:
            line = (
                f"  rank{s.rank}: {s.team_a.code} vs {s.team_b.code}"
                f"  p={s.probability:.3f}  Δ={s.delta_pp:+.2f}pp"
            )
            lines.append(line)

    lines.append("")
    lines.append(
        "Produce the brief now as a single JSON object matching the Brief schema."
        " No prose, no fences."
    )
    return "\n".join(lines)


def run_briefing(
    *,
    match: MatchObject,
    client: AgentClient,
    knowledge_dir: Path,
) -> Brief:
    prefix = build_briefing_prefix(knowledge_dir=knowledge_dir)
    user_message = build_match_user_message(match)
    return client.call_structured(
        system_prefix=prefix,
        user_message=user_message,
        response_model=Brief,
    )
