from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from documents.router import detect_document_type, parse_document_text
from llm.claude import DocumentParseError
from llm.embeddings import VECTOR_SIZE, embed_query, embed_texts
from schemas.documents import (
    BankStatementExtraction,
    DeedExtraction,
    UnknownDocumentExtraction,
    WillExtraction,
)
from store.redis_client import get_estate_state, semantic_search


@pytest.mark.parametrize(
    ("text", "expected_type"),
    [
        ("Last Will and Testament of Robert Milligan naming Dana as executor.", "will"),
        ("Wells Fargo checking statement account 4412 balance 38240.", "bank_statement"),
        ("Grant Deed APN 123-456 legal description for Marin Ave.", "deed"),
        ("A handwritten note about family photos.", "unknown"),
    ],
)
def test_detect_document_type_routes_expected_documents(text: str, expected_type: str) -> None:
    assert detect_document_type(text) == expected_type


@pytest.mark.asyncio
async def test_parse_will_requires_structured_extraction_without_fallback() -> None:
    with pytest.raises(DocumentParseError):
        await parse_document_text(
            "Last Will and Testament. Dana Milligan shall serve as executor. "
            "Beneficiary Sarah receives personal property."
        )


@pytest.mark.asyncio
async def test_parse_bank_statement_requires_structured_extraction_without_fallback() -> None:
    with pytest.raises(DocumentParseError):
        await parse_document_text("Wells Fargo checking statement for account 4412.")


@pytest.mark.asyncio
async def test_parse_deed_extracts_stable_fields() -> None:
    extraction = await parse_document_text(
        "Grant Deed for 1847 Marin Ave. APN 123-456. Legal description attached."
    )

    assert isinstance(extraction, DeedExtraction)
    assert extraction.documentType == "deed"
    assert extraction.propertyAddress == "1847 Marin Ave, Berkeley CA"
    assert extraction.rawChunks


@pytest.mark.asyncio
async def test_unknown_document_is_safe_and_chunked() -> None:
    text = "Family note " * 200
    extraction = await parse_document_text(text)

    assert isinstance(extraction, UnknownDocumentExtraction)
    assert extraction.documentType == "unknown"
    assert extraction.reason
    assert 1 <= len(extraction.rawChunks) <= 3
    assert all(len(chunk) <= 500 for chunk in extraction.rawChunks)


def test_embeddings_are_1536_dimensional_deterministic_and_bounded() -> None:
    texts = ["inventory appraisal deadline", "creditor notice window"]
    first = embed_texts(texts)
    second = embed_texts(texts)

    assert len(first) == len(texts)
    assert all(len(vector) == VECTOR_SIZE for vector in first)
    assert first == second
    assert embed_query(texts[0]) == first[0]
    assert all(-1 <= value <= 1 for vector in first for value in vector)


def test_parse_document_endpoint_embeds_adds_document_and_returns_alerts(monkeypatch: pytest.MonkeyPatch) -> None:
    import main

    async def fake_deadline_agent(estate_id: str):
        assert estate_id == "demo-milligan"
        return []

    monkeypatch.setattr(main, "run_deadline_agent", fake_deadline_agent)
    client = TestClient(main.app)

    response = client.post(
        "/parse-document",
        data={"estateId": "demo-milligan"},
        files={
            "file": (
                "deed.txt",
                b"Grant Deed for 1847 Marin Ave. APN 123-456. Legal description attached.",
                "text/plain",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["estateId"] == "demo-milligan"
    assert payload["extraction"]["documentType"] == "deed"
    assert payload["alerts"] == []

    estate = get_estate_state("demo-milligan")
    assert any(document.fileName == "deed.txt" for document in estate.documents)

    matches = semantic_search("demo-milligan", embed_query("Marin Ave legal description"), top_k=3)
    assert matches
    assert matches[0].estateId == "demo-milligan"
    assert matches[0].source == "deed.txt"
    assert matches[0].documentType == "deed"
