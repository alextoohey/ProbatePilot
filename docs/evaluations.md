# DeadlineAgent Evaluation

`deadline_next_steps_quality` is an LLM-as-a-judge evaluator for the DeadlineAgent's
ranked alerts and recommended next actions. It scores each run from 1 to 5 and always
returns an explanation.

## Evidence and trace selection

The evaluator selects only spans that satisfy all available identifiers:

- span name: `deadline_agent.run`
- agent metadata: `DeadlineAgent`
- action type: `deadline_agent_run`
- route: `/deadline-agent`

Each evaluable span contains an opt-in snapshot of the estate state, uploaded document
status, existing tasks and alerts, deterministic probate-rule alerts, and the final ranked
DeadlineAgent output. This lets the judge evaluate correctness, groundedness,
prioritization, actionability, and clarity using evidence from the same run.

## Configuration

Add these values to `agent/.env`, then restart the agent:

```bash
PHOENIX_CAPTURE_EVAL_CONTEXT=true
PHOENIX_EVAL_PROVIDER=anthropic
PHOENIX_EVAL_MODEL=claude-sonnet-4-6
```

The judge uses the selected provider's existing API key. The captured evidence can contain
sensitive estate facts, so context capture is disabled by default.

## Run and annotate

Generate at least one new DeadlineAgent trace, then run:

```bash
make eval-deadline
```

Equivalent direct command:

```bash
cd agent
uv run python -m evals.deadline_next_steps_quality \
  --project probatepilot-agent \
  --limit 500 \
  --concurrency 3
```

The script prints every score and explanation, converts the results to Phoenix span
annotations, and logs them under `deadline_next_steps_quality`. Useful options:

- `--hours 24`: evaluate only recent spans.
- `--no-log`: run the judge without writing annotations.
- `--provider openai --model <model>`: use a different judge.
- `--base-url <url>`: override the Phoenix application URL.
