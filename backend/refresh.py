"""CLI entrypoint and orchestration for the deterministic refresh pipeline."""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from backend.agents.briefing import run_briefing
from backend.agents.client import AgentClient, AgentSchemaError
from backend.agents.prompts import PROMPT_VERSION
from backend.bracket import (
    Bracket,
    FeederBestThirdPlace,
    FeederGroupRunnerUp,
    FeederGroupWinner,
    FeederQfWinner,
    FeederR32Winner,
    FeederSfLoser,
    load_bracket,
)
from backend.bracket_simulation import SlotMatchupCounts, simulate_bracket
from backend.confidence import grade_confidence
from backend.fixtures import FixtureMatch, load_fixtures
from backend.groups import derive_group_probs
from backend.knowledge import KnowledgeBase, load_knowledge
from backend.match_prediction import predict_from_fifa_rank
from backend.odds_client import NormalizedEvent, OddsApiError, OddsClient, normalize_event
from backend.popularity import FeederLeader, compute_popularity
from backend.probabilities import GroupAdvanceProbs, Top5Result, compute_top5_for_slot
from backend.schema import (
    ConfirmedTeam,
    DataFreshness,
    FeederDistribution,
    FeederTeam,
    MatchesFile,
    MatchObject,
    Phase,
    Status,
    TbdScenario,
    TeamRef,
    TeamsBlock,
    TournamentPhase,
)
from backend.signature import compute_signature
from backend.writer import load_previous, write_matches_file

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "site" / "data" / "matches.json"
DEFAULT_KNOWLEDGE = REPO_ROOT / "knowledge"


def _phase_to_tournament_phase(phase_name: str) -> TournamentPhase:
    mapping = {
        "pre_tournament": TournamentPhase.PRE_TOURNAMENT,
        "group_stage": TournamentPhase.GROUP_STAGE,
        "round_of_32": TournamentPhase.ROUND_OF_32,
        "round_of_16": TournamentPhase.ROUND_OF_16,
        "quarter_finals": TournamentPhase.QUARTER_FINALS,
        "semi_finals": TournamentPhase.SEMI_FINALS,
        "finals": TournamentPhase.FINALS,
    }
    return mapping[phase_name]


GROUP_STAGE_PHASES = frozenset({"pre_tournament", "group_stage"})
KNOCKOUT_PHASES = frozenset({
    "round_of_32",
    "round_of_16",
    "quarter_finals",
    "semi_finals",
    "finals",
})


def should_run_for_cadence(cadence: str, current_phase: str) -> bool:
    """Return True if the given cron cadence should act during the given phase.

    The same refresh script is invoked from two crons:
      - group_stage cadence (every 30 min) — acts during pre_tournament + group_stage
      - knockouts cadence (every 15 min) — acts during R32 → finals

    The "off" cadence early-exits in <2 seconds with no work done.
    """
    if cadence == "group_stage":
        return current_phase in GROUP_STAGE_PHASES
    if cadence == "knockouts":
        return current_phase in KNOCKOUT_PHASES
    raise ValueError(f"unknown cadence: {cadence!r}")


def _safe_code(code: str) -> str:
    """Return code if it's a valid 3-char FIFA code, else 'TBD'."""
    if len(code) == 3:
        return code
    return "TBD"


def _build_name_to_code(kb: KnowledgeBase) -> dict[str, str]:
    """Map full team names (as Odds API returns them) → 3-letter codes."""
    return {profile.name: code for code, profile in kb.teams.items()}


def _build_confirmed_match(
    inv: FixtureMatch,
    kb: KnowledgeBase,
) -> MatchObject:
    confirmed = []
    for code in inv.confirmed_teams:
        team = kb.teams[code]
        confirmed.append(ConfirmedTeam(code=code, name=team.name, fifa_rank=team.fifa_rank))
    sig = compute_signature(
        status="confirmed",
        confirmed_team_codes=(inv.confirmed_teams[0], inv.confirmed_teams[1]),
        top1_codes=None,
        top1_probability=None,
        top5_team_codes=None,
        confidence="certain",
        prompt_version=PROMPT_VERSION,
    )
    popularity = compute_popularity(
        phase=inv.phase,
        status="confirmed",
        confirmed_team_codes=tuple(inv.confirmed_teams),
        feeder_distributions=None,
        team_lookup=kb.teams,
    )
    phase = Phase(inv.phase)
    prediction = predict_from_fifa_rank(confirmed[0], confirmed[1], phase)
    return MatchObject(
        id=inv.id,
        kickoff_utc=inv.kickoff_utc,
        kickoff_local=inv.kickoff_local,
        host_city=inv.host_city,
        venue=inv.venue,
        phase=phase,
        status=Status.CONFIRMED,
        popularity=popularity,
        confidence="certain",
        teams=TeamsBlock(confirmed=confirmed, tbd_scenarios=None),
        signature=sig,
        brief=None,
        prediction=prediction,
        decision_date=None,
        days_to_decision=None,
    )


def _rationale_for(feeders: list[Any], team_a: str, team_b: str) -> str:
    parts = []
    for f, code in zip(feeders, [team_a, team_b], strict=False):
        if isinstance(f, FeederGroupWinner):
            parts.append(f"{code} as Group {f.group} winner")
        elif isinstance(f, FeederGroupRunnerUp):
            parts.append(f"{code} as Group {f.group} runner-up")
    return f"This slot pairs {parts[0]} against {parts[1]}." if len(parts) == 2 else ""


def _scenarios_from_compute_result(
    result: Top5Result,
    kb: KnowledgeBase,
    feeders: list[Any],
) -> list[TbdScenario]:
    return [
        TbdScenario(
            rank=i + 1,
            team_a=TeamRef(
                code=_safe_code(s.team_a_code),
                name=kb.teams[s.team_a_code].name if s.team_a_code in kb.teams else s.team_a_code,
            ),
            team_b=TeamRef(
                code=_safe_code(s.team_b_code),
                name=kb.teams[s.team_b_code].name if s.team_b_code in kb.teams else s.team_b_code,
            ),
            probability=s.probability,
            delta_pp=round(s.delta_pp, 2),
            rationale=_rationale_for(feeders, s.team_a_code, s.team_b_code),
        )
        for i, s in enumerate(result.scenarios[:3])
    ]


def _placeholder_scenarios() -> list[TbdScenario]:
    return [
        TbdScenario(
            rank=i + 1,
            team_a=TeamRef(code="TBD", name="TBD"),
            team_b=TeamRef(code="TBD", name="TBD"),
            probability=0.0,
            delta_pp=0.0,
            rationale="Awaiting bracket simulation.",
        )
        for i in range(3)
    ]


def _label_for_feeder(f: Any) -> str:
    if isinstance(f, FeederGroupWinner):
        return f"Group {f.group} winner"
    if isinstance(f, FeederGroupRunnerUp):
        return f"Group {f.group} runner-up"
    if isinstance(f, FeederBestThirdPlace):
        groups = ", ".join(f.eligible_groups)
        return f"Best 3rd-place team (groups {groups})"
    if isinstance(f, FeederR32Winner):
        return f"Winner of {f.slot}"
    if isinstance(f, FeederQfWinner):
        return f"Winner of {f.slot}"
    if isinstance(f, FeederSfLoser):
        return f"Loser of {f.slot}"
    return "TBD"


def _feeder_distribution(
    feeder: Any,
    group_probs: dict[str, GroupAdvanceProbs],
    sim_counts: dict[str, SlotMatchupCounts],
    kb: KnowledgeBase,
) -> FeederDistribution | None:
    """Return a populated FeederDistribution for a feeder, or None if not derivable."""
    label = _label_for_feeder(feeder)

    if isinstance(feeder, FeederGroupWinner):
        dist = group_probs[feeder.group].win_probs
    elif isinstance(feeder, FeederGroupRunnerUp):
        dist = group_probs[feeder.group].runner_up_probs
    elif isinstance(feeder, FeederBestThirdPlace):
        from backend.probabilities import _team_distribution_for_feeder

        dist = _team_distribution_for_feeder(feeder, group_probs)
    elif isinstance(feeder, FeederR32Winner):
        slot_counts = sim_counts.get(feeder.slot)
        if slot_counts is None or sum(slot_counts.winner_count.values()) == 0:
            return None
        total = sum(slot_counts.winner_count.values())
        dist = {team: count / total for team, count in slot_counts.winner_count.items()}
    else:
        # FeederQfWinner / FeederSfLoser: uniform-pool approximation; don't emit.
        return None

    teams = sorted(
        (
            FeederTeam(
                code=_safe_code(code),
                name=kb.teams[code].name if code in kb.teams else code,
                probability=prob,
            )
            for code, prob in dist.items()
        ),
        key=lambda t: t.probability,
        reverse=True,
    )
    return FeederDistribution(label=label, teams=teams)


def _build_tbd_match(
    inv: FixtureMatch,
    kb: KnowledgeBase,
    bracket: Bracket,
    group_probs: dict[str, GroupAdvanceProbs],
    previous_top5: dict[tuple[str, str], float],
    as_of: date,
    *,
    sim_counts: dict[str, SlotMatchupCounts],
) -> MatchObject:
    feeders = bracket.feeders_for_slot(inv.bracket_slot or "")

    feeder_distributions: list[FeederDistribution] = []
    for f in feeders:
        fd = _feeder_distribution(f, group_probs, sim_counts, kb)
        if fd is not None:
            feeder_distributions.append(fd)
    feeder_distributions_or_none = feeder_distributions if feeder_distributions else None

    feeder_leaders_for_pop: list[FeederLeader] = []
    if feeder_distributions:
        for fd in feeder_distributions:
            if fd.teams:
                top = fd.teams[0]
                feeder_leaders_for_pop.append(
                    {
                        "label": fd.label,
                        "leader_code": top.code,
                        "leader_prob": top.probability,
                    }
                )
    popularity = compute_popularity(
        phase=inv.phase,
        status="tbd",
        confirmed_team_codes=None,
        feeder_distributions=feeder_leaders_for_pop or None,
        team_lookup=kb.teams,
    )

    decision_date_obj = date.fromisoformat(inv.decision_date) if inv.decision_date else None
    days_to_decision = (decision_date_obj - as_of).days if decision_date_obj else None
    confidence = grade_confidence(
        status="tbd",
        days_to_decision=days_to_decision,
        groups_resolved=as_of >= bracket.phases["group_stage"].ends,
    )

    if all(isinstance(f, (FeederGroupWinner, FeederGroupRunnerUp)) for f in feeders):
        result = compute_top5_for_slot(
            feeders=feeders,
            group_probs=group_probs,
            previous_top5=previous_top5,
        )
        scenarios_obj = _scenarios_from_compute_result(result, kb, feeders)
    else:
        slot_counts = sim_counts.get(inv.bracket_slot or "")
        if slot_counts is None or sum(slot_counts.matchup_count.values()) == 0:
            scenarios_obj = _placeholder_scenarios()
        else:
            top5_pairs = slot_counts.top_matchups(3)
            scenarios_obj = []
            for i, (pair, prob) in enumerate(top5_pairs):
                team_a_code, team_b_code = pair
                prev = previous_top5.get((team_a_code, team_b_code), prob)
                delta_pp = (prob - prev) * 100
                scenarios_obj.append(
                    TbdScenario(
                        rank=i + 1,
                        team_a=TeamRef(
                            code=_safe_code(team_a_code),
                            name=(
                                kb.teams[team_a_code].name
                                if team_a_code in kb.teams
                                else team_a_code
                            ),
                        ),
                        team_b=TeamRef(
                            code=_safe_code(team_b_code),
                            name=(
                                kb.teams[team_b_code].name
                                if team_b_code in kb.teams
                                else team_b_code
                            ),
                        ),
                        probability=prob,
                        delta_pp=round(delta_pp, 2),
                        rationale=(
                            "Most-likely matchup based on bracket simulation"
                            " across group standings."
                        ),
                    )
                )
            while len(scenarios_obj) < 3:
                scenarios_obj.append(
                    TbdScenario(
                        rank=len(scenarios_obj) + 1,
                        team_a=TeamRef(code="TBD", name="TBD"),
                        team_b=TeamRef(code="TBD", name="TBD"),
                        probability=0.0,
                        delta_pp=0.0,
                        rationale="Below-threshold long-tail scenario.",
                    )
                )

    scenarios_obj = scenarios_obj[:3]

    top1 = scenarios_obj[0]
    feeder_leaders: tuple[str, ...] | None = None
    if feeder_distributions:
        feeder_leaders = tuple(fd.teams[0].code for fd in feeder_distributions)
    signature = compute_signature(
        status="tbd",
        confirmed_team_codes=None,
        top1_codes=(top1.team_a.code, top1.team_b.code),
        top1_probability=top1.probability,
        top5_team_codes=tuple(
            sorted({s.team_a.code for s in scenarios_obj} | {s.team_b.code for s in scenarios_obj})
        ),
        confidence=confidence,
        feeder_leaders=feeder_leaders,
        prompt_version=PROMPT_VERSION,
    )

    return MatchObject(
        id=inv.id,
        kickoff_utc=inv.kickoff_utc,
        kickoff_local=inv.kickoff_local,
        host_city=inv.host_city,
        venue=inv.venue,
        phase=Phase(inv.phase),
        status=Status.TBD,
        popularity=popularity,
        confidence=confidence,
        teams=TeamsBlock(
            confirmed=None,
            tbd_scenarios=scenarios_obj,
            feeder_distributions=feeder_distributions_or_none,
        ),
        signature=signature,
        brief=None,
        decision_date=inv.decision_date,
        days_to_decision=days_to_decision,
    )


def _derive_all_group_probs(
    odds_events: list[NormalizedEvent],
    bracket: Bracket,
    name_to_code: dict[str, str],
) -> dict[str, GroupAdvanceProbs]:
    return {
        group_name: derive_group_probs(
            group_name=group_name,
            teams=teams,
            name_to_code=name_to_code,
            events=odds_events,
        )
        for group_name, teams in bracket.groups.items()
    }


def _previous_top5_index(
    previous: MatchesFile | None,
) -> dict[str, dict[tuple[str, str], float]]:
    if previous is None:
        return {}
    idx: dict[str, dict[tuple[str, str], float]] = {}
    for m in previous.matches:
        if m.teams.tbd_scenarios is None:
            continue
        idx[m.id] = {
            (s.team_a.code, s.team_b.code): s.probability for s in m.teams.tbd_scenarios
        }
    return idx


def _apply_agents_to_matches(
    new_matches: list[MatchObject],
    previous: MatchesFile | None,
    knowledge_dir: Path,
    client: AgentClient,
) -> list[MatchObject]:
    """For each match, reuse prior brief when signature matches; otherwise call agents.

    On AgentSchemaError, falls back to the previous brief if available; else leaves None.
    """
    previous_by_id: dict[str, MatchObject] = {}
    if previous is not None:
        previous_by_id = {m.id: m for m in previous.matches}

    for i, m in enumerate(new_matches):
        prior = previous_by_id.get(m.id)
        if (
            prior is not None
            and prior.signature == m.signature
            and prior.brief is not None
        ):
            new_matches[i] = m.model_copy(update={"brief": prior.brief})
            continue

        try:
            brief = run_briefing(match=m, client=client, knowledge_dir=knowledge_dir)
            new_matches[i] = m.model_copy(update={"brief": brief})
        except AgentSchemaError:
            if prior is not None and prior.brief is not None:
                new_matches[i] = m.model_copy(update={"brief": prior.brief})

    return new_matches


def build_matches_file(
    inventory: list[FixtureMatch],
    kb: KnowledgeBase,
    bracket: Bracket,
    odds_events: list[NormalizedEvent],
    as_of: datetime,
    previous: MatchesFile | None,
    *,
    agent_client: AgentClient | None = None,
    knowledge_dir: Path | None = None,
) -> MatchesFile:
    name_to_code = _build_name_to_code(kb)
    group_probs = _derive_all_group_probs(odds_events, bracket, name_to_code)
    as_of_date = as_of.date()
    previous_top5 = _previous_top5_index(previous)

    # Plan 1.5: bracket-wide Monte Carlo for slots fed by R32+/QF+/SF+ winners.
    sim_counts = simulate_bracket(
        group_probs=group_probs,
        bracket_yaml_groups=bracket.groups,
        n_iterations=10000,
        rng=random.Random(20260508),  # fixed seed: deterministic refresh runs
    )

    matches: list[MatchObject] = []
    for inv in inventory:
        if inv.status == "confirmed":
            matches.append(_build_confirmed_match(inv, kb))
        else:
            matches.append(
                _build_tbd_match(
                    inv,
                    kb,
                    bracket,
                    group_probs,
                    previous_top5.get(inv.id, {}),
                    as_of_date,
                    sim_counts=sim_counts,
                )
            )

    if agent_client is not None and knowledge_dir is not None:
        matches = _apply_agents_to_matches(matches, previous, knowledge_dir, agent_client)

    return MatchesFile(
        generated_at=as_of,
        data_freshness=DataFreshness.FRESH,
        tournament_phase=_phase_to_tournament_phase(bracket.phase_for_date(as_of_date)),
        matches=matches,
    )


def run_offline(
    *,
    knowledge_dir: Path,
    odds_fixture_path: Path,
    output_path: Path,
    as_of: str,
    anthropic_api_key: str | None = None,
    anthropic_sdk: Any | None = None,
) -> None:
    inventory = load_fixtures(knowledge_dir / "fixtures_2026.yaml")
    kb = load_knowledge(knowledge_dir)
    bracket = load_bracket(knowledge_dir / "bracket_2026.yaml")

    raw = json.loads(odds_fixture_path.read_text())
    odds_events = [normalize_event(e) for e in raw]

    as_of_dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    previous = load_previous(output_path)

    agent_client: AgentClient | None = None
    if anthropic_sdk is not None or (anthropic_api_key is not None and anthropic_api_key != ""):
        agent_client = AgentClient(
            api_key=anthropic_api_key or "stub",
            sdk=anthropic_sdk,
        )

    file = build_matches_file(
        inventory, kb, bracket, odds_events, as_of_dt, previous,
        agent_client=agent_client,
        knowledge_dir=knowledge_dir,
    )
    write_matches_file(file, output_path)


def run_live(
    *,
    knowledge_dir: Path,
    output_path: Path,
    api_key: str,
    client: OddsClient | None = None,
    anthropic_api_key: str | None = None,
) -> None:
    inventory = load_fixtures(knowledge_dir / "fixtures_2026.yaml")
    kb = load_knowledge(knowledge_dir)
    bracket = load_bracket(knowledge_dir / "bracket_2026.yaml")

    live_client = client if client is not None else OddsClient(api_key=api_key)
    as_of_dt = datetime.now(UTC)

    try:
        odds_events = live_client.fetch()
    except OddsApiError:
        # Graceful degradation: mark existing file unreachable rather than crashing.
        previous = load_previous(output_path)
        if previous is None:
            raise
        degraded = previous.model_copy(
            update={
                "generated_at": as_of_dt,
                "data_freshness": DataFreshness.UNREACHABLE,
            }
        )
        write_matches_file(degraded, output_path)
        return

    previous = load_previous(output_path)

    agent_client: AgentClient | None = None
    if anthropic_api_key is not None and anthropic_api_key != "":
        agent_client = AgentClient(api_key=anthropic_api_key)

    file = build_matches_file(
        inventory, kb, bracket, odds_events, as_of_dt, previous,
        agent_client=agent_client,
        knowledge_dir=knowledge_dir,
    )
    write_matches_file(file, output_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="backend.refresh")
    parser.add_argument(
        "--offline", action="store_true", help="use canned fixture instead of live API"
    )
    parser.add_argument("--fixture", type=Path, default=None, help="path to odds fixture JSON")
    parser.add_argument("--knowledge-dir", type=Path, default=DEFAULT_KNOWLEDGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--as-of", type=str, default=None, help="ISO 8601 timestamp; defaults to now"
    )
    parser.add_argument(
        "--cadence",
        choices=["group_stage", "knockouts"],
        default=None,
        help=(
            "Cron cadence label. When set, the script computes the active "
            "tournament phase and exits cleanly if cadence doesn't match."
        ),
    )
    args = parser.parse_args(argv)

    if args.cadence is not None:
        bracket_for_phase = load_bracket(args.knowledge_dir / "bracket_2026.yaml")
        current_phase = bracket_for_phase.phase_for_date(
            datetime.now(UTC).date()
        )
        if not should_run_for_cadence(args.cadence, current_phase):
            print(
                f"cadence={args.cadence} skipped (active phase: {current_phase})",
                file=sys.stderr,
            )
            return 0

    if args.offline:
        default_fixture = (
            REPO_ROOT / "backend" / "tests" / "fixtures" / "odds_response_full.json"
        )
        fixture = args.fixture or default_fixture
        as_of = args.as_of or datetime.now(UTC).isoformat()
        run_offline(
            knowledge_dir=args.knowledge_dir,
            odds_fixture_path=fixture,
            output_path=args.output,
            as_of=as_of,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
    else:
        api_key = os.environ.get("ODDS_API_KEY")
        if not api_key:
            print(
                "ERROR: ODDS_API_KEY environment variable required for live mode",
                file=sys.stderr,
            )
            return 2
        run_live(
            knowledge_dir=args.knowledge_dir,
            output_path=args.output,
            api_key=api_key,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )

    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
