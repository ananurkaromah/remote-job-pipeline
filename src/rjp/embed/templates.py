"""Structured embedding text template (ADR-013). Salary omitted when not disclosed."""
from __future__ import annotations

# Prefix used only for QUERY-side embeddings (retrieval instruction). Never
# prepend this to document-side text.
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


def build_embedding_text(job: dict) -> str:
    lines = [
        f"Title: {job.get('title', '')}",
        f"Company: {job.get('company', '')}",
        f"Remote Policy: {job.get('eligibility_status', 'unknown')}",
    ]
    tech_stack = job.get("tech_stack") or []
    if tech_stack:
        lines.append(f"Tech Stack: {', '.join(tech_stack)}")

    if job.get("salary_status") in ("disclosed", "partial"):
        min_s, max_s = job.get("min_salary_usd"), job.get("max_salary_usd")
        period = job.get("salary_period") or "yearly"
        if min_s and max_s:
            salary_display = f"${min_s:,.0f}-${max_s:,.0f} {period} USD"
        elif max_s:
            salary_display = f"up to ${max_s:,.0f} {period} USD"
        elif min_s:
            salary_display = f"from ${min_s:,.0f} {period} USD"
        else:
            salary_display = None
        if salary_display:
            lines.append(f"Salary: {salary_display}")

    description = job.get("description_clean") or ""
    lines.append(f"Description: {description}")
    return "\n".join(lines)


def build_query_text(query: str) -> str:
    return f"{QUERY_INSTRUCTION}{query}"
