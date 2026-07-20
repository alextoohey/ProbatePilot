from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.deps import ensure_estate_access, optional_user, require_estate_access
from llm.claude import stream_chat, suggest_followups
from llm.embeddings import embed_query
from observability.phoenix import set_span_attribute, set_span_error, span
from prompts.system import build_chat_prompt
from schemas.api import (
    ChatHistoryResponse,
    ChatRequest,
    ChatSessionResponse,
    ChatSessionsResponse,
    ChatSuggestionsRequest,
    ChatSuggestionsResponse,
)
from schemas.auth import User
from schemas.estate import EstateState, utc_now_iso
from store.redis_client import (
    append_chat_session_messages,
    create_chat_session,
    get_chat_history,
    get_chat_session_history,
    get_estate_state,
    list_chat_sessions,
    semantic_search,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(request: ChatRequest, user: User | None = Depends(optional_user)) -> StreamingResponse:
    ensure_estate_access(request.estateId, user)
    with span("route.chat.prepare", estate_id=request.estateId, action_type="chat_query", top_k=request.topK) as current_span:
        try:
            estate_state = get_estate_state(request.estateId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Estate not found") from exc
        matches: list[dict[str, object]] = []
        retrieval_failed = False
        try:
            query_embedding = embed_query(request.message)
            matches = semantic_search(request.estateId, query_embedding, top_k=request.topK)
        except Exception as exc:
            retrieval_failed = True
            set_span_error(current_span, exc)
            LOGGER.exception("Chat retrieval failed; continuing with estate state only.")
        set_span_attribute(current_span, "retrieval_failed", retrieval_failed)
        set_span_attribute(current_span, "retrieved_chunks", len(matches))
        prompt = build_chat_prompt(
            estate_state.model_dump_json(),
            [match.text for match in matches],
        )
        set_span_attribute(current_span, "prompt_length", len(prompt))
        # Prior turns give the model conversational context; the current message
        # is appended inside stream_chat.
        _, session_messages = get_chat_session_history(request.estateId, request.sessionId)
        if not session_messages and request.sessionId is None:
            session_messages = get_chat_history(request.estateId)
        history = [
            {"role": m.get("role", ""), "content": m.get("content", "")}
            for m in session_messages
        ]
        set_span_attribute(current_span, "history_turns", len(history))

    async def events():
        with span(
            "route.chat.stream",
            estate_id=request.estateId,
            action_type="chat_query",
            top_k=request.topK,
            retrieved_chunks=len(matches),
        ):
            answer = ""
            async for token in stream_chat(prompt, request.message, history):
                answer += token
                yield f"data: {json.dumps({'token': token})}\n\n"
            # Persist the exchange so the conversation survives reloads.
            now = utc_now_iso()
            saved_session_id, saved_history = append_chat_session_messages(
                request.estateId,
                request.sessionId,
                [
                    {"role": "user", "content": request.message, "createdAt": now},
                    {"role": "assistant", "content": answer, "createdAt": utc_now_iso()},
                ],
            )
            yield f"data: {json.dumps({'sessionId': saved_session_id, 'messageCount': len(saved_history)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/chat-history/{estate_id}", dependencies=[Depends(require_estate_access)])
async def chat_history(estate_id: str, sessionId: str | None = None) -> ChatHistoryResponse:
    with span("route.chat_history", estate_id=estate_id, action_type="chat_history"):
        resolved_session_id, messages = get_chat_session_history(estate_id, sessionId)
        if not messages and sessionId is None:
            messages = get_chat_history(estate_id)
        return ChatHistoryResponse(estateId=estate_id, sessionId=resolved_session_id, messages=messages)


@router.get("/chat-sessions/{estate_id}", dependencies=[Depends(require_estate_access)])
async def chat_sessions(estate_id: str) -> ChatSessionsResponse:
    with span("route.chat_sessions", estate_id=estate_id, action_type="chat_sessions"):
        return ChatSessionsResponse(estateId=estate_id, sessions=list_chat_sessions(estate_id))


@router.post("/chat-sessions/{estate_id}", dependencies=[Depends(require_estate_access)])
async def new_chat_session(estate_id: str) -> ChatSessionResponse:
    with span("route.chat_session_create", estate_id=estate_id, action_type="chat_session_create"):
        session = create_chat_session(estate_id)
        return ChatSessionResponse(estateId=estate_id, session=session, messages=[])


def _suggestion_fallback(estate: EstateState) -> list[str]:
    """Deterministic next-question suggestions when Claude is unavailable."""
    out: list[str] = []
    if estate.alerts:
        out.append("What's the most urgent deadline?")
    if estate.debts:
        out.append("How much does the estate owe?")
        unnotified = next((d for d in estate.debts if not d.notified), None)
        if unnotified:
            out.append(f"Do I need to notify {unnotified.creditor}?")
    if estate.assets:
        out.append("What is the estate worth right now?")
    out.append("What should I do next?")
    # De-dupe while preserving order.
    return list(dict.fromkeys(out))


@router.post("/chat-suggestions")
async def chat_suggestions(request: ChatSuggestionsRequest, user: User | None = Depends(optional_user)) -> ChatSuggestionsResponse:
    ensure_estate_access(request.estateId, user)
    with span("route.chat_suggestions", estate_id=request.estateId, action_type="chat_suggestions"):
        try:
            estate_state = get_estate_state(request.estateId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Estate not found") from exc
        history = [
            {"role": m.get("role", ""), "content": m.get("content", "")}
            for m in get_chat_history(request.estateId)
        ]
        suggestions = await suggest_followups(
            estate_state.model_dump_json(),
            history,
            _suggestion_fallback(estate_state),
        )
        return ChatSuggestionsResponse(estateId=request.estateId, suggestions=suggestions[:3])
