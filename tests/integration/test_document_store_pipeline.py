from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from llm.embeddings import embed_query
from schemas.documents import BankStatementExtraction
from store.redis_client import get_estate_state, semantic_search


@pytest.fixture(autouse=True)
def no_external_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the local fallback path so integration tests never need API keys."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import main

    async def fake_deadline_agent(_estate_id: str):
        return []

    monkeypatch.setattr(main, "run_deadline_agent", fake_deadline_agent)
    return TestClient(main.app)


def test_bank_statement_upload_updates_estate_assets_documents_and_vectors(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import main

    async def fake_parse_document_text(_text: str, forced_type: str | None = None) -> BankStatementExtraction:
        assert forced_type is None
        return BankStatementExtraction(
            documentType="bank_statement",
            confidence=0.95,
            institution="Wells Fargo",
            accountLast4="4412",
            accountType="checking",
            balance=38240,
            statementDate=None,
            notableTransactions=[],
            rawChunks=["Wells Fargo checking statement for account 4412 with balance 38240."],
        )

    monkeypatch.setattr(main, "parse_document_text", fake_parse_document_text)

    response = client.post(
        "/parse-document",
        data={"estateId": "demo-milligan"},
        files={
            "file": (
                "checking.txt",
                b"Wells Fargo checking statement for account 4412 with balance 38240.",
                "text/plain",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["extraction"]["documentType"] == "bank_statement"
    assert payload["extraction"]["accountLast4"] == "4412"

    estate = get_estate_state("demo-milligan")
    assert any(document.fileName == "checking.txt" and document.documentType == "bank_statement" for document in estate.documents)
    assert any(
        asset.type == "bank_account"
        and "Wells Fargo" in asset.description
        and "account ending 4412" in asset.description
        for asset in estate.assets
    )

    matches = semantic_search("demo-milligan", embed_query("Wells Fargo checking account"), top_k=3)
    assert matches
    assert matches[0].estateId == "demo-milligan"
    assert matches[0].source == "checking.txt"
    assert matches[0].documentType == "bank_statement"


def test_deed_upload_for_new_estate_creates_state_and_keeps_vectors(client: TestClient) -> None:
    response = client.post(
        "/parse-document",
        data={"estateId": "estate-property"},
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
    assert payload["estateId"] == "estate-property"
    assert payload["extraction"]["documentType"] == "deed"

    estate = get_estate_state("estate-property")
    assert estate.id == "estate-property"
    assert any(document.fileName == "deed.txt" and document.documentType == "deed" for document in estate.documents)
    assert any(asset.type == "real_estate" and "1847 Marin Ave" in asset.description for asset in estate.assets)

    matches = semantic_search("estate-property", embed_query("Marin Ave legal description"), top_k=3)
    assert matches
    assert matches[0].estateId == "estate-property"
    assert matches[0].source == "deed.txt"
    assert matches[0].documentType == "deed"


def test_document_vectors_are_scoped_to_their_estate(client: TestClient) -> None:
    for estate_id, filename, body in (
        ("estate-a", "a-deed.txt", b"Grant Deed for 1847 Marin Ave. APN 123-456. Legal description attached."),
        ("estate-b", "b-deed.txt", b"Grant Deed for 1847 Marin Ave. APN 123-456. Legal description attached."),
    ):
        response = client.post(
            "/parse-document",
            data={"estateId": estate_id},
            files={"file": (filename, body, "text/plain")},
        )
        assert response.status_code == 200

    estate_a_matches = semantic_search("estate-a", embed_query("Marin Ave legal description"), top_k=5)
    estate_b_matches = semantic_search("estate-b", embed_query("Marin Ave legal description"), top_k=5)

    assert estate_a_matches
    assert estate_b_matches
    assert all(match.estateId == "estate-a" for match in estate_a_matches)
    assert all(match.estateId == "estate-b" for match in estate_b_matches)
    assert {match.source for match in estate_a_matches} == {"a-deed.txt"}
    assert {match.source for match in estate_b_matches} == {"b-deed.txt"}


def test_rejected_upload_does_not_create_estate_state(client: TestClient) -> None:
    response = client.post(
        "/parse-document",
        data={"estateId": "estate-rejected"},
        files={"file": ("malware.bin", b"not a supported estate document", "application/octet-stream")},
    )

    assert response.status_code == 415
    with pytest.raises(KeyError):
        get_estate_state("estate-rejected")
