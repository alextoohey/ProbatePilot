# Example Documents

These files are upload fixtures for the onboarding and document workflow test plan in
`/docs/onboarding_document_workflow_test_plan.md`.

They are intentionally separate from app-owned document storage. Do not make the app save
uploaded files back into this folder.

## Why These Are PDFs

In a real estate administration workflow, these documents are almost never plain text
files. They are usually:

- Downloaded PDFs from banks, mortgage servicers, courts, or online accounts.
- Scanned PDFs made from paper court records, titles, receipts, or signed letters.
- JPG/PNG photos from a phone when an executor is moving quickly.

The fixture pack uses text-based PDFs because they are realistic enough for the product
flow while still letting the current backend extract text reliably. A later OCR/vision
test pass should add scanned image fixtures.

## Typical Contents

- Will: testator identity, executor nomination, beneficiaries, assets, bequests,
  residue clause, signatures, witnesses, and sometimes a self-proving affidavit.
- Letters testamentary: court, case number, appointed executor, authority granted, issue
  date, clerk signature, and seal.
- Death certificate: decedent identity, date/place of death, last residence, informant,
  registrar fields, and certification details.
- Bank statement: institution, account owner, account type, account number suffix,
  statement period, beginning/ending balances, and transactions.
- Tax return: taxpayer, tax year, filing status, recurring income sources, withholding,
  refund or balance due, and preparer/executor notes.
- Deed: county recorder information, APN, property address, grantor, grantee, legal
  description, recording date, and notarization.
- Vehicle title: owner, VIN, plate, vehicle description, lienholder, odometer, and title
  status.
- Mortgage statement: servicer, loan number, property, principal balance, payment due,
  escrow, and creditor address.
- Insurance policy: carrier, named insured, policy period, insured property, coverage
  limits, premium, mortgagee, and next payment due.
- DE-160 inventory: court case, executor, inventory rows, estimated values, appraised
  values, and probate referee details.
- Creditor notice: estate case, executor, creditor name/address, claim amount, mailing
  date, and certified mail tracking.
- Debt payment receipt: payee, claim amount, payment amount, payment date, method, and
  confirmation number.
- Distribution receipt: beneficiary, property/cash distributed, date, authority, and
  beneficiary acknowledgment signature.

Use the files in numeric order for the happy-path workflow:

1. `01_last_will_and_testament.pdf`
2. `02_letters_testamentary.pdf`
3. `03_death_certificate.pdf`
4. `04_bank_statement_wells_fargo.pdf`
5. `12_2025_form_1040_tax_return.pdf`
6. `05_grant_deed_berkeley_property.pdf`
7. `06_vehicle_title_honda_civic.pdf`
8. `07_mortgage_statement.pdf`
9. `13_homeowners_insurance_policy.pdf`
10. `08_de160_inventory_and_appraisal.pdf`
11. `09_creditor_notice_ucsf.pdf`
12. `10_debt_payment_receipt_chase_visa.pdf`
13. `11_distribution_receipt.pdf`

The current parser should recognize the will, bank statement, and deed. The remaining
fixtures are valid uploads for workflow testing and may be classified as `unknown` until
more document parsers are added.
