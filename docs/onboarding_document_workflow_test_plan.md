# Onboarding And Document Workflow Test Plan

This workflow verifies the first major user journey: create a new California estate,
upload the documents an executor would reasonably have, confirm the app parses and
saves each upload, and walk the user through the six probate phases:

1. File petition
2. Appointment
3. Inventory
4. Notify creditors
5. Pay debts
6. Distribute

Use the files in `/example documents` as the upload fixtures. That folder is only test
input. It must stay separate from any app-owned document storage that gets added later.

The fixtures are PDFs because that is the most common real-world upload format for this
journey. Some originals would be downloaded PDFs, while others would be scanned paper
records or phone photos. This first fixture set uses text-based PDFs so the current
backend can extract the contents deterministically; add scanned image fixtures later for
OCR and Claude Vision testing.

## Test Goal

The setup flow is working when a new executor can:

- Create a new estate from the UI.
- See a new-estate onboarding state instead of the seeded demo dashboard.
- Upload estate documents.
- See every uploaded document appear in the Uploaded documents list with a parsed status.
- See parser-supported documents update the reconstructed estate graph.
- Edit extracted assets when the AI output needs human correction.
- Mark non-applicable document checklist items without losing context.
- Move through each probate phase's instructions and mark steps complete.
- Confirm backend estate state contains uploaded document records, extracted facts, and
  deadline-agent alerts.

## Current Parser Coverage

The backend currently has first-class parsers for:

- Will or testament documents
- Bank statements
- Deeds

The backend accepts but may classify these as `unknown` until additional parsers are
implemented:

- Letters testamentary
- Death certificate
- DE-160 inventory packet
- Creditor notice
- Mortgage statement
- Vehicle title
- Debt payment receipt
- Distribution receipt

That is still useful for this QA pass: unsupported documents should upload, save, show as
parsed, and avoid breaking the flow. Treat "unknown but saved" as pass for unsupported
document types unless the test case says otherwise.

## Preconditions

- Run the Python agent with environment variables configured for document parsing and
  embeddings when testing the full AI path.
- Run the Next.js web app with `AGENT_API_URL` pointing at the agent.
- Use a clean browser session, or clear local storage before the run.
- Do not use the seeded `demo-milligan` estate for this workflow except as a comparison.

Suggested local commands:

```bash
cd agent
uv run uvicorn main:app --reload --port 8000
```

```bash
cd web
npm run dev
```

## Test Estate Data

Create a new estate with this exact data:

- Deceased full name: Evelyn Hartwell
- Date of death: 2026-06-03
- Relationship: Child
- Role: Executor
- State: California
- County: Alameda

The sample documents are internally consistent with this estate. They include:

- Executor: Maya Hartwell
- Court case number: 26PR01842
- Appointment date: 2026-06-10
- Main real property: 1847 Marin Avenue, Berkeley, CA 94706
- Wells Fargo checking account ending 4412
- 2019 Honda Civic
- Known creditors: Golden Gate Mortgage Servicing, UCSF Medical Center, Chase Visa
- Beneficiaries: Maya Hartwell, Noah Hartwell, Lila Chen

## Upload Fixture Order

Upload these from `/example documents` in this order:

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

## Real-World File Types And Contents

These are the file types an executor would usually have:

- Will or trust: scanned PDF or phone image of the signed original. It contains the
  testator, executor nomination, beneficiaries, assets, bequests, residue clause,
  signatures, witnesses, and sometimes a self-proving affidavit.
- Letters testamentary: court-issued PDF or scanned certified copy. It contains court
  name, case number, appointed executor, powers granted, issue date, clerk signature, and
  seal.
- Death certificate: scanned certified copy, PDF, JPG, or PNG. It contains identity,
  death date/place, residence, informant, registrar, and certification fields.
- Bank and brokerage statements: downloaded PDFs. They contain institution, owner,
  account type, account suffix, statement period, balances, and transactions.
- Most recent tax return: preparer PDF or scanned copy. It contains filing status,
  recurring income sources, withholding, refund or balance due, and account clues for the
  final Form 1040.
- Deed: county recorder PDF or scanned copy. It contains APN, property address, legal
  description, grantor, grantee, recording date, and notarization.
- Vehicle title: scanned PDF/JPG/PNG. It contains owner, VIN, plate, vehicle description,
  lienholder, odometer, and title status.
- Mortgage or loan statements: downloaded PDFs. They contain servicer, loan number,
  property, balance, payment due, escrow, creditor address, and secured debt details.
- Insurance policies: declarations PDF or scanned policy page. It contains carrier,
  named insured, covered property, policy period, premium, coverage limits, and payee or
  mortgagee details.
- DE-160 inventory and appraisal: court-form PDF or scanned signed packet. It contains
  estate case data, inventory rows, values, and probate referee appraisal details.
- Creditor notices and certified-mail receipts: generated letter PDFs plus scanned postal
  receipts. They contain creditor name/address, claim amount, mailing date, and tracking.
- Debt receipts: confirmation PDFs, emails saved as PDFs, or scanned receipts. They
  contain payee, amount paid, date, payment method, and confirmation number.
- Distribution receipts: signed PDF or scan. They contain beneficiary, property/cash
  distributed, date, legal authority, and acknowledgment signature.

## End-To-End Manual Workflow

### 1. Create A New Estate

Steps:

1. Open the web app.
2. Click the estate switcher or add-estate control in the sidebar.
3. Choose to add a new estate.
4. Enter the Test Estate Data above.
5. Submit the form.

Expected result:

- The active estate changes to Evelyn Hartwell.
- The dashboard shows "New estate" setup content.
- The phase tracker starts at File petition.
- The call to action asks the user to add documents.
- No Robert A. Milligan seeded data appears in the new estate setup view.

Pass/fail notes:

- Pass if the new estate appears in the sidebar and can be selected again.
- Fail if the new estate immediately shows seeded assets, debts, or beneficiaries.
- Fail if required fields are not validated enough to prevent an empty deceased name.

### 2. Start Document Setup

Steps:

1. Click Add documents from the onboarding card.
2. Confirm the Documents page opens for Evelyn Hartwell.
3. Confirm Uploaded documents is empty.
4. Confirm Estate, reconstructed is empty.

Expected result:

- The upload drop zone is visible.
- The checklist shows required documents and optional documents.
- New-estate state does not pre-populate demo documents.

### 3. Upload The Will

Fixture:

- `/example documents/01_last_will_and_testament.pdf`

Steps:

1. Upload the will.
2. Wait for the upload state to finish.
3. Open the Uploaded documents list item.
4. Close the document preview.
5. Check the reconstructed estate panel.

Expected result:

- The document appears as parsed.
- The document type is Will.
- Beneficiaries and will assets are extracted into backend estate state.
- Any assets mentioned in the will are visible or reflected after refresh.
- The DeadlineAgent runs after upload and returns alerts without crashing.

Backend spot check:

```bash
curl http://localhost:8000/estate/<new-estate-id>
```

Expected backend state:

- `documents[]` contains the will file name.
- `beneficiaries[]` includes Maya Hartwell, Noah Hartwell, and Lila Chen.
- `assets[]` includes at least the Berkeley home, Wells Fargo checking, and Honda Civic
  if the Claude parser extracted them from the will.

### 4. Upload Appointment Documents

Fixtures:

- `/example documents/02_letters_testamentary.pdf`
- `/example documents/03_death_certificate.pdf`

Steps:

1. Upload letters testamentary.
2. Upload death certificate.
3. Confirm both are listed as parsed.
4. Return to the dashboard and confirm the user can still see setup progress.

Expected result:

- Both files save as uploaded documents.
- If classified as `unknown`, the UI still shows the type and keeps the flow intact.
- No upload error appears.
- The app does not overwrite the estate date of death with blank values.

### 5. Build Inventory From Assets

Fixtures:

- `/example documents/04_bank_statement_wells_fargo.pdf`
- `/example documents/12_2025_form_1040_tax_return.pdf`
- `/example documents/05_grant_deed_berkeley_property.pdf`
- `/example documents/06_vehicle_title_honda_civic.pdf`
- `/example documents/13_homeowners_insurance_policy.pdf`
- `/example documents/08_de160_inventory_and_appraisal.pdf`

Steps:

1. Upload the Wells Fargo statement.
2. Confirm a bank-account asset appears.
3. Upload the 2025 tax return.
4. Upload the grant deed.
5. Confirm a real-estate asset appears.
6. Upload the vehicle title.
7. If the vehicle title is classified as unknown, manually add the vehicle asset.
8. Upload the homeowners insurance policy.
9. Upload the DE-160 sample.
10. Edit any asset values to match the fixture values.
11. Mark appraised assets appropriately.

Expected result:

- Bank statement parses as Bank Statement and creates an account asset ending 4412.
- Grant deed parses as Deed and creates a real-estate asset for 1847 Marin Avenue.
- Unsupported inventory, tax, insurance, and vehicle documents still save without
  breaking the flow.
- Manual asset editing works for type, label, detail fields, value, and appraised status.
- Saved manual edits persist while staying on the Documents page.

Manual asset values to verify:

- Berkeley home: $220,000 estimated, $225,000 appraised
- Wells Fargo checking: $38,240.17
- Honda Civic: $12,000 estimated, $11,850 appraised

### 6. Notify Creditors

Fixture:

- `/example documents/09_creditor_notice_ucsf.pdf`

Steps:

1. Return to the dashboard.
2. Open the known-creditors alert or step card.
3. Read the What you'll need and How to do it sections.
4. Upload the creditor notice sample on the Documents page.
5. Return to the alert and mark the step complete.

Expected result:

- The step detail page is warm, direct, and non-legal-advice in tone.
- The creditor notice uploads and saves.
- The completed item appears under Completed on the dashboard.
- Completing this step does not delete the uploaded document.

### 7. Pay Debts

Fixtures:

- `/example documents/07_mortgage_statement.pdf`
- `/example documents/10_debt_payment_receipt_chase_visa.pdf`

Steps:

1. Upload the mortgage statement.
2. Upload the Chase Visa payment receipt.
3. Confirm both documents are saved.
4. Walk through the Pay debts phase instructions if visible.

Expected result:

- Documents save even if classified as unknown.
- The user can understand secured debt should be handled before unsecured debt.
- No UI copy suggests the app is giving legal advice.
- The app does not imply distributions are safe before creditor/debt steps are complete.

Risk check:

- If the app allows distribution steps before secured and unsecured debts are addressed,
  record this as a product gap for DeadlineAgent or phase gating.

### 8. Distribute

Fixture:

- `/example documents/11_distribution_receipt.pdf`

Steps:

1. Upload the distribution receipt.
2. Open or complete distribution-related steps if visible.
3. Confirm the final completed state is understandable.

Expected result:

- The document uploads and saves.
- The user can still inspect uploaded documents.
- The app does not drop or reset previous completed steps.
- The final dashboard state does not show contradictory urgent alerts for completed work.

## API-Level Regression Checks

Use these after the manual flow to confirm the backend contract is intact.

### Health

```bash
curl http://localhost:8000/health
```

Expected:

```json
{"status":"ok"}
```

### Parse A Supported Fixture

```bash
curl -X POST http://localhost:8000/parse-document \
  -F estateId=evelyn-hartwell-test \
  -F "file=@example documents/04_bank_statement_wells_fargo.pdf;type=application/pdf"
```

Expected:

- HTTP 200
- `extraction.documentType` is `bank_statement`
- `extraction.accountLast4` is `4412`
- `alerts` is an array

### Parse An Unsupported But Valid Fixture

```bash
curl -X POST http://localhost:8000/parse-document \
  -F estateId=evelyn-hartwell-test \
  -F "file=@example documents/09_creditor_notice_ucsf.pdf;type=application/pdf"
```

Expected:

- HTTP 200
- `extraction.documentType` may be `unknown`
- Document is added to `documents[]`
- No backend exception

### Reject An Empty File

Create an empty temp file outside `example documents` and upload it.

Expected:

- HTTP 400
- Error says the uploaded file is empty

### Reject Unsupported File Type

Upload a `.zip` file.

Expected:

- HTTP 415
- Error says unsupported file type

## Acceptance Checklist

Mark the workflow complete only when all of these are true:

- New estate creation works and does not leak seeded demo data.
- Documents page starts empty for the new estate.
- Supported parser fixtures extract expected structured facts.
- Unsupported fixtures still save cleanly and remain visible to the user.
- Uploaded documents are not stored in `/example documents`.
- Estate reconstruction can be corrected manually.
- Required and optional checklist controls work.
- Each phase can be opened and marked complete where the UI exposes it.
- The DeadlineAgent runs after uploads and does not block setup.
- Browser console has no user-facing errors during the flow.
- Backend logs show no unhandled exceptions.

## Known Product Gaps To Watch

These are not automatic failures for this setup-focused pass, but they should become
tracked issues if observed:

- New estates are currently UI-local until backend create-estate support is added.
- Parser support is limited to will, bank statement, and deed.
- Appointment date is not collected by the create-estate modal today.
- Phase progress is mostly driven by completed UI alert cards rather than persisted
  estate state.
- Uploaded original files are represented in state but not yet stored as downloadable
  originals by the backend.
- Debt and creditor documents do not yet merge structured debt facts into estate state.
