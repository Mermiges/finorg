from pathlib import Path

from finorg.config import PipelineConfig
from finorg.routing import apply_routing
from finorg.timelines import build_statement_timelines, document_covered_months


def test_config_creates_case_root_layout(tmp_path):
    config = PipelineConfig(source_dir=tmp_path / "src", output_dir=tmp_path / "case")
    config.ensure_dirs()

    assert (config.output_dir / "!lf" / "reports").exists()
    assert (config.output_dir / "03 - Financial Accounts").exists()
    assert (config.output_dir / "12 - Admin" / "Invoices").exists()


def test_bank_statement_routes_to_institution_year_folder():
    doc = apply_routing(
        {
            "doc_id": "DOC_0001",
            "document_type": "checking_statement",
            "document_title": "Checking Statement",
            "institution_name": "Wells Fargo",
            "account_type": "checking",
            "account_number_last4": "4521",
            "statement_end_date": "2024-01-31",
            "statement_start_date": "2024-01-01",
            "is_financial_statement": True,
        }
    )

    assert doc["folder_parts"] == [
        "03 - Financial Accounts",
        "Bank - Wells Fargo",
        "Checking",
        "2024",
    ]
    assert doc["proposed_filename"] == "2024-01-31_WellsFargo_CheckingStatement_Checking_4521"


def test_unknown_document_falls_back_to_additional_categories():
    doc = apply_routing(
        {
            "doc_id": "DOC_0002",
            "document_type": "other",
            "document_title": "Employment Benefits Packet",
            "category_folder": "13 - Additional Categories",
            "suggested_new_category": "Employment Benefits",
            "document_date": "2024-02-01",
        }
    )

    assert doc["folder_parts"] == ["13 - Additional Categories", "Employment Benefits"]
    assert doc["category_folder"] == "13 - Additional Categories"


def test_quarterly_statement_covers_each_month():
    months = document_covered_months(
        {
            "document_type": "tsp_statement",
            "statement_start_date": "2024-01-01",
            "statement_end_date": "2024-03-31",
            "is_financial_statement": True,
        }
    )

    assert months == ["2024-01", "2024-02", "2024-03"]


def test_statement_timelines_detect_missing_months():
    docs = [
        apply_routing(
            {
                "doc_id": "DOC_0001",
                "document_type": "checking_statement",
                "document_title": "Checking Statement",
                "institution_name": "Chase",
                "account_type": "checking",
                "account_number_last4": "7890",
                "statement_start_date": "2024-01-01",
                "statement_end_date": "2024-01-31",
                "is_financial_statement": True,
            }
        ),
        apply_routing(
            {
                "doc_id": "DOC_0002",
                "document_type": "checking_statement",
                "document_title": "Checking Statement",
                "institution_name": "Chase",
                "account_type": "checking",
                "account_number_last4": "7890",
                "statement_start_date": "2024-03-01",
                "statement_end_date": "2024-03-31",
                "is_financial_statement": True,
            }
        ),
    ]

    timelines = build_statement_timelines(docs)

    assert len(timelines) == 1
    assert timelines[0]["timeline_key"] == "Chase | Checking | 7890"
    assert timelines[0]["covered_months"] == ["2024-01", "2024-03"]
    assert timelines[0]["missing_months"] == ["2024-02"]
