from __future__ import annotations

from collections.abc import AsyncIterator
import logging
import os
from typing import Any, TypeVar

from observability.arize import set_span_attribute, set_span_error, span
from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)
LOGGER = logging.getLogger(__name__)

DOCUMENT_MODEL = "claude-sonnet-4-6"
REASONING_MODEL = "claude-opus-4-8"
CHAT_STREAM_FALLBACK = (
    "I can still help from the estate state we have. The most urgent next action is to "
    "notify known creditors and prepare the inventory and appraisal packet. If you are "
    "asking for a legal judgment, This requires your attorney's input — it involves legal advice."
)


def get_client() -> Any | None:
    """Return an Anthropic async client when configured, else None.

    Existing offline placeholders keep working when ANTHROPIC_API_KEY is absent.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        from anthropic import AsyncAnthropic
    except Exception:
        return None
    return AsyncAnthropic(api_key=api_key)


async def create_reasoning_message(
    *,
    system: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = 4096,
) -> Any:
    """Call Claude Opus for reasoning/tool use.

    Raises when the client is unavailable so callers can use deterministic fallback.
    """
    client = get_client()
    if client is None:
        raise RuntimeError("Anthropic client is unavailable.")

    with span(
        "llm.reasoning_message",
        action_type="deadline_agent_run",
        llm_provider="anthropic",
        llm_model=REASONING_MODEL,
        tools_count=len(tools or []),
        messages_count=len(messages),
        prompt_length=len(system),
    ):
        return await client.messages.create(
            model=REASONING_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tools=tools or None,
        )


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
    with span(
        "llm.structured_extract",
        action_type="document_parse",
        llm_provider="anthropic",
        llm_model=DOCUMENT_MODEL,
        response_model=response_model.__name__,
        prompt_length=len(prompt),
        content_length=len(content),
    ):
        return response_model.model_validate(fallback or {})


async def generate_letter_draft(
    *,
    prompt: str,
    letter_type: str,
    fallback: str,
    estate_id: str | None = None,
) -> str:
    """Draft a letter with Claude Sonnet, falling back to deterministic text."""
    with span(
        "llm.generate_letter",
        estate_id=estate_id,
        action_type="letter_generation",
        llm_provider="anthropic",
        llm_model=DOCUMENT_MODEL,
        letter_type=letter_type,
        prompt_length=len(prompt),
    ) as current_span:
        client = get_client()
        if client is None:
            set_span_attribute(current_span, "fallback_used", True)
            set_span_attribute(current_span, "fallback_reason", "anthropic_client_unavailable")
            return fallback

        try:
            response = await client.messages.create(
                model=DOCUMENT_MODEL,
                max_tokens=1800,
                system=(
                    "You draft operational estate administration letters. "
                    "Do not give legal advice. Return only the final sign-ready letter text."
                ),
                messages=[{"role": "user", "content": prompt}],
            )
            draft = _message_text(response)
            if not draft:
                set_span_attribute(current_span, "fallback_used", True)
                set_span_attribute(current_span, "fallback_reason", "empty_claude_letter_response")
                return fallback
            set_span_attribute(current_span, "fallback_used", False)
            set_span_attribute(current_span, "fallback_reason", "")
            set_span_attribute(current_span, "output_length", len(draft))
            return draft
        except Exception as exc:
            set_span_error(current_span, exc)
            set_span_attribute(current_span, "fallback_used", True)
            set_span_attribute(current_span, "fallback_reason", f"{exc.__class__.__name__}: {str(exc)[:160]}")
            LOGGER.exception("Claude letter generation failed; using deterministic fallback.")
            return fallback


async def stream_chat(prompt: str, message: str) -> AsyncIterator[str]:
    """Stream chat tokens from Claude when configured, else use an offline fallback."""
    with span(
        "llm.stream_chat",
        action_type="chat_query",
        llm_provider="anthropic",
        llm_model=REASONING_MODEL,
        prompt_length=len(prompt),
        message_length=len(message),
    ) as current_span:
        client = get_client()
        if client is not None:
            try:
                async with client.messages.stream(
                    model=REASONING_MODEL,
                    max_tokens=1200,
                    system=prompt,
                    messages=[{"role": "user", "content": message}],
                ) as stream:
                    async for text in stream.text_stream:
                        yield text
                set_span_attribute(current_span, "fallback_used", False)
                set_span_attribute(current_span, "fallback_reason", "")
                return
            except Exception as exc:
                set_span_error(current_span, exc)
                set_span_attribute(current_span, "fallback_reason", f"{exc.__class__.__name__}: {str(exc)[:160]}")
                LOGGER.exception("Claude chat streaming failed; using offline fallback.")
        else:
            set_span_attribute(current_span, "fallback_reason", "anthropic_client_unavailable")

        set_span_attribute(current_span, "fallback_used", True)
        response = (
            "Based on the current estate state, the most urgent next action is to notify "
            "known creditors and prepare the inventory and appraisal packet."
        )
        if _asks_for_attorney_judgment(message):
            response = (
                "This requires your attorney's input — it involves legal advice. "
                "Operationally, I can still help you identify deadlines, documents to gather, "
                "and missing facts from the estate record."
            )
        if message:
            response += f" You asked: {message}"
        for token in response.split(" "):
            yield token + " "


def _asks_for_attorney_judgment(message: str) -> bool:
    lowered = message.casefold()
    attorney_terms = (
        "legal advice",
        "what should i legally",
        "can i legally",
        "should i sue",
        "contest the will",
        "disinherit",
        "liable if",
    )
    return any(term in lowered for term in attorney_terms)


def _message_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []) or []:
        if isinstance(block, dict):
            text = block.get("text")
        else:
            text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    return "\n".join(parts).strip()
