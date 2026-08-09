# WP-I0-006 adversarial review

- Reviewer: independent read-only subagent `/root/wp_i0_005_review`
- Instruction: attempt to disprove completion; do not assume PASS.
- Scope: raw packet and authority, the build-output isolation decision, collector, generated evidence, full untracked package scope, prerequisite evidence, and current filesystem state.
- Authoring boundary: the reviewer made no file changes.

## Prior failed invocation

The prior attempt created and deleted an external self-test stdout capture. It was explicitly marked failed, was never staged, committed, pushed, certified, or transitioned, and is preserved in `prior-failed-run-incident.md`. The new invocation streamed all validation output; the old path remained absent before and after review.

## Defects found and repaired before the fresh PASS

1. Enforced exact nested authorization/failure semantics and safe Windows output children.
2. Replaced asserted artifact counts with recursive Codebase, Graphify, package, and `.agents` inventories plus ignored/reparse/special-path checks.
3. Replaced cached preservation counts with two independent 3,697-file SHA-256 comparisons.
4. Enforced case-insensitive output-child uniqueness and exact approved command/source/list semantics.
5. Enforced conservative portable child grammar, rejecting overlong, surrogate, and bidi-spoofing components.
6. Added strict duplicate-key, malformed JSON, nonstandard constant, invalid UTF-8, size, depth, and numeric-limit handling with typed errors.

## Fresh-invocation independent verification

- All 31 structured/raw attacks returned their expected typed errors.
- All 3,697 Codebase files matched the WP-I0-001 path, size, and SHA-256 baseline.
- Fresh before/after fingerprints and recorded SHA-256 values reconciled exactly.
- Recursive inventories found no unexpected directories, ignored files, reparse points, special files, or forbidden output classes.
- AST/JSON and marker checks passed; membership, DAG, test, contract/schema/component ownership, and prerequisite evidence were consistent.
- No workspace, repository copy, build, product test, cache, generated-code, package-manager, temporary, or external scratch output was created during the fresh invocation.
- No actionable defect or nonblocking concern remained.

## Verdict

**PACKAGE REVIEW PASS**

Current package completion remains pending final certification, commit, push, and GitHub 1:1 verification.
