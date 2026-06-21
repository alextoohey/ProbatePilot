from __future__ import annotations

import json

import pytest

from schemas.estate import Alert, EstateState, Executor
from store import redis_client


def test_key_helpers_follow_shared_redis_contract() -> None:
    assert redis_client.estate_key("demo-milligan") == "estate:demo-milligan"
    assert redis_client.vector_set_key("demo-milligan") == "estate:demo-milligan:chunks"
    assert redis_client.chunk_id("estate-1", "will.pdf", 4) == "estate-1:will.pdf:4"
    assert redis_client.chunk_id("estate-1", None, 0) == "estate-1:document:0"


def test_seed_demo_estate_writes_and_round_trips_memory_store() -> None:
    redis_client.upsert_vectors("demo-milligan", ["old chunk"], [[1.0, 0.0]], source="old.txt")

    seeded = redis_client.seed_demo_estate()
    loaded = redis_client.get_estate_state("demo-milligan")

    assert loaded == seeded
    assert loaded.executor.name == "Dana Milligan"
    assert redis_client.semantic_search("demo-milligan", [1.0, 0.0]) == []


def test_get_estate_state_auto_seeds_default_but_not_unknown_estates() -> None:
    default_estate = redis_client.get_estate_state()

    assert default_estate.id == "demo-milligan"
    with pytest.raises(KeyError):
        redis_client.get_estate_state("missing-estate")


def test_set_estate_state_validates_and_updates_timestamp() -> None:
    estate = EstateState(
        id="estate-123",
        deceasedName="Robert",
        dateOfDeath="2026-06-03",
        appointmentDate="2026-06-10",
        executor=Executor(name="Dana", email="dana@example.com"),
        updatedAt="2000-01-01T00:00:00+00:00",
    )

    saved = redis_client.set_estate_state(estate)
    loaded = redis_client.get_estate_state("estate-123")

    assert saved.updatedAt != "2000-01-01T00:00:00+00:00"
    assert loaded == saved
    assert loaded is not saved


def test_merge_estate_state_creates_blank_estate_and_deep_merges() -> None:
    estate = redis_client.merge_estate_state(
        "estate-new",
        {
            "deceasedName": "Robert A. Milligan",
            "dateOfDeath": "2026-06-03",
            "appointmentDate": "2026-06-10",
            "executor": {"name": "Dana Milligan", "email": "dana@example.com"},
            "assets": [
                {
                    "id": "asset-home",
                    "type": "real_estate",
                    "description": "1847 Marin Ave",
                    "estimatedValue": 220000,
                    "appraised": False,
                }
            ],
        },
    )

    assert estate.id == "estate-new"
    assert estate.deceasedName == "Robert A. Milligan"
    assert estate.executor.name == "Dana Milligan"
    assert estate.assets[0].description == "1847 Marin Ave"

    merged = redis_client.merge_estate_state(
        "estate-new",
        {
            "executor": {"email": "updated@example.com"},
            "assets": [
                {"id": "asset-home", "appraised": True, "appraisedValue": 230000},
                {
                    "id": "asset-car",
                    "type": "vehicle",
                    "description": "2019 Honda Civic",
                    "estimatedValue": 12000,
                    "appraised": False,
                },
            ],
        },
    )

    assert merged.executor.name == "Dana Milligan"
    assert merged.executor.email == "updated@example.com"
    assert len(merged.assets) == 2
    assert merged.assets[0].id == "asset-home"
    assert merged.assets[0].appraised is True
    assert merged.assets[0].appraisedValue == 230000


def test_write_alerts_replaces_alerts_and_preserves_contract() -> None:
    redis_client.seed_demo_estate()
    alert = Alert(
        id="alert-creditors",
        severity="critical",
        type="deadline",
        title="Notify creditors",
        body="Known creditors must be notified.",
        rule="CA creditor notice",
        actionRequired="Send certified notices.",
    )

    written = redis_client.write_alerts("demo-milligan", [alert])
    assert written == [alert]
    assert redis_client.get_alerts("demo-milligan") == [alert]

    assert redis_client.write_alerts("demo-milligan", []) == []
    assert redis_client.get_alerts("demo-milligan") == []


def test_memory_vector_upsert_search_filters_by_estate_and_ranks() -> None:
    redis_client.upsert_vectors(
        "estate-a",
        ["home appraisal deadline", "creditor notice window"],
        [[1.0, 0.0], [0.0, 1.0]],
        source="a.txt",
        document_type="will",
    )
    redis_client.upsert_vectors(
        "estate-b",
        ["same vector different estate"],
        [[1.0, 0.0]],
        source="b.txt",
        document_type="deed",
    )

    matches = redis_client.semantic_search("estate-a", [0.9, 0.1], top_k=2)

    assert [match.text for match in matches] == ["home appraisal deadline", "creditor notice window"]
    assert all(match.estateId == "estate-a" for match in matches)
    assert matches[0].source == "a.txt"
    assert matches[0].documentType == "will"
    assert matches[0].chunkIndex == 0


def test_vector_upsert_validates_parallel_lists_and_replaces_chunk_ids() -> None:
    with pytest.raises(ValueError):
        redis_client.upsert_vectors("estate-a", ["one"], [])

    assert redis_client.upsert_vectors("estate-a", ["original"], [[1.0]], source="same.txt") == 1
    assert redis_client.upsert_vectors("estate-a", ["replacement"], [[1.0]], source="same.txt") == 1

    matches = redis_client.semantic_search("estate-a", [1.0], top_k=5)
    assert [match.text for match in matches] == ["replacement"]


def test_clear_estate_vectors_only_removes_requested_estate() -> None:
    redis_client.upsert_vectors("estate-a", ["a"], [[1.0]], source="a.txt")
    redis_client.upsert_vectors("estate-b", ["b"], [[1.0]], source="b.txt")

    assert redis_client.clear_estate_vectors("estate-a") == 1
    assert redis_client.semantic_search("estate-a", [1.0]) == []
    assert redis_client.semantic_search("estate-b", [1.0])[0].text == "b"


def test_redis_cloud_match_parser_accepts_dict_and_flat_responses() -> None:
    attributes = json.dumps(
        {
            "text": "Inventory is due.",
            "source": "inventory.pdf",
            "documentType": "deed",
            "chunkIndex": 3,
            "estateId": "demo-milligan",
        }
    )

    dict_results = redis_client._parse_redis_cloud_vector_matches({"chunk-1": [0.99, attributes]}, "fallback")
    flat_results = redis_client._parse_redis_cloud_vector_matches(["chunk-1", "0.99", attributes], "fallback")

    for results in (dict_results, flat_results):
        assert len(results) == 1
        assert results[0].text == "Inventory is due."
        assert results[0].score == pytest.approx(0.99)
        assert results[0].source == "inventory.pdf"
        assert results[0].documentType == "deed"
        assert results[0].chunkIndex == 3
        assert results[0].estateId == "demo-milligan"


def test_redis_cloud_dimension_guard_deletes_mismatched_vector_set() -> None:
    class FakeRedis:
        def __init__(self) -> None:
            self.deleted: list[str] = []

        def exists(self, key: str) -> int:
            return 1

        def execute_command(self, command: str, key: str) -> int:
            assert command == "VDIM"
            assert key == "estate:demo-milligan:chunks"
            return 512

        def delete(self, key: str) -> int:
            self.deleted.append(key)
            return 1

    fake = FakeRedis()
    redis_client._ensure_redis_cloud_vector_dimension(fake, "estate:demo-milligan:chunks", 1536)

    assert fake.deleted == ["estate:demo-milligan:chunks"]
