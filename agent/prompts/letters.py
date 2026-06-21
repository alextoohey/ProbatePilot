from __future__ import annotations

import json
from typing import Any

from schemas.estate import EstateState


SUPPORTED_LETTER_TYPES = {
    "creditor_notice",
    "bank_notification",
    "irs_ein_request",
    "beneficiary_update",
    "property_transfer",
}
DEFAULT_LETTER_TYPE = "creditor_notice"


LETTER_TYPE_LABELS = {
    "creditor_notice": "California probate creditor notice",
    "bank_notification": "estate bank notification",
    "irs_ein_request": "IRS EIN request preparation",
    "beneficiary_update": "beneficiary status update",
    "property_transfer": "property transfer preparation",
}


def normalize_letter_type(letter_type: str | None) -> str:
    if letter_type in SUPPORTED_LETTER_TYPES:
        return str(letter_type)
    return DEFAULT_LETTER_TYPE


def build_letter_prompt(estate: EstateState, letter_type: str, recipient_name: str | None = None) -> str:
    selected_type = normalize_letter_type(letter_type)
    recipient = recipient_name or _default_recipient(selected_type)
    estate_json = json.dumps(estate.model_dump(mode="json"), indent=2, sort_keys=True)
    relevant_context = _relevant_context(estate, selected_type, recipient)
    statute_context = _statute_context(selected_type)

    return f"""Draft a sign-ready {LETTER_TYPE_LABELS[selected_type]} addressed specifically to: {recipient}

Estate facts:
- Deceased: {estate.deceasedName}, died {estate.dateOfDeath}
- Executor: {estate.executor.name}, email: {estate.executor.email}
- Letters testamentary issued: {estate.appointmentDate}
- Jurisdiction: California

Relevant details:
{relevant_context}

Statute or context:
{statute_context}

Drafting rules:
- Produce only the letter text. No preamble or commentary outside the letter.
- Output plain text only. No markdown, no **, no --, no #, no >, no tables, no backticks.
- Address the letter directly to "{recipient}" — use their name, never a placeholder like [CREDITOR NAME].
- Warm, direct, professional tone. The executor may be grieving.
- Do not give legal advice. Do not overclaim legal authority.
- Only use a [bracketed placeholder] if the fact is truly unknown and critical. Omit optional fields entirely.
- Format as a traditional business letter: sender block, date, recipient block, salutation, body paragraphs, closing, signature.
- End with a signature block for {estate.executor.name}, Executor of the Estate of {estate.deceasedName}.
- For creditor notices: cite California Probate Code §9051, state the specific amount owed to {recipient}, and ask them to file a claim.
"""


def build_letter_fallback(estate: EstateState, letter_type: str, recipient_name: str | None = None) -> str:
    selected_type = normalize_letter_type(letter_type)
    recipient = recipient_name or _default_recipient(selected_type)
    if selected_type == "creditor_notice":
        return _creditor_notice_fallback(estate, recipient)
    if selected_type == "bank_notification":
        return _bank_notification_fallback(estate, recipient)
    if selected_type == "irs_ein_request":
        return _irs_ein_request_fallback(estate, recipient)
    if selected_type == "beneficiary_update":
        return _beneficiary_update_fallback(estate, recipient)
    return _property_transfer_fallback(estate, recipient)


def _creditor_notice_fallback(estate: EstateState, recipient: str) -> str:
    debts = _format_debts(estate)
    return f"""{recipient}
[mailing address]

Re: Estate of {estate.deceasedName}
Date of Death: {estate.dateOfDeath}

Dear {recipient},

I am writing regarding the Estate of {estate.deceasedName}. I am {estate.executor.name}, the executor for the estate. Letters testamentary were issued on {estate.appointmentDate}.

This notice is provided for creditor notification purposes under California Probate Code §9051. Our records show the following possible debt or account information:

{debts}

Please send any claim information, account number, payoff amount, supporting statement, and preferred claim submission instructions to me at {estate.executor.email}. If you need a certified copy of the death certificate or letters testamentary, please tell me exactly what your office requires.

This letter is intended to help administer the estate and does not waive any rights, defenses, objections, or requirements under California probate procedure.

Sincerely,

{estate.executor.name}
Executor of the Estate of {estate.deceasedName}
{estate.executor.email}
"""


def _bank_notification_fallback(estate: EstateState, recipient: str) -> str:
    bank_assets = [asset.description for asset in estate.assets if asset.type == "bank_account"] or ["[account description]"]
    return f"""{recipient}
[bank mailing address]

Re: Estate of {estate.deceasedName}

Dear {recipient},

I am {estate.executor.name}, executor of the Estate of {estate.deceasedName}. {estate.deceasedName} passed away on {estate.dateOfDeath}, and letters testamentary were issued on {estate.appointmentDate}.

Please update your records for the following account or account group:

{_bullets(bank_assets)}

Please provide your estate account requirements, including any forms, account number confirmation, medallion or notarization requirements, and instructions for transferring or retitling funds to the estate.

Sincerely,

{estate.executor.name}
Executor of the Estate of {estate.deceasedName}
{estate.executor.email}
"""


def _irs_ein_request_fallback(estate: EstateState, recipient: str) -> str:
    return f"""{recipient}

Re: EIN preparation for the Estate of {estate.deceasedName}

To whom it may concern,

I am preparing to request an employer identification number for the Estate of {estate.deceasedName}. The decedent passed away on {estate.dateOfDeath}. {estate.executor.name} is the executor, with letters testamentary issued on {estate.appointmentDate}.

Known executor contact:
{estate.executor.name}
{estate.executor.email}

Please use this information to prepare the estate EIN request or identify any missing information, such as [executor mailing address], [responsible party SSN], or [estate mailing address].

Sincerely,

{estate.executor.name}
Executor of the Estate of {estate.deceasedName}
{estate.executor.email}
"""


def _beneficiary_update_fallback(estate: EstateState, recipient: str) -> str:
    return f"""{recipient}
[mailing address]

Re: Status update for the Estate of {estate.deceasedName}

Dear {recipient},

I am writing with a brief update on the Estate of {estate.deceasedName}. I am {estate.executor.name}, the executor. {estate.deceasedName} passed away on {estate.dateOfDeath}, and letters testamentary were issued on {estate.appointmentDate}.

Current administration focus:
- Notify known creditors.
- Prepare the inventory and appraisal packet.
- Gather missing documents and account details.

Beneficiary information currently recorded:
{_format_beneficiaries(estate)}

I will share additional operational updates as estate information is confirmed. Questions involving legal rights, objections, or strategy should go through estate counsel.

Sincerely,

{estate.executor.name}
Executor of the Estate of {estate.deceasedName}
{estate.executor.email}
"""


def _property_transfer_fallback(estate: EstateState, recipient: str) -> str:
    property_assets = [asset.description for asset in estate.assets if asset.type in {"real_estate", "vehicle"}] or ["[property address or asset description]"]
    return f"""{recipient}
[mailing address]

Re: Property transfer preparation for the Estate of {estate.deceasedName}

Dear {recipient},

I am {estate.executor.name}, executor of the Estate of {estate.deceasedName}. {estate.deceasedName} passed away on {estate.dateOfDeath}, and letters testamentary were issued on {estate.appointmentDate}.

Please provide the documents and instructions needed to prepare transfer or title updates for:

{_bullets(property_assets)}

If your office requires a certified death certificate, letters testamentary, parcel number, VIN, legal description, or specific transfer form, please send those requirements to {estate.executor.email}.

Sincerely,

{estate.executor.name}
Executor of the Estate of {estate.deceasedName}
{estate.executor.email}
"""


def _default_recipient(letter_type: str) -> str:
    return {
        "creditor_notice": "Known Creditor",
        "bank_notification": "Financial Institution",
        "irs_ein_request": "Tax Professional",
        "beneficiary_update": "Beneficiary",
        "property_transfer": "Records Office",
    }[letter_type]


def _statute_context(letter_type: str) -> str:
    if letter_type == "creditor_notice":
        return "California Probate Code §9051 requires notice to known or reasonably ascertainable creditors."
    if letter_type == "irs_ein_request":
        return "Estate EIN preparation is an IRS administrative step; do not provide tax advice."
    return "Operational estate administration letter; avoid giving legal advice or making legal conclusions."


def _relevant_context(estate: EstateState, letter_type: str, recipient: str | None = None) -> str:
    if letter_type == "creditor_notice":
        if recipient:
            match = next(
                (d for d in estate.debts if recipient.lower() in d.creditor.lower()),
                None,
            )
            if match:
                return f"Debt for this creditor: {match.creditor}, ${match.amount:,.2f} ({match.type})"
        return f"Known debts:\n{_format_debts(estate)}"
    if letter_type == "bank_notification":
        bank_assets = [asset.description for asset in estate.assets if asset.type == "bank_account"]
        return f"Bank assets:\n{_bullets(bank_assets or ['[account description]'])}"
    if letter_type == "beneficiary_update":
        return f"Beneficiaries:\n{_format_beneficiaries(estate)}"
    if letter_type == "property_transfer":
        assets = [asset.description for asset in estate.assets if asset.type in {"real_estate", "vehicle"}]
        return f"Transfer-related assets:\n{_bullets(assets or ['[property address or asset description]'])}"
    return "Executor and estate identity facts are the relevant context."


def _format_debts(estate: EstateState) -> str:
    if not estate.debts:
        return "- [creditor/account details]"
    return _bullets(f"{debt.creditor}: ${debt.amount:,.2f} ({debt.type}, notified={debt.notified})" for debt in estate.debts)


def _format_beneficiaries(estate: EstateState) -> str:
    if not estate.beneficiaries:
        return "- [beneficiary details]"
    return _bullets(
        f"{beneficiary.name}: {beneficiary.share or beneficiary.specificBequest or '[share/bequest]'}"
        for beneficiary in estate.beneficiaries
    )


def _bullets(items: Any) -> str:
    return "\n".join(f"- {item}" for item in items)
