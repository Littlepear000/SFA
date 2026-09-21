import json
from pathlib import Path
import pandas as pd


BASE_DIR = Path(r"C:\Users\xli7\OneDrive - International Monetary Fund (PRD)\Shelley_My Projects\SFA")
JSON_DIR = BASE_DIR / "output" / "json_dsa" / "2011-2015"
OUTPUT_FILE = BASE_DIR / "output" / "json_dsa" / "2011-2015"/ "compiled_csv" / "dsa_decomposition_sl_20260914.csv"


TOP_LEVEL_CATEGORIES = [
    "change_in_debt",
    "identified_flows",
    "primary_balance",
    "automatic_debt_dynamics",
    "other_identified_flows",
    "residual",
]


def clean_country_name(country):
    """
    Convert country names from all caps to a more readable format.

    Example:
    GREECE -> Greece
    UNITED STATES -> United States
    """

    if not country:
        return country

    return str(country).title()


def extract_year_token(value):
    """Extract a year or fiscal-year token for consistency checks."""
    import re

    text = str(value or "").strip()
    for pattern in (
        r"\b\d{4}/\d{2,4}\b",
        r"\b\d{4}-\d{2,4}\b",
        r"\b\d{4}\b",
    ):
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


def actual_year_fields(source):
    """Return actual-year, latest-observation, and audit-review fields."""
    last_actual_year = source.get("last_actual_year")
    actual_column_label = source.get("actual_column_label")
    audit = source.get("column_header_audit") or {}
    independent_audit = source.get("independent_column_header_audit") or {}
    validation = source.get("actual_column_validation") or {}

    last_token = extract_year_token(last_actual_year)
    label_token = extract_year_token(actual_column_label)
    if last_token and label_token:
        year_match = "Yes" if last_token == label_token else "No"
    else:
        year_match = "Unknown"

    return {
        "last_actual_year": last_actual_year,
        "actual_column_label": actual_column_label,
        "actual_column_status": source.get("actual_column_status"),
        "actual_column_header_verbatim": source.get("actual_column_header_verbatim"),
        "latest_observation_year": source.get("latest_observation_year"),
        "latest_observation_status": source.get("latest_observation_status"),
        "actual_year_label_match": year_match,
        "column_header_selected_year": audit.get("selected_year"),
        "column_header_selection_reason": audit.get("selection_reason"),
        "independent_audit_selected_year": independent_audit.get("selected_year"),
        "independent_audit_selection_reason": independent_audit.get("selection_reason"),
        "independent_latest_observation_year": source.get("independent_latest_observation_year"),
        "independent_latest_observation_status": source.get("independent_latest_observation_status"),
        "actual_column_validation_status": validation.get("status"),
        "actual_column_validation_issues": json.dumps(validation.get("issues") or [], ensure_ascii=False),
        "first_selected_year": validation.get("first_selected_year"),
        "audited_selected_year": validation.get("audited_selected_year"),
        "manual_review_required": "Yes" if validation.get("status") == "manual_review" else "No",
        "column_header_audit_json": json.dumps(audit, ensure_ascii=False) if audit else None,
        "independent_column_header_audit_json": json.dumps(independent_audit, ensure_ascii=False) if independent_audit else None,
    }


def flatten_node(
    node,
    rows,
    top_category,
    level,
    parent_label,
    file_info,
    hierarchy_id,
):
    """
    Recursively flatten one decomposition node and all its children.

    The hierarchy_id records where each row sits in the tree:
    1       top-level category
    1.1     first child of top-level category
    1.1.1   first child of that child
    """

    if not isinstance(node, dict):
        return

    label = node.get("label_verbatim")
    value = node.get("value")

    rows.append({
        **file_info,
        "top_category": top_category,
        "hierarchy_id": hierarchy_id,
        "level": level,
        "parent_label": parent_label,
        "label_verbatim": label,
        "value": value,
    })

    children = node.get("children", [])

    if isinstance(children, list):
        for child_number, child in enumerate(children, start=1):
            child_hierarchy_id = f"{hierarchy_id}.{child_number}"

            flatten_node(
                node=child,
                rows=rows,
                top_category=top_category,
                level=level + 1,
                parent_label=label,
                file_info=file_info,
                hierarchy_id=child_hierarchy_id,
            )


def main():
    rows = []

    # Only read DSA extraction files that end with _dsa.json.
    # This avoids accidentally processing summary files, error logs, or other JSON files.
    json_files = sorted(JSON_DIR.glob("*_dsa.json"))

    if not json_files:
        raise FileNotFoundError(f"No JSON files found in: {JSON_DIR}")

    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Skip files that do not have the expected DSA decomposition structure.
            if "decomposition" not in data:
                continue

            report_metadata = data.get("report_metadata") or {}
            source = data.get("source") or {}
            table_found = data.get("table_found")

            country = report_metadata.get("country") or source.get("country")
            country = clean_country_name(country)

            file_info = {
                "json_file": json_file.name,
                "pdf_file_name": data.get("pdf_file_name") or report_metadata.get("pdf_file_name"),
                "country": country,
                "publication_date": report_metadata.get("publication_date") or source.get("publication_date"),
                "consultation_type": report_metadata.get("consultation_type") or source.get("consultation_type"),
                "report_title": report_metadata.get("report_title"),
                "country_report_number": report_metadata.get("country_report_number"),
                "table_found": table_found,
                "framework": source.get("framework"),
                "table_number": source.get("table_number"),
                "table_title": source.get("table_title"),
                "page_pdf": source.get("page_pdf"),
                "page_printed": source.get("page_printed"),
                **actual_year_fields(source),
                "confidence": source.get("confidence"),
                "extraction_method": data.get("extraction_method"),
                "extraction_notes": (
                    data.get("extraction_notes")
                    if table_found is False
                    else None
                ),
            }

            # For failed extractions, keep one metadata row so the failure reason
            # and extraction notes are preserved in the output CSV.
            if table_found is False:
                rows.append({
                    **file_info,
                    "failure_reason": data.get("failure_reason"),
                    "top_category": None,
                    "hierarchy_id": None,
                    "level": None,
                    "parent_label": None,
                    "label_verbatim": None,
                    "value": None,
                })
                continue

            decomposition = data.get("decomposition") or {}

            for category_number, category in enumerate(TOP_LEVEL_CATEGORIES, start=1):
                node = decomposition.get(category)

                if node is not None:
                    flatten_node(
                        node=node,
                        rows=rows,
                        top_category=category,
                        level=0,
                        parent_label=None,
                        file_info=file_info,
                        hierarchy_id=str(category_number),
                    )

        except Exception as e:
            rows.append({
                "json_file": json_file.name,
                "error": str(e),
            })

    df = pd.DataFrame(rows)

    if "extraction_notes" in df.columns:
        cols = [c for c in df.columns if c != "extraction_notes"] + ["extraction_notes"]
        df = df[cols]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print("Done. CSV file saved to:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()
