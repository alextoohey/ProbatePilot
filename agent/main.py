from __future__ import annotations

import json
import logging
import uuid
from datetime import date
from typing import Any

from dotenv import load_dotenv

load_dotenv(".env")  # must run before any module that reads env vars at import time

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse

from agents.deadline_agent import run_deadline_agent
from auth.security import hash_password, new_session_token, verify_password
from documents.pdf_reader import extract_text
from documents.router import parse_document_text
from llm.claude import DocumentParseError, generate_letter_draft, stream_chat, suggest_followups
from llm.embeddings import embed_query, embed_texts
from observability.arize import get_tracing_status, init_tracing, set_span_attribute, set_span_error, span
from prompts.letters import build_letter_fallback, build_letter_prompt, normalize_letter_type
from prompts.system import build_chat_prompt
from schemas.api import AnyDocumentExtraction, ChatHistoryResponse, ChatRequest, ChatSessionResponse, ChatSessionsResponse, ChatSuggestionsRequest, ChatSuggestionsResponse, DeadlineAgentRequest, GenerateLetterRequest, ParseDocumentResponse
from schemas.auth import AuthResponse, LoginRequest, MeResponse, PublicUser, RegisterRequest, User
from schemas.documents import BankStatementExtraction, DeedExtraction, WillExtraction
from schemas.estate import Asset, EstateState, Executor, UploadedDocument, utc_now_iso
from store.redis_client import (
    add_document,
    append_chat_session_messages,
    create_chat_session,
    create_session,
    create_user,
    delete_session,
    get_chat_history,
    get_chat_session_history,
    get_estate_state,
    get_document_file,
    get_session_user_id,
    get_user,
    get_user_by_email,
    merge_estate_state,
    seed_demo_estate,
    semantic_search,
    list_chat_sessions,
    set_document_file,
    set_estate_state,
    update_user,
    upsert_vectors,
)


LOGGER = logging.getLogger(__name__)
app = FastAPI(title="Executor AI Agent")


@app.on_event("startup")
async def startup() -> None:
    init_tracing()


@app.get("/health")
async def health() -> dict[str, object]:
    return {"status": "ok", "tracing": get_tracing_status()}


# --------------------------------------------------------------------------- #
# Auth — users + sessions live in the same Redis store as estate state.
# The web layer carries the opaque session token in an httpOnly cookie and
# forwards it here as ``Authorization: Bearer <token>``.
# --------------------------------------------------------------------------- #


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


async def require_user(authorization: str | None = Header(default=None)) -> User:
    token = _bearer_token(authorization)
    user_id = get_session_user_id(token) if token else None
    user = get_user(user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _create_estate_for_user(user: User, request: RegisterRequest) -> EstateState:
    """Create the user's first estate from their sign-up details. Jurisdiction
    is California-only for the hackathon, regardless of the chosen state."""
    estate = EstateState(
        id=f"est-{uuid.uuid4().hex[:8]}",
        deceasedName=request.deceasedName.strip() or "Unknown Decedent",
        dateOfDeath=request.dateOfDeath or date.today().isoformat(),
        appointmentDate=date.today().isoformat(),
        executor=Executor(name=user.name, email=user.email),
        phase=1,
    )
    return set_estate_state(estate)


@app.post("/auth/register", response_model=AuthResponse)
async def register(request: RegisterRequest) -> AuthResponse:
    if get_user_by_email(request.email) is not None:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    user = User(
        id=f"user-{uuid.uuid4().hex[:12]}",
        name=request.name.strip(),
        email=str(request.email).strip().lower(),
        phone=request.phone,
        passwordHash=hash_password(request.password),
        relationship=request.relationship,
        state=request.state,
        county=request.county,
    )
    create_user(user)

    estate = _create_estate_for_user(user, request)
    user.estateIds = [estate.id]
    update_user(user)

    token = create_session(user.id, new_session_token())
    return AuthResponse(token=token, user=PublicUser.from_user(user), estate=estate)


@app.post("/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest) -> AuthResponse:
    user = get_user_by_email(str(request.email))
    if user is None or not verify_password(request.password, user.passwordHash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    token = create_session(user.id, new_session_token())
    return AuthResponse(token=token, user=PublicUser.from_user(user))


@app.post("/auth/logout")
async def logout(authorization: str | None = Header(default=None)) -> dict[str, bool]:
    token = _bearer_token(authorization)
    if token:
        delete_session(token)
    return {"ok": True}


@app.get("/auth/me", response_model=MeResponse)
async def me(user: User = Depends(require_user)) -> MeResponse:
    estates: list[EstateState] = []
    for estate_id in user.estateIds:
        try:
            estates.append(get_estate_state(estate_id))
        except KeyError:
            continue
    return MeResponse(user=PublicUser.from_user(user), estates=estates)


@app.post("/seed")
async def seed() -> dict[str, object]:
    estate = seed_demo_estate()
    alerts = await run_deadline_agent(estate.id)
    return {"estate": get_estate_state(estate.id), "alerts": alerts}


@app.get("/estate/{estate_id}")
async def estate(estate_id: str) -> dict[str, object]:
    return {"estate": get_estate_state(estate_id)}


@app.get("/document/{estate_id}/{doc_id}")
async def document_file(estate_id: str, doc_id: str) -> Response:
    record = get_document_file(estate_id, doc_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document file not found.")
    return Response(
        content=record["data"],
        media_type=record["contentType"],
        headers={"Content-Disposition": f'inline; filename="{doc_id}"'},
    )


@app.post("/deadline-agent")
async def deadline_agent(request: DeadlineAgentRequest) -> dict[str, object]:
    with span("route.deadline_agent", estate_id=request.estateId, action_type="deadline_agent_run"):
        alerts = await run_deadline_agent(request.estateId)
        return {"estateId": request.estateId, "alerts": alerts}


ACCEPTED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "text/plain",
    "text/html",
}


def _merge_extraction(estate_id: str, extraction: AnyDocumentExtraction) -> None:
    """Write structured facts from an extraction back into estate state."""
    try:
        estate = get_estate_state(estate_id)
    except KeyError:
        estate = None
    partial: dict[str, Any] = {}

    existing_assets = estate.assets if estate else []
    existing_bens = estate.beneficiaries if estate else []

    if isinstance(extraction, WillExtraction):
        if extraction.beneficiaries:
            existing_names = {b.name.lower().strip() for b in existing_bens}
            new_bens = [
                b for b in extraction.beneficiaries
                if b.name.lower().strip() not in existing_names
            ]
            if new_bens:
                partial["beneficiaries"] = new_bens

        if extraction.assets:
            existing_descs = {a.description.lower().strip() for a in existing_assets}
            new_assets = [
                a for a in extraction.assets
                if a.description.lower().strip() not in existing_descs
            ]
            if new_assets:
                partial["assets"] = new_assets

    elif isinstance(extraction, BankStatementExtraction):
        parts = [
            extraction.institution,
            f"account ending {extraction.accountLast4}" if extraction.accountLast4 else None,
            f"({extraction.accountType})" if extraction.accountType else None,
        ]
        description = " ".join(p for p in parts if p) or "Bank account"
        existing = next(
            (a for a in existing_assets
             if a.type == "bank_account" and extraction.accountLast4
             and extraction.accountLast4 in a.description),
            None,
        ) if estate else None
        if existing:
            existing.description = description
            existing.estimatedValue = extraction.balance or existing.estimatedValue
            partial["assets"] = [existing]
        else:
            partial["assets"] = [Asset(
                id=f"asset-bank-{uuid.uuid4().hex[:8]}",
                type="bank_account",
                description=description,
                estimatedValue=extraction.balance,
            )]

    elif isinstance(extraction, DeedExtraction) and extraction.propertyAddress:
        addr_key = extraction.propertyAddress.lower()[:30]
        existing = next(
            (a for a in existing_assets
             if a.type == "real_estate" and addr_key in a.description.lower()),
            None,
        ) if estate else None
        if existing:
            existing.estimatedValue = extraction.estimatedValue or existing.estimatedValue
            partial["assets"] = [existing]
        else:
            partial["assets"] = [Asset(
                id=f"asset-re-{uuid.uuid4().hex[:8]}",
                type="real_estate",
                description=f"Property at {extraction.propertyAddress}",
                estimatedValue=extraction.estimatedValue,
            )]

    if partial:
        merge_estate_state(estate_id, partial)


@app.post("/parse-document", response_model=ParseDocumentResponse)
async def parse_document(
    estateId: str = Form(default="demo-milligan"),
    documentType: str = Form(default=""),
    file: UploadFile = File(...),
) -> ParseDocumentResponse:
    content_type = (file.content_type or "application/octet-stream").split(";")[0].strip()
    if content_type not in ACCEPTED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {content_type}")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    filename = file.filename or "upload"
    text = extract_text(content, content_type)

    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract any text from the uploaded file.")

    # The user can manually specify the type when auto-detection failed on a prior attempt.
    forced_type = documentType.strip() or None

    try:
        with span(
            "route.parse_document.extract",
            estate_id=estateId,
            action_type="document_parse",
            upload_filename=filename,
            content_type=content_type,
            forced_type=forced_type or "",
        ) as current_span:
            extraction, resolved_type = await parse_document_text(
                text, filename=filename, forced_type=forced_type
            )
            set_span_attribute(current_span, "doc_type", resolved_type)
            set_span_attribute(current_span, "chunk_count", len(extraction.rawChunks))
    except DocumentParseError as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                "We couldn't parse this required document. Please reupload a clearer PDF, "
                "image, or text file, or enter the information manually."
            ),
        ) from exc

    # Auto-detection (content + fuzzy filename) failed and the user hasn't told us
    # the type yet: don't store anything, ask the UI to prompt for a manual choice.
    if resolved_type == "unknown" and forced_type is None:
        return ParseDocumentResponse(
            estateId=estateId,
            extraction=extraction,
            documentType="unknown",
            needsTypeSelection=True,
            alerts=[],
        )

    # Structured facts are written back into estate state (no-op for unknown types).
    _merge_extraction(estateId, extraction)

    doc_id = f"doc-{uuid.uuid4().hex[:8]}-{filename}"
    set_document_file(estateId, doc_id, content_type, content)
    add_document(
        estateId,
        UploadedDocument(id=doc_id, fileName=filename, documentType=resolved_type),
    )

    chunks = extraction.rawChunks
    if chunks:
        embeddings = embed_texts(chunks)
        upsert_vectors(estateId, chunks, embeddings, source=filename, document_type=resolved_type)

    alerts = await run_deadline_agent(estateId)
    return ParseDocumentResponse(
        estateId=estateId,
        extraction=extraction,
        documentType=resolved_type,
        needsTypeSelection=False,
        alerts=alerts,
    )


@app.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    with span("route.chat.prepare", estate_id=request.estateId, action_type="chat_query", top_k=request.topK) as current_span:
        estate_state = get_estate_state(request.estateId)
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


@app.get("/chat-history/{estate_id}")
async def chat_history(estate_id: str, sessionId: str | None = None) -> ChatHistoryResponse:
    with span("route.chat_history", estate_id=estate_id, action_type="chat_history"):
        resolved_session_id, messages = get_chat_session_history(estate_id, sessionId)
        if not messages and sessionId is None:
            messages = get_chat_history(estate_id)
        return ChatHistoryResponse(estateId=estate_id, sessionId=resolved_session_id, messages=messages)


@app.get("/chat-sessions/{estate_id}")
async def chat_sessions(estate_id: str) -> ChatSessionsResponse:
    with span("route.chat_sessions", estate_id=estate_id, action_type="chat_sessions"):
        return ChatSessionsResponse(estateId=estate_id, sessions=list_chat_sessions(estate_id))


@app.post("/chat-sessions/{estate_id}")
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


@app.post("/chat-suggestions")
async def chat_suggestions(request: ChatSuggestionsRequest) -> ChatSuggestionsResponse:
    with span("route.chat_suggestions", estate_id=request.estateId, action_type="chat_suggestions"):
        estate_state = get_estate_state(request.estateId)
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


@app.post("/generate-letter")
async def generate_letter(request: GenerateLetterRequest) -> dict[str, object]:
    letter_type = normalize_letter_type(request.letterType)
    with span(
        "route.generate_letter",
        estate_id=request.estateId,
        action_type="letter_generation",
        letter_type=letter_type,
    ) as current_span:
        estate_state = get_estate_state(request.estateId)
        prompt = build_letter_prompt(estate_state, letter_type, request.recipientName)
        fallback = build_letter_fallback(estate_state, letter_type, request.recipientName)
        set_span_attribute(current_span, "prompt_length", len(prompt))
        draft = await generate_letter_draft(
            prompt=prompt,
            letter_type=letter_type,
            fallback=fallback,
            estate_id=request.estateId,
        )
        return {"estateId": request.estateId, "letterType": letter_type, "draft": draft}
