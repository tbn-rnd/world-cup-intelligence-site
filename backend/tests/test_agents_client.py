import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from backend.agents.client import AgentClient, AgentSchemaError


class _StubModel(BaseModel):
    headline: str
    detail: str


def _mock_anthropic_response(text: str) -> Any:
    """Build a fake Anthropic Messages API response carrying a text block."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


def test_call_returns_validated_pydantic_model() -> None:
    raw = _mock_anthropic_response(json.dumps({"headline": "test", "detail": "ok"}))
    sdk = MagicMock()
    sdk.messages.create.return_value = raw

    client = AgentClient(api_key="k", sdk=sdk)
    result = client.call_structured(
        system_prefix=[{"type": "text", "text": "system", "cache_control": {"type": "ephemeral"}}],
        user_message="hello",
        response_model=_StubModel,
    )
    assert result.headline == "test"
    assert result.detail == "ok"


def test_call_retries_once_on_schema_failure_then_succeeds() -> None:
    bad = _mock_anthropic_response("not valid json at all")
    good = _mock_anthropic_response(json.dumps({"headline": "test", "detail": "ok"}))
    sdk = MagicMock()
    sdk.messages.create.side_effect = [bad, good]

    client = AgentClient(api_key="k", sdk=sdk)
    result = client.call_structured(
        system_prefix=[{"type": "text", "text": "system"}],
        user_message="hello",
        response_model=_StubModel,
    )
    assert result.headline == "test"
    assert sdk.messages.create.call_count == 2


def test_call_raises_after_two_failures() -> None:
    bad = _mock_anthropic_response("still not json")
    sdk = MagicMock()
    sdk.messages.create.return_value = bad

    client = AgentClient(api_key="k", sdk=sdk)
    with pytest.raises(AgentSchemaError):
        client.call_structured(
            system_prefix=[{"type": "text", "text": "system"}],
            user_message="hello",
            response_model=_StubModel,
        )
    assert sdk.messages.create.call_count == 2  # one retry, then raise


def test_extract_json_handles_fenced_code_blocks() -> None:
    """Models sometimes wrap JSON in ```json ... ``` fences. Strip them."""
    from backend.agents.client import _extract_json_text

    fenced = "Here is the JSON:\n```json\n{\"headline\": \"x\", \"detail\": \"y\"}\n```\n"
    assert json.loads(_extract_json_text(fenced)) == {"headline": "x", "detail": "y"}

    plain = '{"headline": "x", "detail": "y"}'
    assert json.loads(_extract_json_text(plain)) == {"headline": "x", "detail": "y"}
