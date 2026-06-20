TYPE_DETECTION_PROMPT = "Classify the estate document as will, bank_statement, deed, or unknown."

WILL_EXTRACTION_PROMPT = "Extract executor, beneficiaries, assets, clauses, and rawChunks from the will."

BANK_STATEMENT_EXTRACTION_PROMPT = (
    "Extract institution, account last four, balance, statement date, transactions, and rawChunks."
)

DEED_EXTRACTION_PROMPT = "Extract property address, APN, parties, recorded date, value, and rawChunks."

