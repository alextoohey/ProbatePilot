from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.api import ChatRequest, ParseDocumentResponse, SearchResult
from schemas.documents import BankStatementExtraction, UnknownDocumentExtraction, WillExtraction
from schemas.estate import Alert, Asset, EstateState, Executor
from seed.demo_estate import build_demo_estate


def test_estate_state_contract_accepts_demo_estate_and_round_trips() -> None:
    estate = build_demo_estate()
    round_tripped = EstateState.model_validate_json(estate.model_dump_json())

    assert round_tripped.id == "demo-milligan"
    assert round_tripped.state == "california"
    assert round_tripped.phase == 2
    assert len(round_tripped.assets) >= 4
    assert len(round_tripped.debts) >= 3
    assert round_tripped.executor == Executor(name="Dana Milligan", email="dana@demo.com")


def test_contract_models_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Executor(name="Dana", email="dana@example.com", phone="555-1212")  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        ChatRequest(estateId="demo-milligan", message="hello", unexpected=True)  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        UnknownDocumentExtraction(confidence=0.5, rawChunks=[], extra="nope")  # type: ignore[call-arg]


def test_estate_literals_and_ranges_are_enforced() -> None:
    with pytest.raises(ValidationError):
        EstateState(
            id="estate-invalid",
            deceasedName="Robert",
            dateOfDeath="2026-06-03",
            appointmentDate="2026-06-10",
            state="nevada",
            executor=Executor(name="Dana", email="dana@example.com"),
        )

    with pytest.raises(ValidationError):
        EstateState(
            id="estate-invalid",
            deceasedName="Robert",
            dateOfDeath="2026-06-03",
            appointmentDate="2026-06-10",
            executor=Executor(name="Dana", email="dana@example.com"),
            phase=7,
        )

    with pytest.raises(ValidationError):
        WillExtraction(confidence=1.5, rawChunks=[])


def test_document_extractions_validate_nested_estate_shapes() -> None:
    will = WillExtraction(
        confidence=0.9,
        executorName="Dana",
        beneficiaries=[{"id": "beneficiary-dana", "name": "Dana", "share": "100%"}],
        assets=[
            {
                "id": "asset-home",
                "type": "real_estate",
                "description": "1847 Marin Ave",
                "estimatedValue": 220000,
                "appraised": False,
            }
        ],
        rawChunks=["Dana receives the home."],
    )
    bank = BankStatementExtraction(
        confidence=0.8,
        institution="Wells Fargo",
        accountLast4="4412",
        accountType="checking",
        balance=38240,
        statementDate="2026-06-01",
        rawChunks=["Checking account ending 4412 has a balance of 38240."],
    )

    assert will.documentType == "will"
    assert will.assets[0] == Asset(
        id="asset-home",
        type="real_estate",
        description="1847 Marin Ave",
        estimatedValue=220000,
        appraised=False,
    )
    assert bank.documentType == "bank_statement"


def test_api_response_contracts_validate_union_payloads() -> None:
    alert = Alert(
        id="alert-inventory",
        severity="critical",
        type="deadline",
        title="Inventory due soon",
        body="File DE-160 before the deadline.",
        rule="CA Probate Code inventory",
        daysRemaining=9,
        actionRequired="Prepare inventory and appraisal.",
    )
    response = ParseDocumentResponse(
        estateId="demo-milligan",
        extraction={
            "documentType": "unknown",
            "confidence": 0.1,
            "rawChunks": ["unclassified"],
            "reason": "No known legal or financial document markers.",
        },
        alerts=[alert],
    )

    assert response.extraction.documentType == "unknown"
    assert response.alerts == [alert]


def test_search_result_contract_preserves_citation_metadata() -> None:
    result = SearchResult(
        text="Inventory and appraisal must be filed.",
        score=0.97,
        source="will.txt",
        documentType="will",
        chunkIndex=2,
        estateId="demo-milligan",
    )

    assert result.model_dump() == {
        "text": "Inventory and appraisal must be filed.",
        "score": 0.97,
        "source": "will.txt",
        "documentType": "will",
        "chunkIndex": 2,
        "estateId": "demo-milligan",
    }
