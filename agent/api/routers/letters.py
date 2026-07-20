from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from api.deps import ensure_estate_access, optional_user, require_estate_access
from llm.claude import generate_letter_draft
from observability.phoenix import set_span_attribute, span
from prompts.letters import (
    CUSTOM_LETTER_TYPE,
    build_custom_letter_fallback,
    build_custom_letter_prompt,
    build_letter_fallback,
    build_letter_prompt,
    normalize_letter_type,
)
from schemas.api import GenerateLetterRequest, SaveLetterRequest
from schemas.auth import User
from schemas.estate import SavedLetter
from store.redis_client import delete_letter, get_estate_state, merge_estate_state

router = APIRouter(tags=["letters"])


@router.post("/generate-letter")
async def generate_letter(request: GenerateLetterRequest, user: User | None = Depends(optional_user)) -> dict[str, object]:
    ensure_estate_access(request.estateId, user)
    letter_type = normalize_letter_type(request.letterType, allow_custom=True)
    with span(
        "route.generate_letter",
        estate_id=request.estateId,
        action_type="letter_generation",
        letter_type=letter_type,
    ) as current_span:
        try:
            estate_state = get_estate_state(request.estateId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Estate not found") from exc
        if letter_type == CUSTOM_LETTER_TYPE:
            prompt = build_custom_letter_prompt(estate_state, request.instructions, request.recipientName)
            fallback = build_custom_letter_fallback(estate_state, request.instructions, request.recipientName)
        else:
            prompt = build_letter_prompt(estate_state, letter_type, request.recipientName)
            fallback = build_letter_fallback(estate_state, letter_type, request.recipientName)
        set_span_attribute(current_span, "prompt_length", len(prompt))
        draft = await generate_letter_draft(
            prompt=prompt,
            letter_type=letter_type,
            fallback=fallback,
            estate_id=request.estateId,
        )
        return {"estateId": request.estateId, "letterType": letter_type, "draft": draft}


@router.delete("/letter/{estate_id}/{letter_id}", dependencies=[Depends(require_estate_access)])
async def delete_letter_route(estate_id: str, letter_id: str) -> dict[str, object]:
    removed = delete_letter(estate_id, letter_id)
    if removed is None:
        raise HTTPException(status_code=404, detail="Letter not found.")
    return {"estateId": estate_id, "deletedLetterId": letter_id}


@router.post("/save-letter")
async def save_letter(request: SaveLetterRequest, user: User | None = Depends(optional_user)) -> dict[str, object]:
    ensure_estate_access(request.estateId, user)
    letter = SavedLetter(
        id=f"letter-{uuid.uuid4().hex[:8]}",
        letterType=request.letterType,
        recipientName=request.recipientName,
        draft=request.draft,
    )
    merge_estate_state(request.estateId, {"letters": [letter.model_dump()]})
    return {"estateId": request.estateId, "letter": letter}
