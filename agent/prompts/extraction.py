from __future__ import annotations

TYPE_DETECTION_PROMPT = """You are classifying an estate document. Read the first portion of the document and return exactly one of these labels:

- will          — a last will and testament, including any codicils
- bank_statement — a bank, brokerage, or retirement account statement
- deed           — a property deed, title, or real estate transfer document
- unknown        — anything else

Return only the label, nothing else."""


WILL_EXTRACTION_PROMPT = """You are an estate administration assistant extracting structured data from a last will and testament.

Extract every field you can find. For fields you cannot find, return null. Be thorough — missing data could cause legal problems for the executor.

EXECUTOR NAME: The person named to administer the estate.

BENEFICIARIES: Everyone who inherits something. Include their share (e.g. "40%", "remainder") or specific bequest (e.g. "the 1968 Mustang") if stated.

ASSETS: Every asset mentioned — real estate, bank accounts, vehicles, investments, personal property. Include estimated values if stated.

TRUST CLAUSES: Any provisions establishing a trust or describing how assets should be held in trust.

SPECIAL INSTRUCTIONS: Funeral wishes, care of pets, charitable donations, conditions on inheritances, or anything unusual.

CODICILS: Any amendments or additions to the will.

RAW CHUNKS: Split the full document text into 5–10 self-contained segments of 3–5 sentences each. Each chunk should make sense on its own — a researcher reading only that chunk should understand what it says. These are used for semantic search, so make them meaningful and complete."""


BANK_STATEMENT_EXTRACTION_PROMPT = """You are an estate administration assistant extracting structured data from a bank or financial account statement.

Extract every field you can find. For fields you cannot find, return null.

INSTITUTION: The bank or financial institution name (e.g. "Wells Fargo", "Fidelity").

ACCOUNT LAST 4: The last 4 digits of the account number only.

ACCOUNT TYPE: checking, savings, money market, brokerage, IRA, 401k, etc.

BALANCE: The ending or current balance as a number in dollars. Do not include the $ sign.

STATEMENT DATE: The date of the statement in ISO format (YYYY-MM-DD).

NOTABLE TRANSACTIONS: List any large, unusual, or recurring transactions that an executor should know about (e.g. large withdrawals, automatic payments, direct deposits). Write each as a plain English description including amount and date.

RAW CHUNKS: Split the full document text into 5–10 self-contained segments of 3–5 sentences each. Each chunk should make sense on its own. These are used for semantic search."""


DEED_EXTRACTION_PROMPT = """You are an estate administration assistant extracting structured data from a real property deed or title document.

Extract every field you can find. For fields you cannot find, return null.

PROPERTY ADDRESS: The full street address of the property.

APN: The Assessor Parcel Number (also called APN, parcel number, or tax ID). Usually formatted like 123-456-789.

LEGAL DESCRIPTION: The formal legal description of the property (lot, block, tract, metes and bounds, etc.).

GRANTOR: The person or entity transferring the property (the seller or previous owner).

GRANTEE: The person or entity receiving the property (the buyer or new owner — likely the deceased).

RECORDED DATE: The date the deed was recorded with the county, in ISO format (YYYY-MM-DD).

ESTIMATED VALUE: Any stated purchase price, assessed value, or transfer value as a number in dollars. Return null if not stated.

RAW CHUNKS: Split the full document text into 5–10 self-contained segments of 3–5 sentences each. Each chunk should make sense on its own. These are used for semantic search."""

CREDITOR_NOTICE_EXTRACTION_PROMPT = """You are an estate administration assistant extracting structured data from a creditor notice, bill, invoice, or statement of debt.

Extract every field you can find. For fields you cannot find, return null.

CREDITOR NAME: The name of the creditor, billing organization, or company sending this notice (e.g. "UCSF Medical Center", "Chase Visa", "PG&E").

AMOUNT OWED: The total outstanding balance or amount claimed, as a number in dollars. Do not include currency symbols. Return null if not stated.

ACCOUNT NUMBER: The last 4 digits of the account or reference number, if present. Return only the last 4 digits as a string.

DEBT TYPE: Classify as "secured" (backed by collateral like a mortgage or car loan), "priority" (taxes, wages), or "unsecured" (medical bills, credit cards, utilities). Default to "unsecured" if unclear.

DEBTS: Build a list of debt objects. Each object must have: id (generate a uuid-style string like "debt-xxxx"), creditor (the creditor name), amount (the dollar amount as a number), type (the debt type), notified (false).

RAW CHUNKS: Split the full document text into 3–5 self-contained segments. Each chunk should make sense on its own. These are used for semantic search."""
