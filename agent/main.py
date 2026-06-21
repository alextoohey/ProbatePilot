from __future__ import annotations

import json
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
from llm.claude import stream_chat
from llm.embeddings import embed_query, embed_texts
from observability.phoenix import span
from prompts.letters import LETTER_PROMPTS
from prompts.system import build_chat_prompt
from schemas.api import AnyDocumentExtraction, ChatRequest, DeadlineAgentRequest, GenerateLetterRequest, ParseDocumentResponse
from schemas.auth import AuthResponse, LoginRequest, MeResponse, PublicUser, RegisterRequest, User
from schemas.documents import BankStatementExtraction, DeedExtraction, WillExtraction
from schemas.estate import Asset, EstateState, Executor, UploadedDocument
from store.redis_client import (
    add_document,
    create_session,
    create_user,
    delete_session,
    get_estate_state,
    get_document_file,
    get_session_user_id,
    get_user,
    get_user_by_email,
    merge_estate_state,
    seed_demo_estate,
    semantic_search,
    set_document_file,
    set_estate_state,
    update_user,
    upsert_vectors,
)


app = FastAPI(title="Executor AI Agent")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


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
    partial: dict[str, Any] = {}

    if isinstance(extraction, WillExtraction):
        if extraction.beneficiaries:
            partial["beneficiaries"] = extraction.beneficiaries
        if extraction.assets:
            partial["assets"] = extraction.assets

    elif isinstance(extraction, BankStatementExtraction):
        parts = [
            extraction.institution,
            f"account ending {extraction.accountLast4}" if extraction.accountLast4 else None,
            f"({extraction.accountType})" if extraction.accountType else None,
        ]
        description = " ".join(p for p in parts if p) or "Bank account"
        partial["assets"] = [Asset(
            id=f"asset-bank-{uuid.uuid4().hex[:8]}",
            type="bank_account",
            description=description,
            estimatedValue=extraction.balance,
        )]

    elif isinstance(extraction, DeedExtraction) and extraction.propertyAddress:
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

    with span("document_parse", estate_id=estateId, filename=filename, action="document_parse"):
        extraction = await parse_document_text(text)

    _merge_extraction(estateId, extraction)

    doc_id = f"doc-{uuid.uuid4().hex[:8]}-{filename}"
    set_document_file(estateId, doc_id, content_type, content)
    add_document(
        estateId,
        UploadedDocument(id=doc_id, fileName=filename, documentType=extraction.documentType),
    )

    chunks = extraction.rawChunks
    if chunks:
        embeddings = embed_texts(chunks)
        upsert_vectors(estateId, chunks, embeddings, source=filename, document_type=extraction.documentType)

    alerts = await run_deadline_agent(estateId)
    return ParseDocumentResponse(estateId=estateId, extraction=extraction, alerts=alerts)


@app.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    estate_state = get_estate_state(request.estateId)
    matches = semantic_search(request.estateId, embed_query(request.message), top_k=request.topK)
    prompt = build_chat_prompt(
        estate_state.model_dump_json(),
        [match.text for match in matches],
    )

    async def events():
        async for token in stream_chat(prompt, request.message):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/generate-letter")
async def generate_letter(request: GenerateLetterRequest) -> dict[str, object]:
    estate_state = get_estate_state(request.estateId)
    prompt = LETTER_PROMPTS.get(request.letterType, LETTER_PROMPTS["creditor_notice"])
    recipient = request.recipientName or "Known Creditor"
    draft = (
        f"{recipient}\n\n"
        f"Re: Estate of {estate_state.deceasedName}\n\n"
        f"{prompt}\n\n"
        f"{estate_state.executor.name} is the executor for the estate. "
        "This placeholder letter should be replaced by the Claude-backed generator."
    )
    return {"estateId": request.estateId, "letterType": request.letterType, "draft": draft}
