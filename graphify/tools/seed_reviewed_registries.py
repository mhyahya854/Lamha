"""Reviewed decisions are authored, never seeded by a generator."""

raise SystemExit(
    "Automatic reviewed-registry seeding is disabled. Add candidate rows with "
    "REVIEW_REQUIRED, then author explicit decisions in semantic-plan-source/reviews."
)
