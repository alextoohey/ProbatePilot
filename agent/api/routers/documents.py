from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from agents.deadline_agent import refresh_deadline_state
from api.deps import ensure_estate_access, optional_user, require_estate_access
from documents.upload_pipeline import (
    ParsedUpload,
    embed_stored_uploads,
    parse_error_response,
    parse_response_from_upload,
    read_and_parse_upload,
    store_parsed_upload,
)
from schemas.api import ParseDocumentFailure, ParseDocumentResponse, ParseDocumentsResponse
from schemas.auth import User
from store.redis_client import DEFAULT_ESTATE_ID, delete_document, get_document_file

LOGGER = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])


@router.get("/document/{estate_id}/{doc_id}", dependencies=[Depends(require_estate_access)])
async def document_file(estate_id: str, doc_id: str) -> Response:
    record = get_document_file(estate_id, doc_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document file not found.")
    return Response(
        content=record["data"],
        media_type=record["contentType"],
        headers={"Content-Disposition": f'inline; filename="{doc_id}"'},
    )


@router.delete("/document/{estate_id}/{doc_id}", dependencies=[Depends(require_estate_access)])
async def delete_document_route(estate_id: str, doc_id: str) -> dict[str, object]:
    removed = delete_document(estate_id, doc_id)
    if removed is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    # Deterministic-only so the response doesn't stack a second Claude call on
    # top of the delete itself; the frontend triggers the full pass afterward.
    alerts = refresh_deadline_state(estate_id)
    return {"estateId": estate_id, "deletedDocumentId": doc_id, "alerts": alerts}


@router.post("/parse-document", response_model=ParseDocumentResponse)
async def parse_document(
    estateId: str = Form(default=DEFAULT_ESTATE_ID),
    documentType: str = Form(default=""),
    file: UploadFile = File(...),
    user: User | None = Depends(optional_user),
) -> ParseDocumentResponse:
    ensure_estate_access(estateId, user)
    parsed = await read_and_parse_upload(estateId, file, documentType)
    if parsed.needs_type_selection:
        return parse_response_from_upload(estateId, parsed)

    store_parsed_upload(estateId, parsed)
    # Deterministic-only here: parsing the document is already one real Claude
    # call, and stacking the full DeadlineAgent tool-use loop on top pushed
    # single-document uploads past 60s. The frontend triggers the full,
    # Claude-enhanced pass in the background right after this returns.
    alerts = refresh_deadline_state(estateId)
    return parse_response_from_upload(estateId, parsed, alerts=alerts)


@router.post("/parse-documents", response_model=ParseDocumentsResponse)
async def parse_documents(
    estateId: str = Form(default=DEFAULT_ESTATE_ID),
    files: list[UploadFile] = File(...),
    user: User | None = Depends(optional_user),
) -> ParseDocumentsResponse:
    ensure_estate_access(estateId, user)
    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    parsed_results = await asyncio.gather(
        *(read_and_parse_upload(estateId, file) for file in files),
        return_exceptions=True,
    )

    responses: list[ParseDocumentResponse] = []
    failures: list[ParseDocumentFailure] = []
    stored_uploads: list[ParsedUpload] = []

    for file, result in zip(files, parsed_results, strict=False):
        filename = file.filename or "upload"
        if isinstance(result, HTTPException):
            failures.append(parse_error_response(result, filename))
            continue
        if isinstance(result, Exception):
            LOGGER.exception("Batch document parse failed for %s", filename, exc_info=result)
            failures.append(ParseDocumentFailure(fileName=filename, detail="Could not parse this document.", statusCode=422))
            continue

        responses.append(parse_response_from_upload(estateId, result))
        if not result.needs_type_selection:
            store_parsed_upload(estateId, result, embed_chunks=False)
            stored_uploads.append(result)

    embed_stored_uploads(estateId, stored_uploads)

    alerts = refresh_deadline_state(estateId) if stored_uploads else []
    for response in responses:
        if not response.needsTypeSelection:
            response.alerts = alerts

    return ParseDocumentsResponse(estateId=estateId, results=responses, failed=failures, alerts=alerts)
