from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, TypeVar

from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)

DOCUMENT_MODEL = "claude-sonnet-4-6"
REASONING_MODEL = "claude-opus-4-8"


def get_client() -> None:
    """Placeholder for a configured Anthropic client."""
    return None


async def structured_extract(
    prompt: str,
    content: str,
    response_model: type[ModelT],
    fallback: dict[str, Any] | None = None,
) -> ModelT:
    """Return a validated placeholder extraction.

    The real implementation should call Anthropic structured output parsing. Keeping this
    function importable unblocks parser and route work before API keys are available.
    """
    _ = (prompt, content)
    return response_model.model_validate(fallback or {})


async def stream_chat(prompt: str, message: str) -> AsyncIterator[str]:
    """Offline token stream with the same interface as Claude streaming."""
    _ = prompt
    response = (
        "Based on the current estate state, the most urgent next action is to notify "
        "known creditors and prepare the inventory and appraisal packet."
    )
    if message:
        response += f" You asked: {message}"
    for token in response.split(" "):
        yield token + " "

