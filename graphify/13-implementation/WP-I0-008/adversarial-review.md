# WP-I0-008 adversarial review

- Review method: independent read-only adversarial review by Avicenna (`/root/wp_i0_005_review`) after each repaired candidate; the reviewer did not author implementation files.
- Final verdict: **PACKAGE REVIEW PASS**.

## Defects found and repaired

Superseded candidates were rejected until the collector and evidence repaired:

- coherent upstream truncation/replacement and unexpected-field acceptance through raw and semantic SHA-256 binding, authoritative counts, exact schemas, and typed negative fixtures;
- CocoaPods `Pods/` outputs misclassified as dependencies instead of generated artifacts;
- lexical duplication of the Docker runtime instead of one canonical strongest-status record;
- missing host-tool consumer attribution for CMake, g++, and extism-js-pdk;
- pseudo-package attribution from target paths such as `${RENOVATE_REMOTE}` and `node_modules`;
- independently observed Compose env-file, credential, tracked `op://`, GitHub Actions secret/token, and deployment `get_env(...)` references.

## Final independent verification

- WP-I0-005 reconciliation: all 220 missing-observation rows evidenced; all 16 non-missing ambiguity/difference rows excluded.
- WP-I0-007 reconciliation: all 50 non-success attempts covered; the one success was not misclassified.
- Final classification: 187 records with category, source evidence, affected package context, blocking effect, `REVIEW_REQUIRED` or `BLOCKED` status, and `NOT_PERFORMED` supply action.
- Strict/failure suite: 31/31 PASS, including coherent replacement, unexpected fields, contradictory attempts, semantic deduplication, generated CocoaPods paths, consumer attribution, and pseudo-package rejection.
- Preservation: 3,697/3,697 Codebase paths and SHA-256 values matched WP-I0-001; no reparse point, cache, temporary artifact, or out-of-scope tracked change existed.

The reviewer retained one nonblocking observation: rust, bun, ninja, and yarn use repository-wide attribution because authoritative upstream evidence contains no concrete consumer declaration.
