from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import os
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from phoenix.client import Client
from phoenix.evals import ClassificationEvaluator, LLM, async_evaluate_dataframe
from phoenix.evals.utils import to_annotation_dataframe


EVALUATOR_NAME = "deadline_next_steps_quality"
DEADLINE_SPAN_NAME = "deadline_agent.run"
CONTEXT_COLUMN = "attributes.deadline_agent.evaluation_context"
OUTPUT_COLUMN = "attributes.deadline_agent.evaluation_output"

DEADLINE_NEXT_STEPS_QUALITY_PROMPT = """You are evaluating Executor AI's DeadlineAgent, a California probate and estate administration assistant.

Determine whether the agent surfaced the correct next actions and prioritized them appropriately. Judge only from the supplied estate evidence and deterministic probate-rule output. Do not add outside facts or legal assumptions.

<estate_and_rule_evidence>
{{context}}
</estate_and_rule_evidence>

<deadline_agent_output>
{{output}}
</deadline_agent_output>

JUDGING CRITERIA

Correctness
- Does the output accurately reflect the estate state, uploaded documents, extracted facts, and deterministic probate rules?

Groundedness
- Does the output avoid inventing facts, deadlines, beneficiaries, assets, debts, court filings, documents, or legal requirements?

Prioritization
- Are blocking tasks, executor-liability risks, and critical probate actions ranked appropriately?

Actionability
- Does the output clearly tell the executor what to do next?

Clarity
- Is the explanation concise and understandable to a non-lawyer?

PENALIZE
- Hallucinated estate facts, documents, assets, debts, beneficiaries, deadlines, or legal requirements.
- Missing obvious blockers, prerequisites, or deadlines present in the evidence.
- Incorrect or irrelevant next actions.
- Confusing severity with timing.
- Treating a blocker, prerequisite, missing-information task, or other non-deadline as a fixed deadline without evidence.

REWARD
- Correct identification of blockers, prerequisites, missing information, and actual deadlines.
- Ranking the most important blocking or liability-sensitive action first.
- Clear reasoning tied directly to the supplied evidence.
- Explicit acknowledgement of uncertainty when required information is missing.

SCORING RUBRIC

1 = Poor
Hallucinates material facts or requirements, misses obvious blockers, recommends incorrect or irrelevant actions, or prioritizes clearly incorrectly.

2 = Weak
Shows some grounding but contains inaccuracies or weak prioritization, misses important blockers or deadlines, or gives only partially useful recommendations.

3 = Acceptable
Generally correct and identifies the main issue. Recommendations are usable but may miss nuance or prioritization opportunities.

4 = Strong
Correctly identifies blockers, deadlines, and prerequisites. Recommendations are actionable, clear, grounded, and well-prioritized.

5 = Excellent
Fully grounded in estate facts and documents; correctly distinguishes blockers, prerequisites, missing data, and actual deadlines; places the most important next action first; gives concise useful reasoning; and contains no unsupported assumptions.

Return exactly one score from 1 through 5. Always provide a concise explanation citing the supplied evidence and the most important reason for the score.
"""


def build_evaluator(provider: str, model: str) -> ClassificationEvaluator:
    return ClassificationEvaluator(
        name=EVALUATOR_NAME,
        llm=LLM(provider=provider, model=model),
        prompt_template=DEADLINE_NEXT_STEPS_QUALITY_PROMPT,
        choices={"1": 1, "2": 2, "3": 3, "4": 4, "5": 5},
        include_explanation=True,
        direction="maximize",
    )


def phoenix_base_url(explicit_base_url: str | None = None) -> str:
    if explicit_base_url:
        return explicit_base_url.rstrip("/")
    configured_base_url = os.getenv("PHOENIX_BASE_URL")
    if configured_base_url:
        return configured_base_url.rstrip("/")
    collector = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    return collector.removesuffix("/v1/traces").rstrip("/")


def select_deadline_agent_spans(spans: pd.DataFrame) -> pd.DataFrame:
    if spans.empty or "name" not in spans.columns:
        return spans.iloc[0:0].copy()

    mask = spans["name"].eq(DEADLINE_SPAN_NAME)
    metadata_filters = []
    for column, expected in (
        ("attributes.agent_name", "DeadlineAgent"),
        ("attributes.action_type", "deadline_agent_run"),
        ("attributes.route", "/deadline-agent"),
    ):
        if column in spans.columns:
            metadata_filters.append(spans[column].eq(expected))
    if metadata_filters:
        metadata_match = metadata_filters[0]
        for candidate in metadata_filters[1:]:
            metadata_match = metadata_match | candidate
        mask = mask & metadata_match

    selected = spans.loc[mask].copy()
    if CONTEXT_COLUMN not in selected.columns or OUTPUT_COLUMN not in selected.columns:
        return selected.iloc[0:0].copy()
    return selected.loc[
        selected[CONTEXT_COLUMN].notna()
        & selected[OUTPUT_COLUMN].notna()
        & selected[CONTEXT_COLUMN].astype(str).str.len().gt(0)
        & selected[OUTPUT_COLUMN].astype(str).str.len().gt(0)
    ].copy()


def evaluation_dataframe(spans: pd.DataFrame) -> pd.DataFrame:
    dataframe = pd.DataFrame(index=spans.index.copy())
    dataframe.index.name = spans.index.name or "context.span_id"
    dataframe["context"] = spans[CONTEXT_COLUMN].astype(str)
    dataframe["output"] = spans[OUTPUT_COLUMN].astype(str)
    if "context.span_id" in spans.columns:
        dataframe["context.span_id"] = spans["context.span_id"]
    return dataframe


async def run(args: argparse.Namespace) -> int:
    load_dotenv(".env")
    base_url = phoenix_base_url(args.base_url)
    project = args.project or os.getenv("PHOENIX_PROJECT_NAME", "executor-ai-agent")
    provider = args.provider or os.getenv("PHOENIX_EVAL_PROVIDER", "anthropic")
    model = args.model or os.getenv("PHOENIX_EVAL_MODEL", "claude-sonnet-4-6")
    api_key = os.getenv("PHOENIX_API_KEY") or None

    client = Client(base_url=base_url, api_key=api_key)
    start_time = None
    if args.hours is not None:
        start_time = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    spans = client.spans.get_spans_dataframe(
        project_identifier=project,
        start_time=start_time,
        limit=args.limit,
        timeout=args.timeout,
    )
    selected = select_deadline_agent_spans(spans)
    if selected.empty:
        print(
            "No evaluable DeadlineAgent spans found. Set "
            "PHOENIX_CAPTURE_EVAL_CONTEXT=true, restart the agent, and run /deadline-agent first."
        )
        return 0

    evaluator = build_evaluator(provider, model)
    results = await async_evaluate_dataframe(
        dataframe=evaluation_dataframe(selected),
        evaluators=[evaluator],
        concurrency=args.concurrency,
        exit_on_error=False,
        max_retries=args.max_retries,
        hide_tqdm_bar=args.hide_progress,
    )

    score_column = f"{EVALUATOR_NAME}_score"
    successful_scores = 0
    for span_id, result in results[score_column].items():
        score: dict[str, Any] = result if isinstance(result, dict) else {}
        numeric_score = score.get("score")
        explanation = score.get("explanation", "")
        if numeric_score is not None:
            successful_scores += 1
        print(f"span={span_id} score={numeric_score} explanation={explanation}")

    if not args.no_log:
        annotations = to_annotation_dataframe(results, [EVALUATOR_NAME])
        if not annotations.empty:
            client.spans.log_span_annotations_dataframe(
                dataframe=annotations,
                annotator_kind="LLM",
                annotation_name=EVALUATOR_NAME,
                sync=True,
            )
            print(f"Logged {len(annotations)} {EVALUATOR_NAME} annotations to Phoenix project {project}.")

    print(f"Evaluated {successful_scores}/{len(results)} DeadlineAgent spans.")
    return 0 if successful_scores == len(results) else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate DeadlineAgent next-step quality from Phoenix traces.",
    )
    parser.add_argument("--project", help="Phoenix project name or ID.")
    parser.add_argument("--base-url", help="Phoenix application base URL.")
    parser.add_argument("--provider", help="Judge provider, such as anthropic or openai.")
    parser.add_argument("--model", help="Judge model name.")
    parser.add_argument("--limit", type=int, default=500, help="Maximum recent spans to fetch.")
    parser.add_argument("--hours", type=float, help="Only evaluate spans from the last N hours.")
    parser.add_argument("--timeout", type=int, default=30, help="Phoenix query timeout in seconds.")
    parser.add_argument("--concurrency", type=int, default=3, help="Concurrent judge calls.")
    parser.add_argument("--max-retries", type=int, default=3, help="Retries per judge call.")
    parser.add_argument("--no-log", action="store_true", help="Evaluate without writing annotations.")
    parser.add_argument("--hide-progress", action="store_true", help="Hide the batch progress bar.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
