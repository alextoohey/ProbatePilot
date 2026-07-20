"""Writes structured facts extracted from an uploaded document back into
estate state, deduping against what's already recorded."""

from __future__ import annotations

import uuid
from typing import Any

from schemas.api import AnyDocumentExtraction
from schemas.documents import BankStatementExtraction, CreditorNoticeExtraction, DeedExtraction, WillExtraction
from schemas.estate import Asset
from store.redis_client import get_estate_state, merge_estate_state


def merge_extraction(estate_id: str, extraction: AnyDocumentExtraction) -> None:
    try:
        estate = get_estate_state(estate_id)
    except KeyError:
        estate = None
    partial: dict[str, Any] = {}

    existing_assets = estate.assets if estate else []
    existing_bens = estate.beneficiaries if estate else []

    if isinstance(extraction, WillExtraction):
        if extraction.beneficiaries:
            existing_names = {b.name.lower().strip() for b in existing_bens}
            new_bens = [
                b for b in extraction.beneficiaries
                if b.name.lower().strip() not in existing_names
            ]
            if new_bens:
                partial["beneficiaries"] = new_bens

        if extraction.assets:
            existing_descs = {a.description.lower().strip() for a in existing_assets}
            new_assets = [
                a for a in extraction.assets
                if a.description.lower().strip() not in existing_descs
            ]
            if new_assets:
                partial["assets"] = new_assets

    elif isinstance(extraction, BankStatementExtraction):
        parts = [
            extraction.institution,
            f"account ending {extraction.accountLast4}" if extraction.accountLast4 else None,
            f"({extraction.accountType})" if extraction.accountType else None,
        ]
        description = " ".join(p for p in parts if p) or "Bank account"
        existing = next(
            (a for a in existing_assets
             if a.type == "bank_account" and extraction.accountLast4
             and extraction.accountLast4 in a.description),
            None,
        ) if estate else None
        if existing:
            existing.description = description
            existing.estimatedValue = extraction.balance or existing.estimatedValue
            partial["assets"] = [existing]
        else:
            partial["assets"] = [Asset(
                id=f"asset-bank-{uuid.uuid4().hex[:8]}",
                type="bank_account",
                description=description,
                estimatedValue=extraction.balance,
            )]

    elif isinstance(extraction, CreditorNoticeExtraction):
        existing_debts = estate.debts if estate else []
        existing_creditors = {d.creditor.lower().strip() for d in existing_debts}
        new_debts = [
            d for d in extraction.debts
            if d.creditor.lower().strip() not in existing_creditors
        ]
        if new_debts:
            partial["debts"] = new_debts

    elif isinstance(extraction, DeedExtraction) and extraction.propertyAddress:
        addr_key = extraction.propertyAddress.lower()[:30]
        existing = next(
            (a for a in existing_assets
             if a.type == "real_estate" and addr_key in a.description.lower()),
            None,
        ) if estate else None
        if existing:
            existing.estimatedValue = extraction.estimatedValue or existing.estimatedValue
            partial["assets"] = [existing]
        else:
            partial["assets"] = [Asset(
                id=f"asset-re-{uuid.uuid4().hex[:8]}",
                type="real_estate",
                description=f"Property at {extraction.propertyAddress}",
                estimatedValue=extraction.estimatedValue,
            )]

    if partial:
        merge_estate_state(estate_id, partial)
