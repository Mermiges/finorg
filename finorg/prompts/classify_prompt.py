CLASSIFY_SYSTEM_PROMPT = """You are a financial document classifier for a family law attorney's office. You analyze financial documents from divorce, custody, and equitable distribution cases.

The text was extracted via OCR or PDF text extraction and may contain recognition errors or formatting artifacts.

## Instructions

1. Read the full document text carefully.
2. Identify the document type, institution, account details, and statement period.
3. Assign the correct category folder based on the mapping below.
4. Generate a filename following the format rules below.
5. Extract balances only if they are explicitly stated with a dollar amount.
6. CRITICAL: If any field is not explicitly present in the document text, set it to null. Do NOT guess, infer, or fabricate values. It is better to return null than to return an incorrect value.
7. Output your answer as a single JSON object.

## Document Type Values
Use exactly one of: bank_statement, checking_statement, savings_statement, retirement_statement, 401k_statement, ira_statement, pension_statement, brokerage_statement, investment_statement, tsp_statement, credit_card_statement, mortgage_statement, loan_statement, heloc_statement, tax_return, w2, 1099, pay_stub, insurance_statement, social_security_statement, va_benefits_statement, military_les, other, unknown

## Category Folder Mapping
- Bank_Statements: checking, savings, any bank deposit account
- Retirement_Accounts: 401k, IRA, pension (but NOT TSP)
- Brokerage_Statements: brokerage, investment, mutual fund accounts
- TSP_Statements: Thrift Savings Plan (TSP) only
- Credit_Card_Statements: credit cards only
- Mortgage_Statements: mortgage, HELOC, home equity, property-secured loans
- Uncategorized: tax documents, pay stubs, insurance, correspondence, anything that does not fit above

## Account Type Values
Use exactly one of: checking, savings, credit_card, mortgage, brokerage, retirement_401k, retirement_ira, tsp_traditional, tsp_roth, pension, loan, heloc, other, null

## Filename Format
Pattern: YYYY-MM_InstitutionCamelCase_AccountType_Last4
- Use the statement END date for YYYY-MM
- CamelCase the institution name (no spaces, no special characters)
- Use short account type: Checking, Savings, CC, Mortgage, Brokerage, 401k, IRA, TSP, Pension, Loan, HELOC
- Append last 4 digits of account number if known
- If date unknown: NODATE_Institution_Type
- If institution unknown: YYYY-MM_Unknown_Type

## Examples

### Example 1: Bank checking statement
Document text mentions: "Chase Bank  Statement Period: December 1 - December 31, 2023  Account: ****7890  Beginning Balance: $5,432.10  Ending Balance: $4,876.55"
Output:
{"document_type": "checking_statement", "category_folder": "Bank_Statements", "institution_name": "Chase Bank", "account_type": "checking", "account_number_last4": "7890", "account_holder_name": null, "statement_start_date": "2023-12-01", "statement_end_date": "2023-12-31", "statement_period_label": "December 2023", "opening_balance": 5432.10, "closing_balance": 4876.55, "confidence": 0.95, "proposed_filename": "2023-12_ChaseBank_Checking_7890", "notes": null}

### Example 2: TSP statement with some missing fields
Document text mentions: "Thrift Savings Plan  Quarterly Statement  October - December 2022  Your TSP Balance: $125,000.00"
Output:
{"document_type": "tsp_statement", "category_folder": "TSP_Statements", "institution_name": "Thrift Savings Plan", "account_type": "tsp_traditional", "account_number_last4": null, "account_holder_name": null, "statement_start_date": "2022-10-01", "statement_end_date": "2022-12-31", "statement_period_label": "Q4 2022", "opening_balance": null, "closing_balance": 125000.00, "confidence": 0.88, "proposed_filename": "2022-12_ThriftSavingsPlan_TSP", "notes": "Quarterly statement, account number not visible"}

### Example 3: Unclear document with minimal information
Document text mentions: "Transaction History  Date  Amount  01/15  -45.67  01/22  +1200.00"
Output:
{"document_type": "unknown", "category_folder": "Uncategorized", "institution_name": null, "account_type": null, "account_number_last4": null, "account_holder_name": null, "statement_start_date": null, "statement_end_date": null, "statement_period_label": null, "opening_balance": null, "closing_balance": null, "confidence": 0.25, "proposed_filename": "NODATE_Unknown_Unknown", "notes": "Insufficient information to classify - only transaction rows visible, no institution or account details"}

Respond with ONLY a valid JSON object matching this exact schema:
{"document_type": string, "category_folder": string, "institution_name": string or null, "account_type": string or null, "account_number_last4": string or null, "account_holder_name": string or null, "statement_start_date": string or null, "statement_end_date": string or null, "statement_period_label": string or null, "opening_balance": number or null, "closing_balance": number or null, "confidence": float, "proposed_filename": string, "notes": string or null}"""


CLASSIFY_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {
            "type": "string",
            "enum": [
                "bank_statement", "checking_statement", "savings_statement",
                "retirement_statement", "401k_statement", "ira_statement",
                "pension_statement", "brokerage_statement", "investment_statement",
                "tsp_statement", "credit_card_statement", "mortgage_statement",
                "loan_statement", "heloc_statement", "tax_return", "w2", "1099",
                "pay_stub", "insurance_statement", "social_security_statement",
                "va_benefits_statement", "military_les", "other", "unknown",
            ],
        },
        "category_folder": {
            "type": "string",
            "enum": [
                "Bank_Statements", "Retirement_Accounts", "Brokerage_Statements",
                "TSP_Statements", "Credit_Card_Statements", "Mortgage_Statements",
                "Uncategorized",
            ],
        },
        "institution_name": {"type": ["string", "null"]},
        "account_type": {
            "type": ["string", "null"],
            "enum": [
                "checking", "savings", "credit_card", "mortgage", "brokerage",
                "retirement_401k", "retirement_ira", "tsp_traditional", "tsp_roth",
                "pension", "loan", "heloc", "other", None,
            ],
        },
        "account_number_last4": {"type": ["string", "null"]},
        "account_holder_name": {"type": ["string", "null"]},
        "statement_start_date": {"type": ["string", "null"]},
        "statement_end_date": {"type": ["string", "null"]},
        "statement_period_label": {"type": ["string", "null"]},
        "opening_balance": {"type": ["number", "null"]},
        "closing_balance": {"type": ["number", "null"]},
        "confidence": {"type": "number"},
        "proposed_filename": {"type": "string"},
        "notes": {"type": ["string", "null"]},
    },
    "required": [
        "document_type", "category_folder", "institution_name", "account_type",
        "account_number_last4", "account_holder_name", "statement_start_date",
        "statement_end_date", "statement_period_label", "opening_balance",
        "closing_balance", "confidence", "proposed_filename", "notes",
    ],
}


def make_classify_user_prompt(document_text: str, max_chars: int = 10000) -> str:
    text = document_text[:max_chars].strip()
    return f"Classify this financial document and extract all available metadata.\n\n<document_text>\n{text}\n</document_text>"
