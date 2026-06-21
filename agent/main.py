from __future__ import annotations

import json

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from agents.deadline_agent import run_deadline_agent
from documents.router import parse_document_text
from llm.claude import stream_chat
from llm.embeddings import embed_query, embed_texts
from prompts.letters import LETTER_PROMPTS
from prompts.system import build_chat_prompt
from schemas.api import ChatRequest, DeadlineAgentRequest, GenerateLetterRequest, ParseDocumentResponse
from schemas.estate import UploadedDocument
from store.redis_client import (
    add_document,
    get_estate_state,
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


@app.post("/parse-document", response_model=ParseDocumentResponse)
async def parse_document(
    estateId: str = Form(default="demo-milligan"),
    file: UploadFile = File(...),
) -> ParseDocumentResponse:
    content = await file.read()
    text = content.decode("utf-8", errors="ignore")
    extraction = await parse_document_text(text)
    embeddings = embed_texts(extraction.rawChunks)
    upsert_vectors(
        estateId,
        extraction.rawChunks,
        embeddings,
        source=file.filename,
        document_type=extraction.documentType,
    )
    add_document(
        estateId,
        UploadedDocument(id=f"doc-{file.filename}", fileName=file.filename or "upload", documentType=extraction.documentType),
    )
    alerts = await run_deadline_agent(estateId)
    return ParseDocumentResponse(estateId=estateId, extraction=extraction, alerts=alerts)


@app.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    estate_state = get_estate_state(request.estateId)
    matches = semantic_search(request.estateId, embed_query(request.message), top_k=request.topK)
    prompt = build_chat_prompt(
        estate_state.model_dump_json(),
        [match["text"] for match in matches],
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
