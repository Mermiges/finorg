from __future__ import annotations

from datetime import date

from finorg.routing import parse_iso_date, timeline_group_key


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def iter_months(start: date, end: date) -> list[str]:
    current = _month_start(start)
    finish = _month_start(end)
    months: list[str] = []
    while current <= finish:
        months.append(current.strftime("%Y-%m"))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return months


def document_covered_months(entry: dict) -> list[str]:
    start = parse_iso_date(entry.get("statement_start_date"))
    end = parse_iso_date(entry.get("statement_end_date")) or parse_iso_date(entry.get("document_date"))
    if start and end:
        if end < start:
            start, end = end, start
        return iter_months(start, end)
    if end:
        return [end.strftime("%Y-%m")]
    if start:
        return [start.strftime("%Y-%m")]
    return []


def build_statement_timelines(entries: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for entry in entries:
        if entry.get("is_duplicate"):
            continue
        key = timeline_group_key(entry)
        if not key:
            continue
        months = document_covered_months(entry)
        if not months:
            continue
        timeline = grouped.setdefault(
            key,
            {
                "timeline_key": key,
                "institution_name": entry.get("institution_name"),
                "account_type": entry.get("account_type"),
                "account_number_last4": entry.get("account_number_last4") or entry.get("account_last4"),
                "document_ids": [],
                "covered_months": set(),
            },
        )
        timeline["document_ids"].append(entry["doc_id"])
        timeline["covered_months"].update(months)

    results: list[dict] = []
    for key, timeline in grouped.items():
        covered = sorted(timeline.pop("covered_months"))
        if not covered:
            continue

        first_month = parse_iso_date(f"{covered[0]}-01")
        last_month = parse_iso_date(f"{covered[-1]}-01")
        expected = iter_months(first_month, last_month) if first_month and last_month else covered
        missing = [month for month in expected if month not in covered]

        results.append(
            {
                **timeline,
                "timeline_key": key,
                "covered_months": covered,
                "missing_months": missing,
                "first_month": covered[0],
                "last_month": covered[-1],
                "document_count": len(timeline["document_ids"]),
            }
        )

    results.sort(key=lambda item: (item["institution_name"] or "", item["account_type"] or "", item["timeline_key"]))
    return results
