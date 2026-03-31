from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable

from finorg.utils import sanitize_filename

TOP_LEVEL_FOLDERS = (
    "!lf",
    "01 - Pleadings",
    "02 - Discovery",
    "03 - Financial Accounts",
    "04 - Real Estate & Property",
    "05 - Income & Taxes",
    "06 - Affidavits",
    "07 - Communications",
    "08 - Medical",
    "09 - Children & Custody",
    "10 - Photos & Media",
    "11 - Trial Prep",
    "12 - Admin",
    "13 - Additional Categories",
    "_archive",
)

CASE_FOLDER_TEMPLATE = (
    "!lf/reports",
    "!lf/Discovery",
    "!lf/Summaries",
    "!lf/logs",
    "!lf/work",
    "!lf/duplicates",
    "01 - Pleadings/Complaint",
    "01 - Pleadings/Answer & Counterclaim",
    "01 - Pleadings/Motions",
    "01 - Pleadings/Orders",
    "02 - Discovery/Our ROGs",
    "02 - Discovery/Our RFPs",
    "02 - Discovery/Their ROGs",
    "02 - Discovery/Their RFPs",
    "02 - Discovery/Our Responses",
    "02 - Discovery/Their Responses",
    "03 - Financial Accounts/Payment Providers/Venmo",
    "03 - Financial Accounts/Payment Providers/PayPal",
    "03 - Financial Accounts/Crypto",
    "03 - Financial Accounts/TSP",
    "03 - Financial Accounts/Retirement - Military/LES (Leave & Earnings Statements)",
    "03 - Financial Accounts/Retirement - Military/Pension Estimates",
    "03 - Financial Accounts/Retirement - Military/DFAS Documents",
    "03 - Financial Accounts/VA Disability/Rating Decisions",
    "03 - Financial Accounts/VA Disability/Award Letters",
    "04 - Real Estate & Property/Marital Home/Closing Docs",
    "04 - Real Estate & Property/Marital Home/Property Taxes",
    "04 - Real Estate & Property/Marital Home/Valuations",
    "04 - Real Estate & Property/Vehicles",
    "04 - Real Estate & Property/Personal Property",
    "05 - Income & Taxes/Pay Stubs",
    "05 - Income & Taxes/Tax Returns",
    "05 - Income & Taxes/Financial Declaration",
    "05 - Income & Taxes/Credit Reports",
    "06 - Affidavits/Client",
    "06 - Affidavits/Witnesses",
    "06 - Affidavits/Templates",
    "07 - Communications/Text Messages",
    "07 - Communications/Email",
    "07 - Communications/Social Media/Facebook",
    "07 - Communications/Social Media/Instagram",
    "07 - Communications/Social Media/Snapchat",
    "07 - Communications/Phone Records",
    "07 - Communications/Other (Discord, etc.)",
    "08 - Medical/Client",
    "08 - Medical/Children",
    "09 - Children & Custody/Parenting Plans",
    "09 - Children & Custody/School Records",
    "09 - Children & Custody/Daycare",
    "09 - Children & Custody/Visitation Schedules",
    "10 - Photos & Media/Evidence Photos",
    "10 - Photos & Media/Family Photos",
    "11 - Trial Prep/Exhibit List",
    "11 - Trial Prep/Bates Stamped",
    "11 - Trial Prep/THP",
    "11 - Trial Prep/Notes",
    "12 - Admin/Intake",
    "12 - Admin/Retainer",
    "12 - Admin/Invoices",
    "12 - Admin/Correspondence",
    "12 - Admin/Call Notes",
    "13 - Additional Categories",
    "_archive",
)

FINANCIAL_DOCUMENT_TYPES = {
    "bank_statement",
    "checking_statement",
    "savings_statement",
    "retirement_statement",
    "401k_statement",
    "ira_statement",
    "pension_statement",
    "brokerage_statement",
    "investment_statement",
    "tsp_statement",
    "credit_card_statement",
    "mortgage_statement",
    "loan_statement",
    "heloc_statement",
    "payment_provider_statement",
    "crypto_statement",
    "military_les",
    "va_benefits_statement",
}

ACCOUNT_TYPE_LABELS = {
    "checking": "Checking",
    "savings": "Savings",
    "credit_card": "CreditCard",
    "mortgage": "Mortgage",
    "brokerage": "Brokerage",
    "retirement_401k": "401k",
    "retirement_ira": "IRA",
    "tsp_traditional": "TSP",
    "tsp_roth": "TSP",
    "pension": "Pension",
    "loan": "Loan",
    "heloc": "HELOC",
    "venmo": "Venmo",
    "paypal": "PayPal",
    "crypto": "Crypto",
    "other": "Document",
}

DOCUMENT_TITLE_FALLBACKS = {
    "bank_statement": "Bank Statement",
    "checking_statement": "Checking Statement",
    "savings_statement": "Savings Statement",
    "retirement_statement": "Retirement Statement",
    "401k_statement": "401k Statement",
    "ira_statement": "IRA Statement",
    "pension_statement": "Pension Statement",
    "brokerage_statement": "Brokerage Statement",
    "investment_statement": "Investment Statement",
    "tsp_statement": "TSP Statement",
    "credit_card_statement": "Credit Card Statement",
    "mortgage_statement": "Mortgage Statement",
    "loan_statement": "Loan Statement",
    "heloc_statement": "HELOC Statement",
    "payment_provider_statement": "Payment Provider Statement",
    "crypto_statement": "Crypto Statement",
    "tax_return": "Tax Return",
    "w2": "W-2",
    "1099": "1099",
    "pay_stub": "Pay Stub",
    "financial_declaration": "Financial Declaration",
    "credit_report": "Credit Report",
    "complaint": "Complaint",
    "answer_counterclaim": "Answer and Counterclaim",
    "motion": "Motion",
    "order": "Order",
    "discovery_request": "Discovery Request",
    "discovery_response": "Discovery Response",
    "affidavit": "Affidavit",
    "email": "Email",
    "text_message": "Text Messages",
    "social_media": "Social Media",
    "phone_record": "Phone Record",
    "medical_record": "Medical Record",
    "parenting_plan": "Parenting Plan",
    "school_record": "School Record",
    "daycare_record": "Daycare Record",
    "visitation_schedule": "Visitation Schedule",
    "evidence_photo": "Evidence Photo",
    "family_photo": "Family Photo",
    "trial_exhibit": "Exhibit",
    "bates_stamped": "Bates Stamped",
    "trial_hearing_plan": "Trial Hearing Plan",
    "invoice": "Invoice",
    "retainer": "Retainer",
    "intake_form": "Intake",
    "call_note": "Call Note",
    "correspondence": "Correspondence",
    "real_estate_record": "Real Estate Record",
    "vehicle_record": "Vehicle Record",
    "property_valuation": "Property Valuation",
    "other": "Document",
    "unknown": "Unknown Document",
}

FOLDER_HINT_FALLBACKS = {
    "tax_return": ["05 - Income & Taxes", "Tax Returns"],
    "w2": ["05 - Income & Taxes", "Tax Returns"],
    "1099": ["05 - Income & Taxes", "Tax Returns"],
    "pay_stub": ["05 - Income & Taxes", "Pay Stubs"],
    "financial_declaration": ["05 - Income & Taxes", "Financial Declaration"],
    "credit_report": ["05 - Income & Taxes", "Credit Reports"],
    "complaint": ["01 - Pleadings", "Complaint"],
    "answer_counterclaim": ["01 - Pleadings", "Answer & Counterclaim"],
    "motion": ["01 - Pleadings", "Motions"],
    "order": ["01 - Pleadings", "Orders"],
    "discovery_request": ["02 - Discovery", "Their RFPs"],
    "discovery_response": ["02 - Discovery", "Their Responses"],
    "affidavit": ["06 - Affidavits", "Witnesses"],
    "email": ["07 - Communications", "Email"],
    "text_message": ["07 - Communications", "Text Messages"],
    "social_media": ["07 - Communications", "Social Media"],
    "phone_record": ["07 - Communications", "Phone Records"],
    "medical_record": ["08 - Medical", "Client"],
    "parenting_plan": ["09 - Children & Custody", "Parenting Plans"],
    "school_record": ["09 - Children & Custody", "School Records"],
    "daycare_record": ["09 - Children & Custody", "Daycare"],
    "visitation_schedule": ["09 - Children & Custody", "Visitation Schedules"],
    "evidence_photo": ["10 - Photos & Media", "Evidence Photos"],
    "family_photo": ["10 - Photos & Media", "Family Photos"],
    "trial_exhibit": ["11 - Trial Prep", "Exhibit List"],
    "bates_stamped": ["11 - Trial Prep", "Bates Stamped"],
    "trial_hearing_plan": ["11 - Trial Prep", "THP"],
    "invoice": ["12 - Admin", "Invoices"],
    "retainer": ["12 - Admin", "Retainer"],
    "intake_form": ["12 - Admin", "Intake"],
    "call_note": ["12 - Admin", "Call Notes"],
    "correspondence": ["12 - Admin", "Correspondence"],
    "real_estate_record": ["04 - Real Estate & Property", "Marital Home"],
    "vehicle_record": ["04 - Real Estate & Property", "Vehicles"],
    "property_valuation": ["04 - Real Estate & Property", "Marital Home", "Valuations"],
}


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def best_document_date(entry: dict) -> date | None:
    for key in ("document_date", "statement_end_date", "statement_start_date"):
        parsed = parse_iso_date(entry.get(key))
        if parsed:
            return parsed
    return None


def best_document_year(entry: dict) -> str | None:
    dt = best_document_date(entry)
    return str(dt.year) if dt else None


def _compact_token(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = sanitize_filename(str(value), max_length=60).replace("_", "")
    return cleaned or None


def _human_token(value: str | None, fallback: str = "Unknown") -> str:
    if not value:
        return fallback
    cleaned = sanitize_filename(str(value), max_length=80).replace("_", " ").strip()
    return cleaned or fallback


def canonical_document_title(entry: dict) -> str:
    title = (entry.get("document_title") or "").strip()
    if title:
        return title
    doc_type = entry.get("document_type") or "unknown"
    return DOCUMENT_TITLE_FALLBACKS.get(doc_type, "Document")


def canonical_filename(entry: dict) -> str:
    dt = best_document_date(entry)
    prefix = dt.isoformat() if dt else "NODATE"

    pieces: list[str] = [prefix]
    inst = _compact_token(entry.get("institution_name"))
    title = _compact_token(canonical_document_title(entry))
    account_type = ACCOUNT_TYPE_LABELS.get(entry.get("account_type"), None)
    account_token = _compact_token(account_type)
    last4 = _compact_token(entry.get("account_number_last4") or entry.get("account_last4"))

    for piece in (inst, title, account_token, last4):
        if piece and piece not in pieces:
            pieces.append(piece)

    if len(pieces) == 1:
        pieces.append("Document")
    return sanitize_filename("_".join(pieces), max_length=160)


def normalize_folder_parts(parts: Iterable[str] | None) -> list[str]:
    if not parts:
        return []
    normalized: list[str] = []
    for part in parts:
        if part is None:
            continue
        text = str(part).replace("\\", "/").strip().strip("/")
        if not text:
            continue
        for token in text.split("/"):
            item = token.strip()
            if item:
                normalized.append(item)
    return normalized


def is_financial_statement(entry: dict) -> bool:
    if entry.get("is_financial_statement") is True:
        return True
    doc_type = entry.get("document_type") or ""
    account_type = entry.get("account_type") or ""
    return doc_type in FINANCIAL_DOCUMENT_TYPES or account_type in ACCOUNT_TYPE_LABELS


def financial_folder_parts(entry: dict) -> list[str]:
    institution = _human_token(entry.get("institution_name"))
    account_type = entry.get("account_type") or ""
    doc_type = entry.get("document_type") or ""
    year = best_document_year(entry)

    if doc_type == "military_les":
        return ["03 - Financial Accounts", "Retirement - Military", "LES (Leave & Earnings Statements)"]
    if doc_type == "va_benefits_statement":
        title = canonical_document_title(entry).lower()
        leaf = "Rating Decisions" if "rating" in title else "Award Letters"
        return ["03 - Financial Accounts", "VA Disability", leaf]
    if doc_type == "tsp_statement" or account_type.startswith("tsp_"):
        parts = ["03 - Financial Accounts", "TSP"]
        if year:
            parts.append(year)
        return parts
    if doc_type == "payment_provider_statement" or account_type in {"venmo", "paypal"}:
        provider = "Venmo" if "venmo" in institution.lower() or account_type == "venmo" else (
            "PayPal" if "paypal" in institution.lower() or account_type == "paypal" else institution
        )
        parts = ["03 - Financial Accounts", "Payment Providers", provider]
        if year:
            parts.append(year)
        return parts
    if doc_type == "crypto_statement" or account_type == "crypto":
        parts = ["03 - Financial Accounts", "Crypto"]
        if year:
            parts.append(year)
        return parts
    if doc_type in {"checking_statement", "savings_statement", "bank_statement"} or account_type in {"checking", "savings"}:
        leaf = "Checking" if account_type == "checking" or doc_type == "checking_statement" else "Savings"
        parts = ["03 - Financial Accounts", f"Bank - {institution}", leaf]
        if year:
            parts.append(year)
        return parts
    if doc_type == "credit_card_statement" or account_type == "credit_card":
        parts = ["03 - Financial Accounts", f"Credit Card - {institution}"]
        if year:
            parts.append(year)
        return parts
    if doc_type in {"brokerage_statement", "investment_statement"} or account_type == "brokerage":
        parts = ["03 - Financial Accounts", f"Brokerage - {institution}"]
        if year:
            parts.append(year)
        return parts
    if doc_type in {"retirement_statement", "401k_statement", "ira_statement", "pension_statement"} or account_type in {
        "retirement_401k",
        "retirement_ira",
        "pension",
    }:
        parts = ["03 - Financial Accounts", f"Retirement - {institution}"]
        if year:
            parts.append(year)
        return parts
    if doc_type == "mortgage_statement" or account_type == "mortgage":
        parts = ["03 - Financial Accounts", f"Mortgage - {institution}"]
        if year:
            parts.append(year)
        return parts
    if doc_type in {"loan_statement", "heloc_statement"} or account_type in {"loan", "heloc"}:
        descriptor = institution if institution != "Unknown" else _human_token(canonical_document_title(entry), "Loan")
        parts = ["03 - Financial Accounts", f"Loans - {descriptor}"]
        if year:
            parts.append(year)
        return parts
    parts = ["03 - Financial Accounts", f"Bank - {institution}"]
    if year:
        parts.append(year)
    return parts


def fallback_unknown_folder(entry: dict) -> list[str]:
    suggestion = (
        entry.get("suggested_new_category")
        or entry.get("document_title")
        or entry.get("document_type")
        or "Needs Review"
    )
    return ["13 - Additional Categories", _human_token(suggestion, "Needs Review")]


def build_folder_parts(entry: dict) -> list[str]:
    if is_financial_statement(entry):
        return financial_folder_parts(entry)

    hinted = normalize_folder_parts(entry.get("folder_hint_parts"))
    if hinted and hinted[0] in TOP_LEVEL_FOLDERS:
        return hinted

    doc_type = entry.get("document_type") or ""
    if doc_type in FOLDER_HINT_FALLBACKS:
        parts = list(FOLDER_HINT_FALLBACKS[doc_type])
        year = best_document_year(entry)
        if parts[:2] == ["05 - Income & Taxes", "Tax Returns"] and year:
            parts.append(year)
        return parts

    category = entry.get("category_folder")
    if category == "13 - Additional Categories":
        return fallback_unknown_folder(entry)
    if category in TOP_LEVEL_FOLDERS:
        return [category]

    return fallback_unknown_folder(entry)


def apply_routing(entry: dict) -> dict:
    routed = dict(entry)
    routed["document_title"] = canonical_document_title(routed)
    routed["proposed_filename"] = canonical_filename(routed)
    routed["folder_parts"] = build_folder_parts(routed)
    if routed["folder_parts"]:
        routed["category_folder"] = routed["folder_parts"][0]
    return routed


def timeline_group_key(entry: dict) -> str | None:
    if not is_financial_statement(entry):
        return None

    institution = _human_token(entry.get("institution_name"))
    last4 = _human_token(entry.get("account_number_last4") or entry.get("account_last4"), "NoLast4")
    account_type = ACCOUNT_TYPE_LABELS.get(entry.get("account_type"), canonical_document_title(entry))
    return f"{institution} | {account_type} | {last4}"
