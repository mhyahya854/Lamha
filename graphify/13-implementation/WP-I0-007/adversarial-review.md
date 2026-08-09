# WP-I0-007 adversarial review

- Review method: independent read-only adversarial review by Avicenna (`/root/wp_i0_005_review`) after each repaired candidate; the reviewer did not edit repository files.
- Final candidate: `run-20260809-019`.
- Final verdict: **PACKAGE REVIEW PASS**.

## Defects found and repaired

The review/repair loop rejected superseded runs until all actionable findings were resolved. Repairs covered:

- faithful discovery of all package and mise build/test surfaces, including prefixed tasks, Docker build-producing commands, and table-form task wrappers;
- full semantic tuple comparison across source path, source command, authorized command, working directory, kind, isolation proof, and blocker;
- faithful ML test coverage flags and working directory;
- strict JSON types, duplicate/malformed JSON handling, typed path errors, and raw negative fixtures;
- canonical Windows path components, reserved devices, alternate streams, namespaces, UNC aliases, lexical junction detection, and package/run root-template binding;
- exact slash-bounded repository allowlists and whole-repository preservation hashing;
- real junction and forbidden dependency-tree scanner fixtures;
- transactional output setup, injected mid-setup failure recovery, exact template-parent cleanup, and typed setup/execution/cleanup failures;
- candid rejection and cleanup evidence for every superseded authoring/run incident.

## Final independent verification

- Authorization/plan/oracle/attempt identities: 51/51 matched.
- Outcomes: 1 successful build attempt, 2 executed offline dependency failures, 48 typed pre-execution blockers.
- Codebase preservation: 3,697/3,697 paths and SHA-256 values matched; zero forbidden or reparse additions.
- Protected repository preservation: PASS.
- Real junction validator/scanner fixture: PASS.
- Injected mid-setup recovery: PASS and clean before the real run.
- Final cleanup: run root and both created template parents absent.
- Evidence consistency and all exit-gate clauses: PASS.

The reviewer noted one nonblocking wording concern: the exit-gate prose groups recovery/scanner checks with negative fixtures. The recorded fixture identities, results, and counts remain explicit and correct.
