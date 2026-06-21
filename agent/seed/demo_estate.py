from __future__ import annotations

from copy import deepcopy

from schemas.estate import Asset, Beneficiary, Debt, EstateState, Executor, Task, UploadedDocument


DEMO_ESTATE = EstateState(
    id="demo-milligan",
    deceasedName="Robert A. Milligan",
    dateOfDeath="2026-06-03",
    appointmentDate="2026-06-10",
    executor=Executor(name="Dana Milligan", email="dana@demo.com"),
    assets=[
        Asset(
            id="asset-real-estate-berkeley",
            type="real_estate",
            description="1847 Marin Ave, Berkeley CA",
            estimatedValue=220000,
            appraised=False,
        ),
        Asset(
            id="asset-wells-fargo-4412",
            type="bank_account",
            description="Wells Fargo checking ...4412",
            estimatedValue=38240,
            appraised=True,
        ),
        Asset(
            id="asset-fidelity-7731",
            type="retirement",
            description="Fidelity IRA ...7731",
            estimatedValue=26500,
            appraised=True,
            beneficiaryNamed=True,
        ),
        Asset(
            id="asset-honda-civic",
            type="vehicle",
            description="2019 Honda Civic",
            estimatedValue=12000,
            appraised=False,
        ),
    ],
    debts=[
        Debt(id="debt-ucsf", creditor="UCSF Medical Center", amount=4200, type="unsecured"),
        Debt(id="debt-chase", creditor="Chase Visa", amount=3100, type="unsecured"),
        Debt(id="debt-mortgage", creditor="First Republic Mortgage", amount=141000, type="secured"),
    ],
    beneficiaries=[
        Beneficiary(id="beneficiary-dana", name="Dana Milligan", share="40%"),
        Beneficiary(id="beneficiary-sarah", name="Sarah Milligan", share="40%"),
        Beneficiary(id="beneficiary-marcus", name="Marcus Milligan", share="20%"),
    ],
    documents=[
        UploadedDocument(id="doc-seed-will", fileName="Last Will & Testament.pdf", documentType="will"),
        UploadedDocument(id="doc-seed-bank", fileName="Wells Fargo statement, May.pdf", documentType="bank_statement"),
        UploadedDocument(id="doc-seed-deed", fileName="Grant Deed, 1847 Marin Ave.pdf", documentType="deed"),
    ],
    tasks=[
        Task(id="task-order-death-certificates", title="Order 12 certified death certificates", phase=1),
        Task(id="task-notify-creditors", title="Notify all known creditors by certified mail", phase=2),
        Task(id="task-inventory-appraisal", title="Prepare DE-160 Inventory and Appraisal", phase=2),
    ],
    phase=2,
)


def build_demo_estate() -> EstateState:
    return deepcopy(DEMO_ESTATE)

