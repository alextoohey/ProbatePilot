from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from dotenv import load_dotenv

load_dotenv(".env")  # must run before any module that reads env vars at import time

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from agents.deadline_agent import run_deadline_agent
from documents.pdf_reader import extract_text
from documents.router import parse_document_text
from llm.claude import DocumentParseError, generate_letter_draft, stream_chat
from llm.embeddings import embed_query, embed_texts
from observability.arize import get_tracing_status, init_tracing, set_span_attribute, set_span_error, span
from prompts.letters import build_letter_fallback, build_letter_prompt, normalize_letter_type
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


LOGGER = logging.getLogger(__name__)
app = FastAPI(title="Executor AI Agent")


@app.on_event("startup")
async def startup() -> None:
    init_tracing()


@app.get("/health")
async def health() -> dict[str, object]:
    return {"status": "ok", "tracing": get_tracing_status()}


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
        with span(
            "route.parse_document.extract",
            estate_id=estateId,
            action_type="document_parse",
            upload_filename=filename,
            content_type=content_type,
        ) as current_span:
            extraction = await parse_document_text(text)
            set_span_attribute(current_span, "doc_type", extraction.documentType)
            set_span_attribute(current_span, "chunk_count", len(extraction.rawChunks))
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

    async def events():
        with span(
            "route.chat.stream",
            estate_id=request.estateId,
            action_type="chat_query",
            top_k=request.topK,
            retrieved_chunks=len(matches),
        ):
            async for token in stream_chat(prompt, request.message):
                yield f"data: {json.dumps({'token': token})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


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
