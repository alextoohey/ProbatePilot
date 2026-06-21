from __future__ import annotations

import json
from typing import Any


ATTORNEY_INPUT_SENTENCE = "This requires your attorney's input — it involves [reason]."

BASE_CHAT_SYSTEM_PROMPT = f"""You are an estate administration assistant helping an executor manage a California estate.

RULES YOU MUST FOLLOW:
- California probate only.
- Answer from the estate state and retrieved documents below, not generic probate advice.
- When citing a deadline, always include the exact date and the consequence of missing it.
- If you do not have a fact, such as an account number, filing date, publication date, or document status, say so explicitly.
- Never give legal advice. For attorney-judgment questions, say exactly:
  "{ATTORNEY_INPUT_SENTENCE}"
- You may still explain operational next steps, deadlines, documents to gather, and what information is missing.
- Keep tone warm and direct. This person is grieving. Never be clinical.
- If the user sounds overwhelmed, surface only the single most urgent next action.
- Always answer in plain English. Define any legal term you use.

TODO: Add Anthropic prompt caching for the stable instruction + estate-state prefix once the SDK path is settled for this service.
"""


def build_chat_prompt(estate_json: str, retrieved_chunks: list[str]) -> str:
    estate = _parse_estate_json(estate_json)
    deceased_name = estate.get("deceasedName", "the deceased")
    date_of_death = estate.get("dateOfDeath", "unknown")
    executor_name = (estate.get("executor") or {}).get("name", "the executor")
    appointment_date = estate.get("appointmentDate", "unknown")
    state = estate.get("state", "california")
    chunks = _format_retrieved_chunks(retrieved_chunks)

    return (
        f"{BASE_CHAT_SYSTEM_PROMPT}\n"
        f"You are helping {executor_name} manage the estate of {deceased_name}, "
        f"who passed away on {date_of_death}.\n\n"
        f"This estate is in {state.title()}. Letters testamentary were issued on {appointment_date}, "
        "meaning the executor has had legal authority since that date.\n\n"
        f"DECEASED NAME:\n{deceased_name}\n\n"
        f"DATE OF DEATH:\n{date_of_death}\n\n"
        f"EXECUTOR NAME:\n{executor_name}\n\n"
        f"APPOINTMENT DATE:\n{appointment_date}\n\n"
        f"ESTATE STATE JSON:\n{_stable_json(estate)}\n\n"
        f"RETRIEVED DOCUMENT CONTEXT:\n{chunks}"
    )


def _parse_estate_json(estate_json: str) -> dict[str, Any]:
    try:
        parsed = json.loads(estate_json)
    except json.JSONDecodeError:
        return {"rawEstateState": estate_json}
    return parsed if isinstance(parsed, dict) else {"rawEstateState": parsed}


def _format_retrieved_chunks(retrieved_chunks: list[str]) -> str:
    if not retrieved_chunks:
        return "No retrieved document context was available for this question."
    return "\n\n".join(f"[{index}] {chunk}" for index, chunk in enumerate(retrieved_chunks, start=1))


def _stable_json(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True)
