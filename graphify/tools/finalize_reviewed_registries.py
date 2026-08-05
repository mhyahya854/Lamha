"""Validate and apply explicit reviewed values without inventing review decisions."""

from __future__ import annotations

import csv

from apply_final_blocker_repairs import REVIEWS, apply_requirement_decisions


PERMITTED = {
    "REVIEWED_CONFIRMED",
    "REVIEWED_CORRECTED",
    "REVIEW_REQUIRED",
    "BLOCKED",
    "NOT_APPLICABLE",
}
REQUIRED_FIELDS = {
    "record_id",
    "candidate_value",
    "final_reviewed_value",
    "review_status",
    "review_rationale",
    "evidence",
    "reviewer_type",
    "review_revision",
    "correction_applied",
}


def main() -> None:
    path = REVIEWS / "reviewed-requirement-decisions.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not REQUIRED_FIELDS.issubset(reader.fieldnames or []):
            raise ValueError("explicit reviewed-decision registry is missing required fields")
        rows = list(reader)
    ids = [row["record_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate explicit reviewed decision")
    for row in rows:
        missing = [field for field in REQUIRED_FIELDS if not row.get(field)]
        if missing:
            raise ValueError(f"incomplete explicit reviewed decision {row['record_id']}: {missing}")
        if row["review_status"] not in PERMITTED:
            raise ValueError(f"invalid explicit status for {row['record_id']}")
    apply_requirement_decisions()


if __name__ == "__main__":
    main()
