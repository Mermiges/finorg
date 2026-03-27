import csv
import logging
from datetime import datetime
from pathlib import Path

from finorg.config import PipelineConfig

logger = logging.getLogger("finorg")


def run_report(config: PipelineConfig, doc_groups: list[dict], log) -> Path:
    active = [g for g in doc_groups if not g.get("is_duplicate")]
    review = [g for g in active if g.get("needs_review")]
    dups = [g for g in doc_groups if g.get("is_duplicate")]

    # MASTER_INDEX.csv
    csv_path = config.output_dir / "MASTER_INDEX.csv"
    fieldnames = [
        "filename", "folder_path", "document_type", "institution", "account_type",
        "account_last4", "holder_name", "start_date", "end_date", "period_label",
        "opening_balance", "closing_balance", "page_count", "source_pdf", "confidence", "notes",
    ]

    def _row(g):
        organized = g.get("organized_path") or ""
        return {
            "filename": Path(organized).name if organized else g["doc_id"],
            "folder_path": str(Path(organized).parent) if organized else "",
            "document_type": g.get("document_type", ""),
            "institution": g.get("institution_name", ""),
            "account_type": g.get("account_type", ""),
            "account_last4": g.get("account_number_last4") or g.get("account_last4", ""),
            "holder_name": g.get("account_holder_name", ""),
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
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for g in active:
            w.writerow(_row(g))

    # REVIEW_NEEDED.csv
    review_path = config.output_dir / "REVIEW_NEEDED.csv"
    with open(review_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for g in review:
            w.writerow(_row(g))

    # PIPELINE_REPORT.md
    report_path = config.output_dir / "PIPELINE_REPORT.md"
    lines = []
    lines.append("# Financial Document Organization Report")
    lines.append(f"\nRun: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Source: `{config.source_dir}`")
    lines.append(f"Output: `{config.output_dir}`\n")

    source_pdfs = len(set(g["source_pdf"] for g in doc_groups))
    total_pages = sum(g.get("page_count", 0) for g in doc_groups)
    lines.append("## Summary\n")
    lines.append(f"- Source PDFs: {source_pdfs}")
    lines.append(f"- Total pages: {total_pages}")
    lines.append(f"- Documents extracted: {len(doc_groups)}")
    lines.append(f"- Duplicates removed: {len(dups)}")
    lines.append(f"- Unique documents organized: {len(active)}")
    lines.append(f"- Flagged for review: {len(review)}\n")

    lines.append("## By Category\n")
    lines.append("| Category | Count | Institutions |")
    lines.append("|----------|-------|--------------|")
    cat_data = {}
    for g in active:
        cat = g.get("category_folder", "Uncategorized")
        inst = g.get("institution_name") or "Unknown"
        cat_data.setdefault(cat, {"count": 0, "insts": set()})
        cat_data[cat]["count"] += 1
        cat_data[cat]["insts"].add(inst)
    for cat, d in sorted(cat_data.items()):
        lines.append(f"| {cat} | {d['count']} | {', '.join(sorted(d['insts']))} |")

    lines.append("\n## By Institution\n")
    lines.append("| Institution | Types | Count |")
    lines.append("|-------------|-------|-------|")
    inst_data = {}
    for g in active:
        inst = g.get("institution_name") or "Unknown"
        dt = g.get("document_type") or "unknown"
        inst_data.setdefault(inst, {"types": set(), "count": 0})
        inst_data[inst]["types"].add(dt)
        inst_data[inst]["count"] += 1
    for inst, d in sorted(inst_data.items(), key=lambda x: -x[1]["count"]):
        lines.append(f"| {inst} | {', '.join(sorted(d['types']))} | {d['count']} |")

    lines.append("\n## Monthly Coverage\n")
    lines.append("| Month | Count |")
    lines.append("|-------|-------|")
    month_counts = {}
    for g in active:
        ed = g.get("statement_end_date")
        if ed and len(str(ed)) >= 7:
            ym = str(ed)[:7]
            month_counts[ym] = month_counts.get(ym, 0) + 1
    for ym in sorted(month_counts.keys()):
        lines.append(f"| {ym} | {month_counts[ym]} |")

    if review:
        lines.append(f"\n## Review Needed ({len(review)} documents)\n")
        lines.append("| Document | Type | Confidence | Reason |")
        lines.append("|----------|------|------------|--------|")
        for g in review:
            fname = g.get("proposed_filename") or g["doc_id"]
            reason = []
            if (g.get("confidence") or 0) < config.confidence_threshold:
                reason.append("low confidence")
            if g.get("category_folder") == "Uncategorized":
                reason.append("uncategorized")
            if (g.get("proposed_filename") or "").startswith("NODATE"):
                reason.append("no date")
            if (g.get("proposed_filename") or "").startswith("Unknown"):
                reason.append("unknown institution")
            lines.append(f"| {fname} | {g.get('document_type', '')} | {g.get('confidence', 0):.2f} | {', '.join(reason)} |")

    lines.append(f"\n## Duplicates ({len(dups)} removed)\n")
    layer_counts = {1: 0, 2: 0, 3: 0}
    for g in dups:
        layer_counts[g.get("dedup_layer", 0)] = layer_counts.get(g.get("dedup_layer", 0), 0) + 1
    lines.append(f"- Layer 1 (exact file match): {layer_counts.get(1, 0)}")
    lines.append(f"- Layer 2 (text content match): {layer_counts.get(2, 0)}")
    lines.append(f"- Layer 3 (metadata match): {layer_counts.get(3, 0)}")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Report written to {report_path}")
    return report_path
