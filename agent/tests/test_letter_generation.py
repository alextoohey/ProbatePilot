from __future__ import annotations

from fastapi.testclient import TestClient

import main
from prompts.letters import build_letter_fallback, build_letter_prompt
from seed.demo_estate import build_demo_estate
from store.redis_client import seed_demo_estate


def test_creditor_notice_fallback_includes_demo_estate_facts() -> None:
    estate = build_demo_estate()

    draft = build_letter_fallback(estate, "creditor_notice", "UCSF Medical Center")

    assert "UCSF Medical Center" in draft
    assert "Estate of Robert A. Milligan" in draft
    assert "Dana Milligan" in draft
    assert "2026-06-10" in draft
    assert "California Probate Code §9051" in draft
    assert "claim information" in draft
    assert "Executor of the Estate of Robert A. Milligan" in draft


def test_unknown_letter_type_uses_safe_creditor_notice_default() -> None:
    estate = build_demo_estate()

    draft = build_letter_fallback(estate, "unexpected_type", "Known Creditor")

    assert "Known Creditor" in draft
    assert "California Probate Code §9051" in draft
    assert "Estate of Robert A. Milligan" in draft


def test_generate_letter_route_works_without_anthropic_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    seed_demo_estate()
    client = TestClient(main.app)

    response = client.post(
        "/generate-letter",
        json={
            "estateId": "demo-milligan",
            "letterType": "creditor_notice",
            "recipientName": "UCSF Medical Center",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["estateId"] == "demo-milligan"
    assert payload["letterType"] == "creditor_notice"
    assert "UCSF Medical Center" in payload["draft"]
    assert "California Probate Code §9051" in payload["draft"]


def test_generated_fallback_does_not_contain_placeholder_word() -> None:
    draft = build_letter_fallback(build_demo_estate(), "creditor_notice", "UCSF Medical Center")

    assert "placeholder" not in draft.casefold()


def test_letter_prompt_includes_estate_facts_and_letter_type() -> None:
    estate = build_demo_estate()

    prompt = build_letter_prompt(estate, "bank_notification", "Wells Fargo")

    assert "Letter type: bank_notification" in prompt
    assert "Robert A. Milligan" in prompt
    assert "2026-06-03" in prompt
    assert "Dana Milligan" in prompt
    assert "dana@demo.com" in prompt
    assert "2026-06-10" in prompt
    assert "Wells Fargo" in prompt


def test_generate_letter_route_uses_claude_helper_when_configured(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def fake_generate_letter_draft(
        *,
        prompt: str,
        letter_type: str,
        fallback: str,
        estate_id: str | None = None,
    ) -> str:
        calls.append({"prompt": prompt, "letter_type": letter_type, "fallback": fallback, "estate_id": estate_id})
        return "Claude drafted letter"

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(main, "generate_letter_draft", fake_generate_letter_draft)
    seed_demo_estate()
    client = TestClient(main.app)

    response = client.post(
        "/generate-letter",
        json={
            "estateId": "demo-milligan",
            "letterType": "beneficiary_update",
            "recipientName": "Sarah Milligan",
        },
    )

    assert response.status_code == 200
    assert response.json()["draft"] == "Claude drafted letter"
    assert calls[0]["letter_type"] == "beneficiary_update"
    assert calls[0]["estate_id"] == "demo-milligan"
    assert "Sarah Milligan" in str(calls[0]["prompt"])
