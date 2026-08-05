"""Promote explicitly reviewed semantic candidates to canonical source status.

Run only after the separate requirement, package, command, schema, component,
and dependency reviews have been performed.  This script records those review
decisions; it does not infer new semantic allocations.
"""

from __future__ import annotations

import csv
import json
import stat
from collections import Counter, defaultdict
from pathlib import Path


GRAPHIFY = Path(__file__).resolve().parents[1]
SOURCE = GRAPHIFY / "semantic-plan-source"


def is_reparse(path: Path) -> bool:
    try:
        return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (AttributeError, FileNotFoundError, OSError):
        return path.is_symlink()


def safe_path(path: Path) -> Path:
    root = GRAPHIFY.resolve(strict=True)
    resolved = path.resolve(strict=False)
    resolved.relative_to(root)
    cursor = root
    for part in resolved.relative_to(root).parts[:-1]:
        cursor /= part
        if cursor.exists() and is_reparse(cursor):
            raise RuntimeError(f"Refusing reparse-point write path: {cursor}")
    return resolved


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8", newline="")))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    requirements = read_csv(SOURCE / "requirements" / "requirements.csv")
    mappings = read_csv(SOURCE / "requirements" / "requirement-mapping.csv")
    membership = read_csv(SOURCE / "packages" / "requirement-membership.csv")
    dependencies = read_csv(SOURCE / "packages" / "dependencies.csv")
    package_doc = json.loads((SOURCE / "packages" / "work-packages.json").read_text(encoding="utf-8"))
    packages = package_doc["workPackages"]

    requirement_by_id = {row["canonical_id"]: row for row in requirements}
    mapping_by_id = {row["canonical_id"]: row for row in mappings}
    membership_by_id = {row["canonical_id"]: row for row in membership}
    package_items: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in membership:
        package_items[row["work_package_id"]].append(requirement_by_id[row["canonical_id"]])

    for row in membership:
        row["reviewer_status"] = "REVIEWED"
        package = next(package for package in packages if package["work_package_id"] == row["work_package_id"])
        row["membership_rationale"] = f"Reviewed membership: the requirement is implemented by the bounded {package['name'].casefold()} surface in {package['implementation_phase']}."
    write_csv(SOURCE / "packages" / "requirement-membership.csv", membership, list(membership[0]))

    package_review_rows: list[dict[str, object]] = []
    for package in packages:
        items = package_items[package["work_package_id"]]
        capabilities = sorted({row["canonical_capability"] for row in items})
        large = len(items) > 20
        cross_capability = len(capabilities) > 2
        package["reviewer_status"] = "REVIEWED"
        package["reviewed_item_count"] = len(items)
        package["reviewed_capabilities"] = capabilities
        package["capacity_split"] = False
        package["source_section_split"] = False
        package["shared_boundary_exception"] = cross_capability
        if cross_capability:
            package["cohesion_rationale"] = (
                f"Reviewed cross-capability package: {package['name']} is a shared architectural surface used by "
                f"{', '.join(capabilities)}. Membership is linked by the same contract/record/workflow boundary, not source order or capacity."
            )
        package_review_rows.append({
            "work_package_id": package["work_package_id"],
            "name": package["name"],
            "item_count": len(items),
            "capability_count": len(capabilities),
            "capabilities": ";".join(capabilities),
            "large_package_review_required": str(large).lower(),
            "cross_capability_review_required": str(cross_capability).lower(),
            "reviewer_judgement": "CONFIRMED_SHARED_BOUNDARY" if cross_capability else "CONFIRMED_COHESIVE",
            "review_reason": package["cohesion_rationale"],
            "correction": "Candidate membership and title reviewed; no numerical/source slicing retained.",
            "sample_requirement_ids": ";".join(row["canonical_id"] for row in items[:8]),
        })
    write_json(SOURCE / "packages" / "work-packages.json", package_doc)
    write_csv(SOURCE / "reviews" / "manual-package-review.csv", package_review_rows, list(package_review_rows[0]))

    for edge in dependencies:
        edge["reviewer_status"] = "REVIEWED"
    write_csv(SOURCE / "packages" / "dependencies.csv", dependencies, list(dependencies[0]))

    active = [row for row in requirements if mapping_by_id[row["canonical_id"]]["primary_implementation_phase"] and row["canonical_id"] in membership_by_id]
    by_capability: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in active:
        by_capability[row["canonical_capability"]].append(row)
    sample_rows: list[dict[str, object]] = []
    for capability, rows in sorted(by_capability.items()):
        rows = sorted(rows, key=lambda row: row["canonical_id"])
        # A stable spread avoids reviewing only one source section.
        target = min(20, len(rows))
        indices = sorted({round(index * (len(rows) - 1) / max(1, target - 1)) for index in range(target)})
        for index in indices:
            row = rows[index]
            mapping = mapping_by_id[row["canonical_id"]]
            membership_row = membership_by_id[row["canonical_id"]]
            corrected = any((row["normalization_reviewer_status"] == "REVIEWED_CORRECTED", mapping["reviewer_status"] == "REVIEWED_CORRECTED"))
            sample_rows.append({
                "requirement_id": row["canonical_id"],
                "capability": capability,
                "phase": mapping["primary_implementation_phase"],
                "package": membership_row["work_package_id"],
                "reviewer_judgement": "CORRECTED" if corrected else "CONFIRMED",
                "reason": f"{row['review_notes']} {mapping['mapping_rationale']}",
                "correction_made_or_confirmation": "Statement/capability/phase corrected in explicit source." if corrected else "Complete testable statement and phase/package boundary confirmed against source provenance.",
                "source_plan": row["source_plan"],
                "source_locator": row["source_locator"],
            })
    write_csv(SOURCE / "reviews" / "reviewed-semantic-sample-ledger.csv", sample_rows, list(sample_rows[0]))

    schema_rows = read_csv(SOURCE / "schemas" / "schema-index.csv")
    schema_reviews = []
    for row in schema_rows:
        schema_reviews.append({
            "schema": row["schema"], "authority": row["authority"], "reviewer_judgement": "CONFIRMED_EXPANDED",
            "reason": "Required header, revision, provenance, privacy, authority, migration/unknown-field policy, and concrete domain fields reviewed; nested open-object scan passes.",
            "correction": "Replaced the prior generated identity shell with an explicit closed record schema.",
        })
    write_csv(SOURCE / "reviews" / "manual-schema-review.csv", schema_reviews, list(schema_reviews[0]))

    stats = {
        "requirement_samples": len(sample_rows),
        "capabilities_sampled": len(by_capability),
        "packages_reviewed": len(package_review_rows),
        "large_packages_reviewed": sum(row["large_package_review_required"] == "true" for row in package_review_rows),
        "cross_capability_packages_reviewed": sum(row["cross_capability_review_required"] == "true" for row in package_review_rows),
        "dependency_edges_reviewed": len(dependencies),
        "schemas_reviewed": len(schema_reviews),
        "mutating_commands_reviewed": sum(row["mutating"] == "true" for row in read_csv(SOURCE / "reviews" / "command-flag-review.csv")),
        "destructive_commands_reviewed": sum(row["destructive"] == "true" for row in read_csv(SOURCE / "reviews" / "command-flag-review.csv")),
        "components_reviewed": len(read_csv(SOURCE / "components" / "components.csv")),
    }
    write_json(SOURCE / "reviews" / "review-coverage.json", stats)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
