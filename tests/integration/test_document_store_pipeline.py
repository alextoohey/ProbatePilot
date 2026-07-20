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
    from api.routers import documents

    async def fake_deadline_agent(_estate_id: str):
        return []

    monkeypatch.setattr(documents, "run_deadline_agent", fake_deadline_agent)
    return TestClient(main.app)


def _register(client: TestClient, email: str, deceased_name: str) -> tuple[dict[str, str], str]:
    """Register a fresh account and return (auth headers, its estate id).
    Document uploads are estate-scoped and require the caller to own the
    estate, so integration tests exercise the same register -> upload flow
    a real user does rather than writing to an arbitrary estate id."""
    response = client.post(
        "/auth/register",
        json={
            "name": "Test User",
            "email": email,
            "password": "correct horse battery staple",
            "deceasedName": deceased_name,
            "dateOfDeath": "2026-06-03",
            "relationship": "Child",
            "state": "California",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    return {"authorization": f"Bearer {payload['token']}"}, payload["estate"]["id"]


def test_bank_statement_upload_updates_estate_assets_documents_and_vectors(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from documents import upload_pipeline

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

    monkeypatch.setattr(upload_pipeline, "parse_document_text", fake_parse_document_text)

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


def test_deed_upload_for_owned_estate_updates_state_and_keeps_vectors(client: TestClient) -> None:
    headers, estate_id = _register(client, "deed-owner@example.com", "Property Owner")

    response = client.post(
        "/parse-document",
        data={"estateId": estate_id},
        files={
            "file": (
                "deed.txt",
                b"Grant Deed for 1847 Marin Ave. APN 123-456. Legal description attached.",
                "text/plain",
            )
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["estateId"] == estate_id
    assert payload["extraction"]["documentType"] == "deed"

    estate = get_estate_state(estate_id)
    assert any(document.fileName == "deed.txt" and document.documentType == "deed" for document in estate.documents)
    assert any(asset.type == "real_estate" and "1847 Marin Ave" in asset.description for asset in estate.assets)

    matches = semantic_search(estate_id, embed_query("Marin Ave legal description"), top_k=3)
    assert matches
    assert matches[0].estateId == estate_id
    assert matches[0].source == "deed.txt"
    assert matches[0].documentType == "deed"


def test_document_vectors_are_scoped_to_their_estate(client: TestClient) -> None:
    estate_ids: dict[str, str] = {}
    for label, email, filename, body in (
        ("a", "estate-a-owner@example.com", "a-deed.txt", b"Grant Deed for 1847 Marin Ave. APN 123-456. Legal description attached."),
        ("b", "estate-b-owner@example.com", "b-deed.txt", b"Grant Deed for 1847 Marin Ave. APN 123-456. Legal description attached."),
    ):
        headers, estate_id = _register(client, email, f"Deceased {label.upper()}")
        estate_ids[label] = estate_id
        response = client.post(
            "/parse-document",
            data={"estateId": estate_id},
            files={"file": (filename, body, "text/plain")},
            headers=headers,
        )
        assert response.status_code == 200

    estate_a_matches = semantic_search(estate_ids["a"], embed_query("Marin Ave legal description"), top_k=5)
    estate_b_matches = semantic_search(estate_ids["b"], embed_query("Marin Ave legal description"), top_k=5)

    assert estate_a_matches
    assert estate_b_matches
    assert all(match.estateId == estate_ids["a"] for match in estate_a_matches)
    assert all(match.estateId == estate_ids["b"] for match in estate_b_matches)
    assert {match.source for match in estate_a_matches} == {"a-deed.txt"}
    assert {match.source for match in estate_b_matches} == {"b-deed.txt"}


def test_rejected_upload_does_not_add_a_document(client: TestClient) -> None:
    headers, estate_id = _register(client, "rejected-upload@example.com", "Rejected Case")

    response = client.post(
        "/parse-document",
        data={"estateId": estate_id},
        files={"file": ("malware.bin", b"not a supported estate document", "application/octet-stream")},
        headers=headers,
    )

    assert response.status_code == 415
    estate = get_estate_state(estate_id)
    assert not any(document.fileName == "malware.bin" for document in estate.documents)
