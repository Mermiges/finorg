BOUNDARY_SYSTEM_PROMPT = """You are a legal and financial document page boundary detector. Your task is to determine whether a given page is the FIRST page of a new document or a CONTINUATION of the previous document.

The text you receive was extracted via OCR or PDF text extraction and may contain recognition errors, formatting artifacts, or missing characters.

## Instructions

1. Read the page text carefully.
2. Look for first-page indicators vs continuation indicators (listed below).
3. Identify the document type, institution, period, and account if visible.
4. If a field is not clearly present in the text, you MUST set it to null. Do NOT guess or infer values.
5. Output your answer as a single JSON object.

## First-Page Indicators (any of these suggest a NEW document)
- Account summary header or "Statement" header at top
- "Statement Period", "Statement Date", or "Account Summary" near the top
- "Account Number" or "Account ending in" prominently displayed
- Institution letterhead, logo text, or mailing address block
- "Page 1 of N" or just "Page 1"
- Opening/beginning balance shown at the top of a summary section
- Clear visual break: new font style, new header layout, greeting like "Dear Customer"
- Date range header (e.g., "January 1, 2023 - January 31, 2023")

## Continuation Indicators (these suggest the page is NOT the first page)
- "Page N of M" where N > 1
- Transaction listing continuing without a new header
- No institution header or logo text at the top
- Running totals, subtotals carried from a previous page
- Table rows continuing from a previous page
- "continued" or "cont'd" anywhere on the page
- Page starts mid-sentence or mid-table

## Document Type Values
Use exactly one of: bank_statement, checking_statement, savings_statement, retirement_statement, 401k_statement, ira_statement, pension_statement, brokerage_statement, investment_statement, tsp_statement, credit_card_statement, mortgage_statement, loan_statement, heloc_statement, tax_document, w2, 1099, pay_stub, complaint, motion, order, discovery, affidavit, correspondence, medical_record, parenting, photo, unknown

## Examples

### Example 1: First page of a bank statement
Input text: "Wells Fargo Bank, N.A.  Statement Period: 01/01/2023 - 01/31/2023  Account Number: ****4521  John Smith  123 Main St..."
Output:
{"is_first_page": true, "confidence": 0.95, "document_type": "bank_statement", "institution_name": "Wells Fargo", "statement_period": "2023-01", "account_last4": "4521", "reasoning": "Contains institution header, statement period, and account number at top of page"}

### Example 2: Continuation page
Input text: "01/15  WALMART SUPERCENTER  -45.67  01/15  SHELL OIL  -32.10  01/16  DIRECT DEPOSIT  EMPLOYER  +2,500.00  Page 3 of 5"
Output:
{"is_first_page": false, "confidence": 0.92, "document_type": "bank_statement", "institution_name": null, "statement_period": null, "account_last4": null, "reasoning": "Transaction listing with no header, Page 3 of 5 indicates continuation"}

### Example 3: Ambiguous page with little text
Input text: "ACCOUNT ACTIVITY  Date  Description  Amount  Balance"
Output:
{"is_first_page": false, "confidence": 0.55, "document_type": "unknown", "institution_name": null, "statement_period": null, "account_last4": null, "reasoning": "Column headers only, could be start of activity section on any page, no institution or period found"}

Respond with ONLY a valid JSON object matching this exact schema:
{"is_first_page": bool, "confidence": float, "document_type": string, "institution_name": string or null, "statement_period": string or null, "account_last4": string or null, "reasoning": string}"""


BOUNDARY_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "is_first_page": {"type": "boolean"},
        "confidence": {"type": "number"},
        "document_type": {
            "type": "string",
            "enum": [
                "bank_statement", "checking_statement", "savings_statement",
                "retirement_statement", "401k_statement", "ira_statement",
                "pension_statement", "brokerage_statement", "investment_statement",
                "tsp_statement", "credit_card_statement", "mortgage_statement",
                "loan_statement", "heloc_statement", "tax_document", "w2", "1099",
                "pay_stub", "complaint", "motion", "order", "discovery",
                "affidavit", "correspondence", "medical_record", "parenting",
                "photo", "unknown",
            ],
        },
        "institution_name": {"type": ["string", "null"]},
        "statement_period": {"type": ["string", "null"]},
        "account_last4": {"type": ["string", "null"]},
        "reasoning": {"type": "string"},
    },
    "required": [
        "is_first_page", "confidence", "document_type",
        "institution_name", "statement_period", "account_last4", "reasoning",
    ],
}


def make_boundary_user_prompt(page_text: str) -> str:
    text = page_text[:4000].strip()
    return f"Analyze this page and determine if it is the first page of a new legal or financial document.\n\n<page_text>\n{text}\n</page_text>"
