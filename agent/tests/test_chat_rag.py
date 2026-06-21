from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

import main
from llm.claude import stream_chat
from prompts.system import ATTORNEY_INPUT_SENTENCE, build_chat_prompt
from seed.demo_estate import build_demo_estate
from store.redis_client import seed_demo_estate


def test_build_chat_prompt_includes_estate_facts_and_retrieved_chunks() -> None:
    estate = build_demo_estate()
    prompt = build_chat_prompt(
        estate.model_dump_json(),
        ["Will names Dana as executor.", "Bank statement shows Wells Fargo checking ...4412."],
    )

    assert "Robert A. Milligan" in prompt
    assert "2026-06-03" in prompt
    assert "Dana Milligan" in prompt
    assert "2026-06-10" in prompt
    assert "Will names Dana as executor." in prompt
    assert "Bank statement shows Wells Fargo checking ...4412." in prompt
    assert "ESTATE STATE JSON" in prompt


def test_build_chat_prompt_includes_exact_attorney_input_sentence() -> None:
    prompt = build_chat_prompt(build_demo_estate().model_dump_json(), [])

    assert ATTORNEY_INPUT_SENTENCE in prompt
    assert "California probate only" in prompt


def test_stream_chat_works_without_anthropic_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    async def collect_tokens() -> str:
        return "".join([token async for token in stream_chat("prompt", "What is next?")])

    response = asyncio.run(collect_tokens())

    assert "most urgent next action" in response
    assert "notify known creditors" in response


def test_stream_chat_attorney_guardrail_offline(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    async def collect_tokens() -> str:
        return "".join([token async for token in stream_chat("prompt", "Can I legally disinherit someone?")])

    response = asyncio.run(collect_tokens())

    assert "This requires your attorney's input — it involves legal advice." in response


def test_chat_sse_streams_with_retrieval_failure(monkeypatch) -> None:
    seed_demo_estate()

    def failing_embed_query(message: str) -> list[float]:
        raise RuntimeError("embedding unavailable")

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(main, "embed_query", failing_embed_query)
    client = TestClient(main.app)

    response = client.post(
        "/chat",
        json={"estateId": "demo-milligan", "message": "What should I do next?", "topK": 3},
    )

    assert response.status_code == 200
    assert 'data: {"token":' in response.text
    assert "data: [DONE]" in response.text


def test_chat_sse_persists_exchange_after_stream(monkeypatch) -> None:
    seed_demo_estate()

    def failing_embed_query(message: str) -> list[float]:
        raise RuntimeError("embedding unavailable")

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(main, "embed_query", failing_embed_query)
    client = TestClient(main.app)

    response = client.post(
        "/chat",
        json={"estateId": "demo-milligan", "message": "What should I do next?", "topK": 3},
    )
    history = client.get("/chat-history/demo-milligan")

    assert response.status_code == 200
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "What should I do next?"
    assert "most urgent next action" in messages[1]["content"]


def test_chat_sessions_keep_past_chats_separate(monkeypatch) -> None:
    seed_demo_estate()

    def failing_embed_query(message: str) -> list[float]:
        raise RuntimeError("embedding unavailable")

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(main, "embed_query", failing_embed_query)
    client = TestClient(main.app)

    first = client.post("/chat-sessions/demo-milligan").json()["session"]
    second = client.post("/chat-sessions/demo-milligan").json()["session"]
    client.post("/chat", json={"estateId": "demo-milligan", "sessionId": first["id"], "message": "First chat question"})
    client.post("/chat", json={"estateId": "demo-milligan", "sessionId": second["id"], "message": "Second chat question"})

    sessions = client.get("/chat-sessions/demo-milligan").json()["sessions"]
    first_history = client.get(f"/chat-history/demo-milligan?sessionId={first['id']}").json()["messages"]
    second_history = client.get(f"/chat-history/demo-milligan?sessionId={second['id']}").json()["messages"]

    assert {s["id"] for s in sessions} == {first["id"], second["id"]}
    assert sessions[0]["messageCount"] == 2
    assert first_history[0]["content"] == "First chat question"
    assert second_history[0]["content"] == "Second chat question"
