from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)

DOCUMENT_MODEL = "claude-sonnet-4-6"
REASONING_MODEL = "claude-sonnet-4-6"

_client: anthropic.Anthropic | None = None
_async_client: anthropic.AsyncAnthropic | None = None


class DocumentParseError(RuntimeError):
    """Raised when a document needs a real structured parse and none is available."""


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _get_async_client() -> anthropic.AsyncAnthropic:
    global _async_client
    if _async_client is None:
        _async_client = anthropic.AsyncAnthropic()
    return _async_client


def get_client() -> anthropic.Anthropic:
    return _get_client()


async def structured_extract(
    prompt: str,
    content: str,
    response_model: type[ModelT],
    fallback: dict[str, Any] | None = None,
    allow_fallback: bool = True,
) -> ModelT:
    tool_name = response_model.__name__
    schema = response_model.model_json_schema()
    schema.pop("title", None)
    failure: Exception | None = None

    try:
        response = _get_client().messages.create(
            model=DOCUMENT_MODEL,
            max_tokens=4096,
            tools=[{
                "name": tool_name,
                "description": f"Extract all {tool_name} fields from the provided document.",
                "input_schema": schema,
            }],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{
                "role": "user",
                "content": f"{prompt}\n\nDOCUMENT CONTENT:\n{content}",
            }],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                return response_model.model_validate(block.input)

    except Exception as exc:
        failure = exc
        print(f"[claude] structured_extract failed: {exc}")

    if not allow_fallback:
        raise DocumentParseError("Structured document extraction did not complete.") from failure
    if fallback is None:
        raise DocumentParseError("No structured extraction fallback is available.") from failure

    return response_model.model_validate(fallback)


async def stream_chat(system_prompt: str, message: str) -> AsyncIterator[str]:
    async with _get_async_client().messages.stream(
        model=REASONING_MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": message}],
    ) as stream:
        async for text in stream.text_stream:
            yield text
