from __future__ import annotations

import pandas as pd

from evals.deadline_next_steps_quality import (
    CONTEXT_COLUMN,
    DEADLINE_NEXT_STEPS_QUALITY_PROMPT,
    EVALUATOR_NAME,
    OUTPUT_COLUMN,
    evaluation_dataframe,
    phoenix_base_url,
    select_deadline_agent_spans,
)


def test_rubric_has_expected_name_scale_and_grounding_requirements() -> None:
    assert EVALUATOR_NAME == "deadline_next_steps_quality"
    assert all(f"{score} =" in DEADLINE_NEXT_STEPS_QUALITY_PROMPT for score in range(1, 6))
    assert "Hallucinated estate facts" in DEADLINE_NEXT_STEPS_QUALITY_PROMPT
    assert "Confusing severity with timing" in DEADLINE_NEXT_STEPS_QUALITY_PROMPT
    assert "Always provide a concise explanation" in DEADLINE_NEXT_STEPS_QUALITY_PROMPT


def test_selects_only_deadline_agent_spans_with_evaluation_payload() -> None:
    spans = pd.DataFrame(
        [
            {
                "context.span_id": "deadline-span",
                "name": "deadline_agent.run",
                "attributes.agent_name": "DeadlineAgent",
                "attributes.action_type": "deadline_agent_run",
                CONTEXT_COLUMN: '{"estateState": {}}',
                OUTPUT_COLUMN: '{"alerts": []}',
            },
            {
                "context.span_id": "chat-span",
                "name": "llm.stream_chat",
                "attributes.action_type": "chat_query",
                CONTEXT_COLUMN: "chat context",
                OUTPUT_COLUMN: "chat output",
            },
            {
                "context.span_id": "old-deadline-span",
                "name": "deadline_agent.run",
                "attributes.action_type": "deadline_agent_run",
            },
        ]
    ).set_index("context.span_id", drop=False)

    selected = select_deadline_agent_spans(spans)

    assert list(selected.index) == ["deadline-span"]
    evaluator_input = evaluation_dataframe(selected)
    assert evaluator_input.loc["deadline-span", "context"] == '{"estateState": {}}'
    assert evaluator_input.loc["deadline-span", "output"] == '{"alerts": []}'


def test_phoenix_base_url_accepts_collector_url(monkeypatch) -> None:
    monkeypatch.delenv("PHOENIX_BASE_URL", raising=False)
    monkeypatch.setenv(
        "PHOENIX_COLLECTOR_ENDPOINT",
        "https://app.phoenix.arize.com/s/executor-ai/v1/traces",
    )

    assert phoenix_base_url() == "https://app.phoenix.arize.com/s/executor-ai"
