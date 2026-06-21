from __future__ import annotations

from collections.abc import AsyncIterator
import json
import logging
import os
import re
from typing import Any, TypeVar

import anthropic
from observability.phoenix import set_span_attribute, set_span_error, span
from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)
LOGGER = logging.getLogger(__name__)

DOCUMENT_MODEL = "claude-sonnet-4-6"
REASONING_MODEL = "claude-sonnet-4-6"

_client: anthropic.Anthropic | None = None
_async_client: anthropic.AsyncAnthropic | None = None


class DocumentParseError(RuntimeError):
    """Raised when a document needs a real structured parse and none is available."""

def _get_client() -> anthropic.Anthropic | None:
    """Return a sync Anthropic client when configured, else None."""
    global _client
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def get_client() -> anthropic.Anthropic | None:
    return _get_client()


def get_async_client() -> anthropic.AsyncAnthropic | None:
    """Return an async Anthropic client when configured, else None."""
    global _async_client
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    if _async_client is None:
        _async_client = anthropic.AsyncAnthropic()
    return _async_client


async def create_reasoning_message(
    *,
    system: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = 4096,
) -> Any:
    """Call Claude for reasoning/tool use.

    Raises when the client is unavailable so callers can use deterministic fallback.
    """
    client = get_async_client()
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
    allow_fallback: bool = True,
) -> ModelT:
    """Extract structured document data with Claude, falling back when allowed."""
    with span(
        "llm.structured_extract",
        action_type="document_parse",
        llm_provider="anthropic",
        llm_model=DOCUMENT_MODEL,
        response_model=response_model.__name__,
        prompt_length=len(prompt),
        content_length=len(content),
    ) as current_span:
        tool_name = response_model.__name__
        schema = response_model.model_json_schema()
        schema.pop("title", None)
        client = get_async_client()

        if client is None:
            set_span_attribute(current_span, "fallback_used", True)
            set_span_attribute(current_span, "fallback_reason", "anthropic_client_unavailable")
            if not allow_fallback:
                raise DocumentParseError("ANTHROPIC_API_KEY is required for this document parse.")
            if fallback is None:
                raise DocumentParseError("No structured extraction fallback is available.")
            return response_model.model_validate(fallback)

        try:
            response = await client.messages.create(
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
                    set_span_attribute(current_span, "fallback_used", False)
                    set_span_attribute(current_span, "fallback_reason", "")
                    return response_model.model_validate(block.input)

            set_span_attribute(current_span, "fallback_reason", "missing_tool_use")
            failure: Exception = DocumentParseError("Structured document extraction did not complete.")
        except Exception as exc:
            failure = exc
            set_span_error(current_span, exc)
            set_span_attribute(current_span, "fallback_reason", f"{exc.__class__.__name__}: {str(exc)[:160]}")
            LOGGER.exception("Claude structured extraction failed; using deterministic fallback.")

        set_span_attribute(current_span, "fallback_used", True)
        if not allow_fallback:
            raise DocumentParseError("Structured document extraction did not complete.") from failure
        if fallback is None:
            raise DocumentParseError("No structured extraction fallback is available.") from failure
        return response_model.model_validate(fallback)


async def generate_letter_draft(
    *,
    prompt: str,
    letter_type: str,
    fallback: str,
    estate_id: str | None = None,
) -> str:
    """Draft a letter with Claude, falling back to deterministic text."""
    with span(
        "llm.generate_letter",
        estate_id=estate_id,
        action_type="letter_generation",
        llm_provider="anthropic",
        llm_model=DOCUMENT_MODEL,
        letter_type=letter_type,
        prompt_length=len(prompt),
    ) as current_span:
        client = get_async_client()
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


async def stream_chat(
    prompt: str,
    message: str,
    history: list[dict[str, str]] | None = None,
) -> AsyncIterator[str]:
    """Stream chat tokens from Claude when configured, else use an offline fallback.

    ``history`` is the prior conversation (alternating user/assistant turns) so the
    model keeps context across messages; the current ``message`` is appended last.
    """
    prior = [
        {"role": m["role"], "content": m["content"]}
        for m in (history or [])
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    with span(
        "llm.stream_chat",
        action_type="chat_query",
        llm_provider="anthropic",
        llm_model=REASONING_MODEL,
        prompt_length=len(prompt),
        message_length=len(message),
        history_turns=len(prior),
    ) as current_span:
        client = get_async_client()
        if client is not None:
            try:
                async with client.messages.stream(
                    model=REASONING_MODEL,
                    max_tokens=1200,
                    system=prompt,
                    messages=[*prior, {"role": "user", "content": message}],
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


def _parse_suggestions(text: str) -> list[str]:
    """Pull a JSON array of strings out of the model's reply (tolerates code fences)."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [str(s).strip() for s in data if isinstance(s, str) and s.strip()]


async def suggest_followups(
    estate_json: str,
    history: list[dict[str, str]],
    fallback: list[str],
) -> list[str]:
    """Suggest exactly 3 short follow-up questions the executor might ask next,
    grounded in the estate state and recent conversation. Falls back to the
    provided deterministic list when Claude is unavailable or returns nothing."""
    client = get_async_client()
    if client is None:
        return fallback[:3]

    recent = history[-6:]
    convo = "\n".join(f"{m.get('role', '')}: {m.get('content', '')}" for m in recent) or "(no messages yet)"
    system = (
        "You suggest the next questions an estate executor is likely to ask a chat "
        "assistant for California probate. Use the estate state and the recent "
        "conversation to propose EXACTLY 3 short, distinct questions (max ~9 words each) "
        "that move the executor forward and avoid repeating what was just answered. "
        "Ground them in this estate's real data. Respond with ONLY a JSON array of 3 strings."
    )
    user = f"Estate state (JSON):\n{estate_json}\n\nRecent conversation:\n{convo}"

    with span(
        "llm.suggest_followups",
        action_type="chat_suggestions",
        llm_provider="anthropic",
        llm_model=DOCUMENT_MODEL,
        history_turns=len(recent),
    ) as current_span:
        try:
            response = await client.messages.create(
                model=DOCUMENT_MODEL,
                max_tokens=300,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            items = _parse_suggestions(_message_text(response))
            set_span_attribute(current_span, "suggestion_count", len(items))
            if len(items) >= 3:
                return items[:3]
            # Top up from the fallback (deduped) if the model returned too few.
            merged = items + [f for f in fallback if f not in items]
            return merged[:3]
        except Exception as exc:
            set_span_error(current_span, exc)
            LOGGER.exception("Follow-up suggestion generation failed; using fallback.")
            return fallback[:3]


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
