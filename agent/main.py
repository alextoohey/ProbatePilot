from __future__ import annotations

import json
import uuid
from typing import Any

from dotenv import load_dotenv

load_dotenv(".env")  # must run before any module that reads env vars at import time

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from agents.deadline_agent import run_deadline_agent
from documents.pdf_reader import extract_text
from documents.router import parse_document_text
from llm.claude import DocumentParseError, stream_chat
from llm.embeddings import embed_query, embed_texts
from observability.phoenix import span
from prompts.letters import LETTER_PROMPTS
from prompts.system import build_chat_prompt
from schemas.api import AnyDocumentExtraction, ChatRequest, DeadlineAgentRequest, GenerateLetterRequest, ParseDocumentResponse
from schemas.documents import BankStatementExtraction, DeedExtraction, UnknownDocumentExtraction, WillExtraction
from schemas.estate import Asset, UploadedDocument
from store.redis_client import (
    add_document,
    get_estate_state,
    merge_estate_state,
    seed_demo_estate,
    semantic_search,
    upsert_vectors,
)


app = FastAPI(title="Executor AI Agent")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/seed")
async def seed() -> dict[str, object]:
    estate = seed_demo_estate()
    alerts = await run_deadline_agent(estate.id)
    return {"estate": get_estate_state(estate.id), "alerts": alerts}


@app.get("/estate/{estate_id}")
async def estate(estate_id: str) -> dict[str, object]:
    return {"estate": get_estate_state(estate_id)}


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

    try:
        with span("document_parse", estate_id=estateId, filename=filename, action="document_parse"):
            extraction = await parse_document_text(text)
    except DocumentParseError as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                "We couldn't parse this required document. Please reupload a clearer PDF, "
                "image, or text file, or enter the information manually."
            ),
        ) from exc

    if isinstance(extraction, UnknownDocumentExtraction):
        raise HTTPException(
            status_code=422,
            detail=(
                "We couldn't identify this document. Please reupload a clearer file or "
                "enter the information manually."
            ),
        )

    _merge_extraction(estateId, extraction)

    doc_id = f"doc-{uuid.uuid4().hex[:8]}-{filename}"
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
