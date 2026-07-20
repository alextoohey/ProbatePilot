"""The upload -> extract -> merge -> embed pipeline shared by the single-
and batch-upload routes."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, UploadFile

from documents.merge import merge_extraction
from documents.pdf_reader import extract_text
from documents.router import parse_document_text_with_type as parse_document_text
from llm.claude import DocumentParseError
from llm.embeddings import embed_texts
from observability.phoenix import set_span_attribute, span
from schemas.api import AnyDocumentExtraction, ParseDocumentFailure, ParseDocumentResponse
from schemas.documents import BankStatementExtraction, DeedExtraction, WillExtraction
from schemas.estate import Alert, UploadedDocument
from store.redis_client import add_document, set_document_file, upsert_vectors

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


@dataclass
class ParsedUpload:
    filename: str
    content_type: str
    content: bytes
    extraction: AnyDocumentExtraction
    resolved_type: str
    needs_type_selection: bool


def parse_error_response(exc: HTTPException, filename: str) -> ParseDocumentFailure:
    detail = exc.detail if isinstance(exc.detail, str) else "Could not parse this document."
    status_code = int(exc.status_code or 422)
    return ParseDocumentFailure(fileName=filename, detail=detail, statusCode=status_code)


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


async def _call_parse_document_text(text: str, filename: str, forced_type: str | None) -> Any:
    try:
        return await parse_document_text(text, filename=filename, forced_type=forced_type)
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        return await parse_document_text(text, forced_type=forced_type)


async def read_and_parse_upload(
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


def store_parsed_upload(estate_id: str, parsed: ParsedUpload, *, embed_chunks: bool = True) -> None:
    if parsed.needs_type_selection:
        return

    merge_extraction(estate_id, parsed.extraction)

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


def embed_stored_uploads(estate_id: str, parsed_uploads: list[ParsedUpload]) -> None:
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


def parse_response_from_upload(
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
