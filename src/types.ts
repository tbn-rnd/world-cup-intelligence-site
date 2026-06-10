// Mirror of backend/schema.py — keep in sync with matches.json shape.

export type DataFreshness = "fresh" | "stale" | "unreachable";
export type TournamentPhase =
  | "pre_tournament"
  | "group_stage"
  | "round_of_32"
  | "round_of_16"
  | "quarter_finals"
  | "semi_finals"
  | "finals";

export type Phase =
  | "friendly"
  | "group_stage"
  | "round_of_32"
  | "round_of_16"
  | "quarter_final"
  | "semi_final"
  | "bronze_final"
  | "final";

export type Status = "confirmed" | "tbd";
export type PopularityTier = "popular" | "moderate" | "standard";
export type Confidence = "certain" | "high" | "medium" | "low";
export type HostCity = string;

export interface Popularity {
  tier: PopularityTier;
  rationale: string;
}

export interface ConfirmedTeam {
  code: string;
  name: string;
  fifa_rank: number;
}

export interface TeamRef {
  code: string;
  name: string;
}

export interface TbdScenario {
  rank: number;
  team_a: TeamRef;
  team_b: TeamRef;
  probability: number;
  delta_pp: number;
  rationale: string;
}

export interface FeederTeam {
  code: string;
  name: string;
  probability: number;
}

export interface FeederDistribution {
  label: string;
  teams: FeederTeam[];
}

export interface TeamsBlock {
  confirmed: ConfirmedTeam[] | null;
  tbd_scenarios: TbdScenario[] | null;
  feeder_distributions: FeederDistribution[] | null;
}

export interface Brief {
  headline: string;
  scenario_summary: string | null;
  fan_demographics: string;
  traveling_volume_est: string;
  cultural_context: string;
}

export interface TeamWinProb {
  code: string;
  name: string;
  win_prob: number;
}

export interface MatchPrediction {
  method: "fifa_rank_elo";
  teams: TeamWinProb[];
  draw_prob: number | null;
}

export interface MatchObject {
  id: string;
  kickoff_utc: string;
  kickoff_local: string;
  host_city: HostCity;
  venue: string;
  phase: Phase;
  status: Status;
  popularity: Popularity;
  confidence: Confidence;
  teams: TeamsBlock;
  signature: string;
  brief: Brief | null;
  prediction: MatchPrediction | null;
  decision_date: string | null;
  days_to_decision: number | null;
}

export interface MatchesFile {
  generated_at: string;
  data_freshness: DataFreshness;
  tournament_phase: TournamentPhase;
  matches: MatchObject[];
}
