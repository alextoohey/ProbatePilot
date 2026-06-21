from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
import uuid
from datetime import date
from typing import Any

from dotenv import load_dotenv

load_dotenv(".env")  # must run before any module that reads env vars at import time

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse

from agents.deadline_agent import mark_alert_complete, run_deadline_agent
from auth.security import hash_password, new_session_token, verify_password
from documents.pdf_reader import extract_text
from documents.router import parse_document_text_with_type as parse_document_text
from llm.claude import DocumentParseError, generate_letter_draft, stream_chat
from llm.embeddings import embed_query, embed_texts
from observability.arize import get_tracing_status, init_tracing, set_span_attribute, set_span_error, span
from prompts.letters import (
    CUSTOM_LETTER_TYPE,
    build_custom_letter_fallback,
    build_custom_letter_prompt,
    build_letter_fallback,
    build_letter_prompt,
    normalize_letter_type,
)
from prompts.system import build_chat_prompt
from schemas.api import (
    AnyDocumentExtraction,
    ChatHistoryResponse,
    ChatRequest,
    ChatSessionResponse,
    ChatSessionsResponse,
    CompleteAlertRequest,
    DeadlineAgentRequest,
    EstateResponse,
    GenerateLetterRequest,
    ParseDocumentFailure,
    ParseDocumentResponse,
    ParseDocumentsResponse,
    SaveLetterRequest,
)
from schemas.auth import AuthResponse, LoginRequest, MeResponse, PublicUser, RegisterRequest, User
from schemas.documents import BankStatementExtraction, CreditorNoticeExtraction, DeedExtraction, WillExtraction
from schemas.estate import Alert, Asset, EstateState, Executor, SavedLetter, UploadedDocument, utc_now_iso
from store.redis_client import (
    add_document,
    append_chat_session_messages,
    create_chat_session,
    create_session,
    create_user,
    delete_document,
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
        county=user.county,
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


@app.delete("/document/{estate_id}/{doc_id}")
async def delete_document_route(estate_id: str, doc_id: str) -> dict[str, object]:
    removed = delete_document(estate_id, doc_id)
    if removed is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    alerts = await run_deadline_agent(estate_id)
    return {"estateId": estate_id, "deletedDocumentId": doc_id, "alerts": alerts}


@app.post("/deadline-agent")
async def deadline_agent(request: DeadlineAgentRequest) -> dict[str, object]:
    with span("route.deadline_agent", estate_id=request.estateId, action_type="deadline_agent_run"):
        alerts = await run_deadline_agent(request.estateId)
        return {"estateId": request.estateId, "alerts": alerts}


@app.post("/complete-alert", response_model=EstateResponse)
async def complete_alert(request: CompleteAlertRequest) -> EstateResponse:
    with span("route.complete_alert", estate_id=request.estateId, action_type="complete_alert", alert_id=request.alertId):
        try:
            estate = mark_alert_complete(request.estateId, request.alertId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return EstateResponse(estate=estate)


ACCEPTED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/heif",
    "text/plain",
}

FILENAME_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".txt": "text/plain",
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

    elif isinstance(extraction, CreditorNoticeExtraction):
        existing_debts = estate.debts if estate else []
        existing_creditors = {d.creditor.lower().strip() for d in existing_debts}
        new_debts = [
            d for d in extraction.debts
            if d.creditor.lower().strip() not in existing_creditors
        ]
        if new_debts:
            partial["debts"] = new_debts

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


def _normalize_content_type(content_type: str, filename: str) -> str:
    lowered = filename.lower()
    for suffix, mapped_type in FILENAME_CONTENT_TYPES.items():
        if lowered.endswith(suffix):
            return mapped_type
    return content_type


def _plural(noun: str, count: int) -> str:
    return noun if count == 1 else f"{noun}s"


def _review_message(extraction: AnyDocumentExtraction) -> str:
    findings: list[str] = []
    if isinstance(extraction, WillExtraction):
        if extraction.executorName:
            findings.append(f"executor name {extraction.executorName}")
        if extraction.beneficiaries:
            findings.append(f"{len(extraction.beneficiaries)} {_plural('beneficiary', len(extraction.beneficiaries))}")
        if extraction.assets:
            findings.append(f"{len(extraction.assets)} {_plural('asset', len(extraction.assets))}")
    elif isinstance(extraction, BankStatementExtraction):
        if extraction.institution:
            findings.append(f"institution {extraction.institution}")
        if extraction.accountLast4:
            findings.append(f"account ending in {extraction.accountLast4}")
        if extraction.balance is not None:
            findings.append(f"reported balance ${extraction.balance:,.2f}")
        if extraction.statementDate:
            findings.append(f"statement date {extraction.statementDate}")
    elif isinstance(extraction, DeedExtraction):
        if extraction.propertyAddress:
            findings.append(f"property address {extraction.propertyAddress}")
        if extraction.apn:
            findings.append(f"APN {extraction.apn}")
        if extraction.grantor:
            findings.append(f"grantor {extraction.grantor}")
        if extraction.grantee:
            findings.append(f"grantee {extraction.grantee}")

    if not findings:
        return "We read the document. Please review it before relying on the estate update."
    if len(findings) == 1:
        summary = findings[0]
    elif len(findings) == 2:
        summary = f"{findings[0]} and {findings[1]}"
    else:
        summary = f"{', '.join(findings[:-1])}, and {findings[-1]}"
    return f"We found {summary}. Please review this before relying on the estate update."


@dataclass
class ParsedUpload:
    filename: str
    content_type: str
    content: bytes
    extraction: AnyDocumentExtraction
    resolved_type: str
    needs_type_selection: bool


def _parse_error_response(exc: HTTPException, filename: str) -> ParseDocumentFailure:
    detail = exc.detail if isinstance(exc.detail, str) else "Could not parse this document."
    status_code = int(exc.status_code or 422)
    return ParseDocumentFailure(fileName=filename, detail=detail, statusCode=status_code)


async def _read_and_parse_upload(
    estate_id: str,
    file: UploadFile,
    document_type: str = "",
) -> ParsedUpload:
    filename = file.filename or "upload"
    content_type = _normalize_content_type((file.content_type or "application/octet-stream").split(";")[0].strip(), filename)
    if content_type not in ACCEPTED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {content_type}")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    text = await asyncio.to_thread(extract_text, content, content_type)

    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract any text from the uploaded file.")

    forced_type = document_type.strip() or None

    try:
        with span(
            "route.parse_document.extract",
            estate_id=estate_id,
            action_type="document_parse",
            upload_filename=filename,
            content_type=content_type,
            forced_type=forced_type or "",
        ) as current_span:
            parsed = await _call_parse_document_text(text, filename=filename, forced_type=forced_type)
            if isinstance(parsed, tuple):
                extraction, resolved_type = parsed
            else:
                extraction, resolved_type = parsed, parsed.documentType
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

    return ParsedUpload(
        filename=filename,
        content_type=content_type,
        content=content,
        extraction=extraction,
        resolved_type=resolved_type,
        needs_type_selection=resolved_type == "unknown" and forced_type is None,
    )


async def _call_parse_document_text(text: str, filename: str, forced_type: str | None) -> Any:
    try:
        return await parse_document_text(text, filename=filename, forced_type=forced_type)
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        return await parse_document_text(text, forced_type=forced_type)


def _store_parsed_upload(estate_id: str, parsed: ParsedUpload, *, embed_chunks: bool = True) -> None:
    if parsed.needs_type_selection:
        return

    _merge_extraction(estate_id, parsed.extraction)

    doc_id = f"doc-{uuid.uuid4().hex[:8]}-{parsed.filename}"
    set_document_file(estate_id, doc_id, parsed.content_type, parsed.content)
    add_document(
        estate_id,
        UploadedDocument(id=doc_id, fileName=parsed.filename, documentType=parsed.resolved_type),
    )

    chunks = parsed.extraction.rawChunks
    if embed_chunks and chunks:
        embeddings = embed_texts(chunks)
        upsert_vectors(estate_id, chunks, embeddings, source=parsed.filename, document_type=parsed.resolved_type)


def _embed_stored_uploads(estate_id: str, parsed_uploads: list[ParsedUpload]) -> None:
    chunk_records: list[tuple[ParsedUpload, list[str]]] = [
        (parsed, parsed.extraction.rawChunks)
        for parsed in parsed_uploads
        if not parsed.needs_type_selection and parsed.extraction.rawChunks
    ]
    all_chunks = [chunk for _, chunks in chunk_records for chunk in chunks]
    if not all_chunks:
        return

    embeddings = embed_texts(all_chunks)
    offset = 0
    for parsed, chunks in chunk_records:
        next_offset = offset + len(chunks)
        upsert_vectors(
            estate_id,
            chunks,
            embeddings[offset:next_offset],
            source=parsed.filename,
            document_type=parsed.resolved_type,
        )
        offset = next_offset


def _parse_response_from_upload(
    estate_id: str,
    parsed: ParsedUpload,
    alerts: list[Alert] | None = None,
) -> ParseDocumentResponse:
    needs_type_selection = parsed.needs_type_selection
    return ParseDocumentResponse(
        estateId=estate_id,
        fileName=parsed.filename,
        extraction=parsed.extraction,
        documentType="unknown" if needs_type_selection else parsed.resolved_type,
        needsTypeSelection=needs_type_selection,
        reviewMessage=None if needs_type_selection else _review_message(parsed.extraction),
        alerts=alerts or [],
    )


@app.post("/parse-document", response_model=ParseDocumentResponse)
async def parse_document(
    estateId: str = Form(default="demo-milligan"),
    documentType: str = Form(default=""),
    file: UploadFile = File(...),
) -> ParseDocumentResponse:
    parsed = await _read_and_parse_upload(estateId, file, documentType)
    if parsed.needs_type_selection:
        return _parse_response_from_upload(estateId, parsed)

    _store_parsed_upload(estateId, parsed)
    alerts = await run_deadline_agent(estateId)
    return _parse_response_from_upload(estateId, parsed, alerts=alerts)


@app.post("/parse-documents", response_model=ParseDocumentsResponse)
async def parse_documents(
    estateId: str = Form(default="demo-milligan"),
    files: list[UploadFile] = File(...),
) -> ParseDocumentsResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    parsed_results = await asyncio.gather(
        *(_read_and_parse_upload(estateId, file) for file in files),
        return_exceptions=True,
    )

    responses: list[ParseDocumentResponse] = []
    failures: list[ParseDocumentFailure] = []
    stored_uploads: list[ParsedUpload] = []

    for file, result in zip(files, parsed_results, strict=False):
        filename = file.filename or "upload"
        if isinstance(result, HTTPException):
            failures.append(_parse_error_response(result, filename))
            continue
        if isinstance(result, Exception):
            LOGGER.exception("Batch document parse failed for %s", filename, exc_info=result)
            failures.append(ParseDocumentFailure(fileName=filename, detail="Could not parse this document.", statusCode=422))
            continue

        responses.append(_parse_response_from_upload(estateId, result))
        if not result.needs_type_selection:
            _store_parsed_upload(estateId, result, embed_chunks=False)
            stored_uploads.append(result)

    _embed_stored_uploads(estateId, stored_uploads)

    alerts = await run_deadline_agent(estateId) if stored_uploads else []
    for response in responses:
        if not response.needsTypeSelection:
            response.alerts = alerts

    return ParseDocumentsResponse(estateId=estateId, results=responses, failed=failures, alerts=alerts)


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


@app.post("/generate-letter")
async def generate_letter(request: GenerateLetterRequest) -> dict[str, object]:
    letter_type = normalize_letter_type(request.letterType, allow_custom=True)
    with span(
        "route.generate_letter",
        estate_id=request.estateId,
        action_type="letter_generation",
        letter_type=letter_type,
    ) as current_span:
        estate_state = get_estate_state(request.estateId)
        if letter_type == CUSTOM_LETTER_TYPE:
            prompt = build_custom_letter_prompt(estate_state, request.instructions, request.recipientName)
            fallback = build_custom_letter_fallback(estate_state, request.instructions, request.recipientName)
        else:
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


@app.post("/save-letter")
async def save_letter(request: SaveLetterRequest) -> dict[str, object]:
    letter = SavedLetter(
        id=f"letter-{uuid.uuid4().hex[:8]}",
        letterType=request.letterType,
        recipientName=request.recipientName,
        draft=request.draft,
    )
    merge_estate_state(request.estateId, {"letters": [letter.model_dump()]})
    return {"estateId": request.estateId, "letter": letter}
