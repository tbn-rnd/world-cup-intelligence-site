<div class="guide-legal" role="note" aria-label="Legal notice">
  <strong>Legal notice.</strong> This site is not a sponsor, partner, or affiliate of FIFA or the 2026 World Cup. Content is descriptive context only.
</div>

# World Cup 2026 Insight Aggregator — Guide

A short orientation for anyone using the World Cup 2026 Insight Aggregator.

The site is a single place to look up every match of the World Cup 2026 (11 June – 19 July 2026), check which ones are drawing the most attention, and read background context on the teams and their traveling fans. It is descriptive — not a sponsor, partner, or affiliate of FIFA or the 2026 World Cup. Content is intended as general background context, not operational guidance.

## What you'll see when you open the site

A typical landing experience, top to bottom:

1. **A status banner** with the tournament phase, the time until the next kickoff, and a count of matches. The banner updates as filters are applied.
2. **A "Next Up" card** with the next high-attention match: teams, kickoff date and time, host city, and a one-sentence headline.
3. **Filters** — a row of team chips for following one nation's fixtures across the whole tournament, plus dropdowns for host city, popularity tier, and tournament phase.
4. **The match list** — every match in the tournament, in date order. Each is a tile that can be expanded for a deeper brief.

That is the entire site. Everything below the banner is the same idea repeated for 104 matches.

## The match list

Every match in the tournament is rendered as a tile. Tiles are the same shape whether the teams are confirmed or still pending the bracket; the contents differ.

A tile shows:

- **Date strip** — kickoff date and local time, host city, and tournament phase (Group Stage, Round of 16, etc.).
- **Popularity badge** — `Popular`, `Moderate`, or `Standard`. Top right of the tile.
- **Match body** — for confirmed matches: the two teams with flags, FIFA ranks, and a model estimate of each team's chance of winning. For TBD knockout matches: the candidate teams who could fill the slot, and the most-likely matchups.
- **Popularity rationale** — one short sentence describing what triggered the badge.
- **Venue + "View brief" button** — the button opens a deeper card with the match brief.

## Match popularity

Every match carries one of three popularity labels. Assignment is automatic and rule-based — there is no manual curation.

| Tier | Approximately what it means |
| --- | --- |
| **Popular** | The match is likely to draw a wider audience: finals and semi-finals, matches involving a FIFA top-10 team, host-nation matches (USA, Mexico, Canada), or matches involving a team with a long-established global following. |
| **Moderate** | Knockout matches that didn't qualify as Popular, and group-stage matches with at least one FIFA top-25 team. |
| **Standard** | Most other group-stage matches between teams outside the FIFA top 25. |

The rationale line on each tile names the specific trigger ("Host-nation match (Mexico)," "Group stage; teams outside the top 25 FIFA," and so on). If a tier looks surprising, that line is the reason.

The full rule set is in the reference section at the bottom of this guide.

## Filtering

A row of team chips sits at the top of the filter area — click a team to narrow the match list to that team's fixtures across the whole tournament. The chips cover the nine global-following sides whose traveling fans drive the largest international flows: Brazil, Argentina, England, France, Germany, Spain, Portugal, Netherlands, Belgium. A `✕ Clear` link appears next to the row once a team is selected.

Three dropdown filters sit below the team chips:

- **City** — narrow to matches in a single host city.
- **Popularity** — narrow to one tier.
- **Phase** — narrow to one stage of the tournament (Group Stage, Round of 32, etc.).

Filters compose: a selected team chip plus the dropdowns narrow to the intersection. The banner countdown and the totals on the right both update with the filter, so the "next kickoff" timer reflects only matches in the filtered set. When the filter has no upcoming match, the countdown reads `No upcoming matches in filter`.

## The brief

Clicking **View brief** on any tile opens a deeper card. Every match has a brief.

A brief contains:

- **Headline** — one neutral sentence summarizing the matchup and its traveling-fan profile.
- **Scenario summary** — for TBD knockout matches, a paragraph on the most-likely matchup landscape. Not present for confirmed matches.
- **Fan demographics** — who travels for this team and from where, grounded in diaspora data.
- **Traveling volume estimate** — light, moderate, or heavy, with the reasoning.
- **Cultural context** — food traditions, religious or dietary observances, language patterns, and fan rituals.

Briefs are background. They describe; they do not recommend. Any operational interpretation belongs to the property.

## TBD knockout matches

Many knockout slots have no confirmed teams yet — the bracket has not progressed that far. A TBD tile shows:

- **Feeder distributions** — the probability that each candidate team (a group winner, runner-up, or third-place qualifier) ends up in this slot.
- **Specific matchups** — the three most-likely team-vs-team pairings, with joint probabilities.
- **Decides-in countdown** — a small ring with `Decides in Xd` showing how many days until the slot's teams are fully known. The same label appears on the Next Up card for TBD matches.
- **Confidence label** — `Confidence high`, `medium`, or `low` next to the venue, indicating how sharply the model can already pick the most-likely matchup. Confidence rises as feeder distributions concentrate on fewer candidates.

A TBD slot's popularity badge can change. A Round of 16 slot may begin as `Moderate` because no specific team is confirmed yet, then upgrade to `Popular` once one candidate team passes a confidence threshold and that team meets a Popular trigger.

## Win probability

Confirmed matches display a model estimate of each team's chance of winning, derived from the teams' FIFA rankings using an Elo-style heuristic. It is a data signal, not bookmaker odds.

- **Group-stage and friendly matches** show a draw probability alongside each team's win probability.
- **Knockout matches** show a two-way split — one team must advance, so the model folds in extra time and penalties.

The percentages reflect FIFA rankings at the time of the last data refresh.

## Data refresh and the status banner

A single line at the top of the page shows:

- **Tournament phase** — `Pre-Tournament`, `<Phase> active`, `Tournament Complete`, or `Off-Season` when no matches are in range.
- **Countdown** — time to the next kickoff in days, hours, or minutes.
- **Match counts** — total, confirmed, and TBD.

The match data is refreshed on a schedule — every hour through pre-tournament and the group stage (11 June – 27 June 2026), and every 30 minutes once the knockout phase begins on 28 June 2026, when results move the brackets faster. The header carries a `Last refreshed …` timestamp of when the underlying data was last written. If the upstream data source is unreachable, the header reads `Offline · last refreshed …` and the site continues to show the last known good snapshot.

---

## Reference

### Popularity rules in full

| Tier | All triggers |
| --- | --- |
| **Popular** | Match phase is Final, Semi-final, or Bronze-final. Or any team is FIFA top-10. Or (group stage) any team is a host nation (USA, Mexico, Canada). Or (group stage) any team is a long-established global-following side: Brazil, Argentina, France, England, Germany, Spain, Portugal, Netherlands, Belgium. |
| **Moderate** | Any knockout round (R32, R16, Quarter-final) that did not already qualify as Popular. Or a group-stage match where at least one team is FIFA top-25. |
| **Standard** | Everything else — most often group-stage matches between teams outside the top 25. |

### How TBD-slot probabilities are computed

The feeder distributions on each TBD tile and the most-likely matchups in the expanded card combine match-winner odds from the Odds API with the official 2026 World Cup bracket structure.

Group-stage standings are derived by closed-form enumeration over all 729 possible outcomes within each four-team group (three wins, draws, or losses across three matches each). Downstream knockout-slot probabilities are then computed by a 10,000-iteration Monte Carlo simulation against the bracket structure, propagating the group-stage distribution through R32, R16, quarter-finals, and beyond.

Confirmed-match win probabilities (the per-team percentages shown on a confirmed tile) are derived separately, from FIFA rankings using an Elo-style heuristic — they are a data signal, not bookmaker odds.

### Glossary

- **Bracket slot** — A position in the knockout tree, filled by the winner or qualifier of an earlier stage. A slot whose teams are not yet known is rendered as a TBD tile.
- **Bronze final** — The third-place playoff, played the day before the Final.
- **Confirmed match** — A match whose two teams are known. All 72 group-stage matches are confirmed before kickoff; knockout matches become confirmed as the bracket resolves.
- **Decides in** — The countdown on a TBD tile showing how many days until that slot's teams are fully confirmed (rendered as `Decides in Xd`).
- **Diaspora** — Communities of a team's nationality living abroad. Used to estimate traveling fan volume.
- **Feeder distribution** — For a TBD knockout slot, the probability that each candidate team fills the slot.
- **FIFA rank** — World football's official team ranking. Lower numbers are stronger; FIFA #1 is the top-ranked nation.
- **Global-following side** — A team whose appearance reliably draws an out-of-market audience: Brazil, Argentina, France, England, Germany, Spain, Portugal, Netherlands, Belgium.
- **Group stage** — The opening round: 12 groups of 4, 72 matches in total. Top two from each group plus the eight best third-placed teams advance.
- **Host city** — The metro region of the venue.
- **Host nation** — USA, Mexico, or Canada — the tournament's three co-hosts.
- **Kickoff (local vs UTC)** — The local time is the time at the venue. The UTC time is the same moment in Coordinated Universal Time, useful for time-zone comparisons.
- **Knockout phase** — Single-elimination rounds from Round of 32 through the Final.
- **Phase** — Where a match sits in the tournament: group stage, R32, R16, quarter-final, semi-final, bronze final, or final.
- **Popularity rationale** — The short sentence on each tile naming the trigger that produced the popularity tier.
- **Quarter-final** — The eight teams remaining after Round of 16 play four matches to reach the semi-finals.
- **Round of 16** — The eight matches following Round of 32; sixteen teams enter, eight advance.
- **Round of 32** — The first knockout round in the 48-team format. Thirty-two teams enter, sixteen advance.
- **Scenario** — In a TBD knockout slot, a specific team-vs-team matchup that could fill the slot, with its probability.
- **Semi-final** — Two matches that decide the two finalists.
- **TBD** — A knockout slot whose teams are not yet known. Carries scenarios and feeder distributions instead of confirmed teams.
- **Win probability** — A model estimate of each team's chance of winning a confirmed match, derived from FIFA rankings (not bookmaker odds).

## Questions

For site questions or data corrections, open an issue on the repository.

<div class="guide-legal" role="note" aria-label="Legal notice">
  <strong>Legal notice.</strong> This site is not a sponsor, partner, or affiliate of FIFA or the 2026 World Cup. Content is descriptive context only.
</div>
