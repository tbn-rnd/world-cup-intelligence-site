"""Anthropic SDK wrapper with prompt caching, schema validation, and retry semantics.

Used by the briefing agent to share auth handling, caching,
structured-output validation, and error recovery in one place.

Output protocol: the agent prompt instructs the model to emit a single JSON
object matching the requested Pydantic schema. We strip optional ``` fences,
validate, retry once on failure, and raise AgentSchemaError after two
failures so the caller can keep the previous brief instead of writing
garbage.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from anthropic import Anthropic
from anthropic.types import TextBlockParam
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 2048


class AgentSchemaError(RuntimeError):
    """Raised after the model fails twice to emit valid JSON for the requested schema."""


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json_text(text: str) -> str:
    """Extract a JSON payload from a model response, stripping optional code fences."""
    text = text.strip()
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text


class AgentClient:
    """Thin wrapper over the Anthropic Messages API for structured outputs."""

    def __init__(
        self,
        api_key: str,
        *,
        sdk: Any | None = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self._sdk = sdk if sdk is not None else Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def call_structured(
        self,
        *,
        system_prefix: list[TextBlockParam],
        user_message: str,
        response_model: type[T],
        max_attempts: int = 2,
    ) -> T:
        """Call the model with a cacheable system prefix and validate the JSON output.

        Args:
            system_prefix: list of system content blocks (TextBlockParam). The caller
                is responsible for setting `cache_control: {"type": "ephemeral"}` on
                the blocks that should be cached. The wrapper passes the list through
                unmodified.
            user_message: plain-text variable suffix (per-match state).
            response_model: Pydantic class the response must validate against.
            max_attempts: total tries (including retries). Defaults to 2.
        """
        last_error: Exception | None = None
        for _ in range(max_attempts):
            response = self._sdk.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_prefix,
                messages=[{"role": "user", "content": user_message}],
            )
            text = "".join(
                t
                for block in response.content
                if (t := getattr(block, "text", None)) is not None
                and getattr(block, "type", None) == "text"
            )
            try:
                payload = json.loads(_extract_json_text(text))
                return response_model.model_validate(payload)
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = e
                continue

        raise AgentSchemaError(
            f"agent failed to produce valid {response_model.__name__} JSON"
            f" after {max_attempts} attempts: {last_error}"
        )
