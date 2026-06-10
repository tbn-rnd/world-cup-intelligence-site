"""Compute and diff regeneration signatures.

A signature captures the things that, if changed, would cause the briefing
agent to write meaningfully different output. Sub-percentage probability
jitter does not change the signature; a 5pp shift, a leader flip, a new team
in the top-5, or a confidence-tier transition does.

The signature also embeds a `prompt_version` token so that an edit to the
agent prompts forces regeneration of every match's brief on the next
refresh. Bump the token in backend/agents/prompts.py whenever the prompts
change in a way that should invalidate the cache.
"""

from typing import Literal


def compute_signature(
    *,
    status: Literal["confirmed", "tbd"],
    confirmed_team_codes: tuple[str, str] | None,
    top1_codes: tuple[str, str] | None,
    top1_probability: float | None,
    top5_team_codes: tuple[str, ...] | None,
    confidence: str,
    feeder_leaders: tuple[str, ...] | None = None,
    prompt_version: str = "v2",  # was "v1"
) -> str:
    if status == "confirmed":
        assert confirmed_team_codes is not None, "confirmed match requires team codes"
        a, b = sorted(confirmed_team_codes)
        return f"{prompt_version}:confirmed:{a}-{b}"

    assert top1_codes is not None
    assert top1_probability is not None
    assert top5_team_codes is not None
    a, b = sorted(top1_codes)
    bucket_lo = int((top1_probability * 100) // 5) * 5
    bucket_hi = bucket_lo + 5
    set_str = ",".join(sorted(top5_team_codes))
    feeders_str = ""
    if feeder_leaders:
        feeders_str = f":feeders={','.join(feeder_leaders)}"
    return (
        f"{prompt_version}:tbd:top1={a}-{b}:bucket={bucket_lo}-{bucket_hi}"
        f":set={set_str}:conf={confidence}{feeders_str}"
    )


def signatures_differ(new: str, old: str | None) -> bool:
    return old is None or new != old
