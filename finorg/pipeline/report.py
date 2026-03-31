import csv
import logging
from datetime import datetime
from pathlib import Path

from finorg.config import PipelineConfig
from finorg.timelines import build_statement_timelines

logger = logging.getLogger("finorg")


def run_report(config: PipelineConfig, doc_groups: list[dict], log) -> Path:
    active = [g for g in doc_groups if not g.get("is_duplicate")]
    review = [g for g in active if g.get("needs_review")]
    dups = [g for g in doc_groups if g.get("is_duplicate")]
    timelines = build_statement_timelines(active)

    config.reports_dir.mkdir(parents=True, exist_ok=True)

    csv_path = config.reports_dir / "MASTER_INDEX.csv"
    fieldnames = [
        "filename",
        "root_copy_path",
        "organized_path",
        "relative_folder",
        "document_type",
        "document_title",
        "institution",
        "account_type",
        "account_last4",
        "holder_name",
        "document_date",
        "start_date",
        "end_date",
        "period_label",
        "opening_balance",
        "closing_balance",
        "page_count",
        "source_pdf",
        "confidence",
        "notes",
    ]

    def _row(g):
        organized = g.get("organized_path") or ""
        root_copy = g.get("root_copy_path") or ""
        return {
            "filename": Path(root_copy).name if root_copy else (g.get("proposed_filename") or g["doc_id"]),
            "root_copy_path": root_copy,
            "organized_path": organized,
            "relative_folder": g.get("relative_folder", ""),
            "document_type": g.get("document_type", ""),
            "document_title": g.get("document_title", ""),
            "institution": g.get("institution_name", ""),
            "account_type": g.get("account_type", ""),
            "account_last4": g.get("account_number_last4") or g.get("account_last4", ""),
            "holder_name": g.get("account_holder_name", ""),
            "document_date": g.get("document_date", ""),
            "start_date": g.get("statement_start_date", ""),
            "end_date": g.get("statement_end_date", ""),
            "period_label": g.get("statement_period_label", ""),
            "opening_balance": g.get("opening_balance", ""),
            "closing_balance": g.get("closing_balance", ""),
            "page_count": g.get("page_count", ""),
            "source_pdf": g.get("source_pdf", ""),
            "confidence": g.get("confidence", ""),
            "notes": g.get("notes", ""),
        }

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for g in active:
            writer.writerow(_row(g))

    review_path = config.reports_dir / "REVIEW_NEEDED.csv"
    with open(review_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for g in review:
            writer.writerow(_row(g))

    timelines_path = config.reports_dir / "STATEMENT_TIMELINES.csv"
    with open(timelines_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timeline_key",
                "institution_name",
                "account_type",
                "account_number_last4",
                "first_month",
                "last_month",
                "document_count",
                "covered_months",
                "missing_months",
            ],
        )
        writer.writeheader()
        for timeline in timelines:
            writer.writerow(
                {
                    **timeline,
                    "covered_months": ", ".join(timeline["covered_months"]),
                    "missing_months": ", ".join(timeline["missing_months"]),
                }
            )

    missing_path = config.reports_dir / "MISSING_STATEMENT_MONTHS.csv"
    with open(missing_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timeline_key", "missing_month"])
        writer.writeheader()
        for timeline in timelines:
            for month in timeline["missing_months"]:
                writer.writerow({"timeline_key": timeline["timeline_key"], "missing_month": month})

    report_path = config.reports_dir / "PIPELINE_REPORT.md"
    lines = []
    lines.append("# Financial Document Organization Report")
    lines.append(f"\nRun: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Source: `{config.source_dir}`")
    lines.append(f"Case Root: `{config.output_dir}`")
    lines.append(f"Reports: `{config.reports_dir}`\n")

    source_pdfs = len(set(g["source_pdf"] for g in doc_groups))
    total_pages = sum(g.get("page_count", 0) for g in doc_groups)
    lines.append("## Summary\n")
    lines.append(f"- Source PDFs scanned: {source_pdfs}")
    lines.append(f"- Total pages: {total_pages}")
    lines.append(f"- Documents extracted: {len(doc_groups)}")
    lines.append(f"- Duplicates removed: {len(dups)}")
    lines.append(f"- Unique documents organized: {len(active)}")
    lines.append(f"- Flagged for review: {len(review)}")
    lines.append(f"- Statement timelines tracked: {len(timelines)}\n")

    lines.append("## Folder Distribution\n")
    lines.append("| Top-Level Folder | Count |")
    lines.append("|------------------|-------|")
    by_folder = {}
    for g in active:
        folder = (g.get("folder_parts") or [g.get("category_folder") or "13 - Additional Categories"])[0]
        by_folder[folder] = by_folder.get(folder, 0) + 1
    for folder, count in sorted(by_folder.items()):
        lines.append(f"| {folder} | {count} |")

    lines.append("\n## Statement Timelines\n")
    lines.append("| Account Timeline | Covered Range | Missing Months |")
    lines.append("|------------------|---------------|----------------|")
    if timelines:
        for timeline in timelines:
            covered = f"{timeline['first_month']} -> {timeline['last_month']}"
            missing = ", ".join(timeline["missing_months"]) if timeline["missing_months"] else "None"
            lines.append(f"| {timeline['timeline_key']} | {covered} | {missing} |")
    else:
        lines.append("| None | N/A | N/A |")

    if review:
        lines.append(f"\n## Review Needed ({len(review)} documents)\n")
        lines.append("| Document | Folder | Confidence | Reason |")
        lines.append("|----------|--------|------------|--------|")
        for g in review:
            reasons = []
            if (g.get("confidence") or 0) < config.confidence_threshold:
                reasons.append("low confidence")
            if (g.get("folder_parts") or [""])[0] == "13 - Additional Categories":
                reasons.append("new or unknown category")
            if (g.get("proposed_filename") or "").startswith("NODATE"):
                reasons.append("no explicit date")
            if "Unknown" in (g.get("proposed_filename") or ""):
                reasons.append("unknown entity")
            lines.append(
                f"| {g.get('proposed_filename') or g['doc_id']} | "
                f"{g.get('relative_folder', '')} | "
                f"{g.get('confidence', 0):.2f} | "
                f"{', '.join(reasons) or 'manual check'} |"
            )

    lines.append(f"\n## Duplicates ({len(dups)} removed)\n")
    layer_counts = {1: 0, 2: 0, 3: 0}
    for g in dups:
        layer_counts[g.get("dedup_layer", 0)] = layer_counts.get(g.get("dedup_layer", 0), 0) + 1
    lines.append(f"- Layer 1 (exact file match): {layer_counts.get(1, 0)}")
    lines.append(f"- Layer 2 (text content match): {layer_counts.get(2, 0)}")
    lines.append(f"- Layer 3 (metadata match): {layer_counts.get(3, 0)}")

    lines.append("\n## Output Layout\n")
    lines.append("- Root-level PDFs are chronological renamed copies.")
    lines.append("- Foldered PDFs are copies placed under the case structure.")
    lines.append("- Generated artifacts live under `!lf/reports`, `!lf/logs`, and `!lf/work`.")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Report written to {report_path}")
    return report_path
