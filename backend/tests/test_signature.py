from backend.signature import compute_signature, signatures_differ


def test_confirmed_signature() -> None:
    sig = compute_signature(
        status="confirmed",
        confirmed_team_codes=("USA", "POR"),
        top1_codes=None,
        top1_probability=None,
        top5_team_codes=None,
        confidence="certain",
    )
    assert sig == "v2:confirmed:POR-USA"  # codes are sorted


def test_tbd_signature() -> None:
    sig = compute_signature(
        status="tbd",
        confirmed_team_codes=None,
        top1_codes=("MEX", "JPN"),
        top1_probability=0.34,
        top5_team_codes=("ARG", "BRA", "JPN", "MEX", "SWE"),
        confidence="medium",
    )
    assert sig == "v2:tbd:top1=JPN-MEX:bucket=30-35:set=ARG,BRA,JPN,MEX,SWE:conf=medium"


def test_signature_bucket_rounding() -> None:
    sig_a = compute_signature(
        status="tbd",
        confirmed_team_codes=None,
        top1_codes=("MEX", "JPN"),
        top1_probability=0.32,
        top5_team_codes=("ARG", "BRA", "JPN", "MEX", "SWE"),
        confidence="medium",
    )
    sig_b = compute_signature(
        status="tbd",
        confirmed_team_codes=None,
        top1_codes=("MEX", "JPN"),
        top1_probability=0.34,
        top5_team_codes=("ARG", "BRA", "JPN", "MEX", "SWE"),
        confidence="medium",
    )
    assert sig_a == sig_b  # both fall in 30-35 bucket


def test_signatures_differ_helper() -> None:
    assert not signatures_differ("v1:confirmed:POR-USA", "v1:confirmed:POR-USA")
    assert signatures_differ("v1:confirmed:POR-USA", "v1:confirmed:POR-MEX")


def test_signature_includes_feeder_leaders() -> None:
    """When feeder_leaders is populated, the signature embeds them deterministically."""
    sig = compute_signature(
        status="tbd",
        confirmed_team_codes=None,
        top1_codes=("MEX", "NED"),
        top1_probability=0.11,
        top5_team_codes=("CZE", "JPN", "MEX", "NED", "SWE"),
        confidence="low",
        feeder_leaders=("MEX", "NED"),
    )
    assert "feeders=MEX,NED" in sig


def test_signature_changes_when_feeder_leader_flips() -> None:
    sig_a = compute_signature(
        status="tbd",
        confirmed_team_codes=None,
        top1_codes=("MEX", "NED"),
        top1_probability=0.11,
        top5_team_codes=("CZE", "JPN", "MEX", "NED", "SWE"),
        confidence="low",
        feeder_leaders=("MEX", "NED"),
    )
    sig_b = compute_signature(
        status="tbd",
        confirmed_team_codes=None,
        top1_codes=("MEX", "NED"),
        top1_probability=0.11,
        top5_team_codes=("CZE", "JPN", "MEX", "NED", "SWE"),
        confidence="low",
        feeder_leaders=("MEX", "JPN"),
    )
    assert sig_a != sig_b


def test_signature_includes_prompt_version_for_confirmed() -> None:
    """Bumping prompt_version invalidates the cached signature for confirmed matches."""
    sig_v1 = compute_signature(
        status="confirmed",
        confirmed_team_codes=("USA", "POR"),
        top1_codes=None,
        top1_probability=None,
        top5_team_codes=None,
        confidence="certain",
        prompt_version="v1",
    )
    sig_v2 = compute_signature(
        status="confirmed",
        confirmed_team_codes=("USA", "POR"),
        top1_codes=None,
        top1_probability=None,
        top5_team_codes=None,
        confidence="certain",
        prompt_version="v2",
    )
    assert sig_v1 != sig_v2
    assert sig_v1.startswith("v1:")
    assert sig_v2.startswith("v2:")


def test_signature_includes_prompt_version_for_tbd() -> None:
    """Bumping prompt_version invalidates the cached signature for TBD matches."""
    kwargs = dict(
        status="tbd",
        confirmed_team_codes=None,
        top1_codes=("MEX", "JPN"),
        top1_probability=0.34,
        top5_team_codes=("ARG", "BRA", "JPN", "MEX", "SWE"),
        confidence="medium",
    )
    sig_v1 = compute_signature(**kwargs, prompt_version="v1")  # type: ignore[arg-type]
    sig_v2 = compute_signature(**kwargs, prompt_version="v2")  # type: ignore[arg-type]
    assert sig_v1 != sig_v2


def test_signature_omits_feeders_when_none() -> None:
    """When feeder_leaders is None, the signature has no feeders= component."""
    sig = compute_signature(
        status="tbd",
        confirmed_team_codes=None,
        top1_codes=("MEX", "NED"),
        top1_probability=0.11,
        top5_team_codes=("CZE", "JPN", "MEX", "NED", "SWE"),
        confidence="low",
        feeder_leaders=None,
    )
    assert "feeders=" not in sig
