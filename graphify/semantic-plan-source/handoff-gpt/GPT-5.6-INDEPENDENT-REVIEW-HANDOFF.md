# GPT-5.6 Independent Review Handoff

## What Lamha is

Lamha is a local-first desktop application plan for managing a personal media
library: library and folder management, search (text, OCR, semantic, and
structured), review workflows, maps, editing, events, people and faces, tags,
albums, backup/trash/restore, and AI-assisted organisation. The implementation
target is a Tauri 2 desktop shell with a Rust core, a SvelteKit static
frontend, SQLite for rebuildable derived indexes, and local-only AI (OCR,
embeddings, face detection) executed through a Rust-native inference host.

This repository contains the *planning* only. The application source in
`Codebase/` is read-only during planning and review. Implementation work is
administered through work-package packets and must not start during this
review.

## What the plan promises

- 2,339 canonical requirement rows, of which 1,125 are active and 724 are
  actionable implementation records, each individually reviewed.
- 155 work packages, 724 reviewed requirement memberships, and a reviewed
  dependency DAG with exactly one root (`WP-I0-001`) and zero cycles.
- 17 component and licence decisions, all final, with version rules and
  redistribution status.
- 116 planned IPC commands, 30 schemas, and an executable SQLite DDL plan.
- The AI model override amendment `CAN-LAM-AI-090`: stronger compatible
  models remain manually selectable on weaker hardware; slow estimates alone
  never block; hard incompatibilities block with exact reasons; no silent
  model substitution; quantized variants are distinct; provenance persists.
- A three-layer deterministic proof (content manifest, certification report,
  release envelope) that runs twice with identical hashes.

## Authoritative versus generated files

`graphify/semantic-plan-source/` is authoritative. Every generated file in
`graphify/12-semantic-implementation-plan/` is rendered deterministically by
`graphify/build_semantic_plan.py` from those sources. Review reports never
override the records they validate. See `gpt-review-file-index.json` for the
full mapping and `gpt-review-counts.json` for the recomputed counts.

## How to rebuild the plan

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
Set-Location "C:\Users\mhyah\Downloads\Code\Lamha"
python graphify\build_semantic_plan.py
```

## How to run every validator

```powershell
python graphify\12-semantic-implementation-plan\12-validators\validate_plan.py --write-results
```

The validator covers 24 levels (L1-L21 with sub-levels) including requirement
semantics, mappings, packages, the technical DAG, components, IPC contracts,
schemas, SQLite, review provenance, Pass B architecture completeness, Pass C
component and licence completeness, the final 100% certification, and the
structural AI-override amendment check.

## How to run adversarial fixtures

```powershell
python graphify\12-semantic-implementation-plan\12-validators\adversarial_fixtures.py
```

Every fixture starts from a valid baseline, applies exactly one mutation, and
must fail for one intended reason. Shared multi-failure mutations are
prohibited and rejected.

## How to verify determinism

```powershell
python graphify\build_semantic_plan.py
python graphify\12-semantic-implementation-plan\12-validators\validate_plan.py --write-results --pre-certification
python graphify\12-semantic-implementation-plan\12-validators\adversarial_fixtures.py
python graphify\tools\generate_gpt_handoff.py
python graphify\tools\final_certification.py
```

The final certification is gated and uses a non-circular two-stage design:

1. **Pre-certification validation** runs first: the plan is rebuilt, all
   non-final-certification validator levels execute (`--pre-certification`),
   the adversarial suite runs, and then the full Graphify SHA manifest and
   handoff counts are regenerated over the current evidence.
2. **Final certification validation** runs after the certification artifacts
   exist: L20 independently re-verifies every required file, validator level,
   adversarial fixture, hash agreement, source/rendered pair, external
   integrity report, exclusion, and full-tree manifest recomputation.

The certification may write `status: PASS` only after every gate passes. On
any failure it writes `status: FAIL` with the exact blockers and exits
non-zero. Layer 1 (content manifest) and Layer 3 (release envelope) hashes are
computed twice and must match. The Layer 2 certification report is hashed by
Layer 3, and the Layer 1 manifest excludes itself plus explicitly documented
volatile timestamp files.

## How to verify external integrity

```powershell
python graphify\tools\pass3_external_integrity.py
```

First run creates the baseline; the second run compares every file outside
`graphify/` and must report added=0, removed=0, modified=0, renamed=0.

## How to inspect package consistency

For every package, compare `04-work-packages/packets/WP-*.md` against the
membership ledger (`04-work-packages/requirement-membership.csv`) and the
work-package registry (`04-work-packages/work-packages.json`). The packet
requirement count, objective, contracts, tests, and exit gate must agree with
the membership. L12 and L21 enforce this mechanically.

## How to detect false certifications

- Re-run the build, validator, adversarial suite, and determinism from the
  committed sources instead of trusting saved PASS text.
- Never accept a PASS certification that was written before its prerequisite
  gates completed. The certification must record every completed gate and the
  validator must independently re-verify each gate's evidence.
- Verify that the final certification requires and hashes every required file,
  fails on any missing Layer 3 member, records per-file hashes, and calculates
  `missingFiles`, `mismatchedFiles`, `unexpectedFiles`, and
  `unexplainedExclusions` from real results rather than hardcoding empty
  arrays.
- Verify that authoritative sources under `semantic-plan-source/` and the
  certification tools are covered by the full Graphify SHA manifest and that
  the saved manifest matches an independent recomputation.
- Confirm the certification report and handoff carry the exact declaration
  `FULL IMPLEMENTATION PLANNING 100% COMPLETE — WP-I0-001 MAY BEGIN` and that
  the old declaration `IMPLEMENTATION-READY PLANNING COMPLETE — I0 MAY BEGIN`
  appears nowhere active.
- Confirm every validator level that claims PASS actually re-executes the
  underlying checks (L13 meta-validation) and that the adversarial report
  lists an expected failure for each fixture.
- Confirm `gpt-review-sha-manifest.json` matches the committed tree.

## How to verify GitHub 1:1

```powershell
git rev-parse HEAD
git ls-remote origin refs/heads/main
git ls-tree -r HEAD graphify | Out-File local-tree.txt
git ls-tree -r origin/main graphify | Out-File remote-tree.txt
```

The two tree listings, every blob hash, and every final artifact
(canonical ledger, membership ledger, component ledger, validator output,
adversarial report, Layer 1 manifest, certification report, release envelope,
`START-HERE.md`) must match byte-for-byte.

## Areas that previously had defects

- AI amendment propagation: `WP-I10-003` previously described only two
  requirements while owning three; contracts, tests, and exit gate omitted
  `CAN-LAM-AI-090`. Corrected in the authoritative work-package registry.
- L21 previously searched whole JSON dumps for keywords. It now validates
  structured concepts, commands, behavioural rules, hard-block reasons,
  component rules, and the packet against its canonical membership.
- Adversarial fixtures previously reused one empty amendment artifact for many
  purposes. Each fixture now uses one controlled mutation.
- Component decision ownership: `Installer/signing tools` was owned by
  `WP-I15-005` while packaging (`WP-I15-001`) consumed it, contradicting the
  reviewed technical order (signing consumes packaging). Ownership moved to
  `WP-I15-001`; the unreviewed reverse edges were removed.
- Pass B review coverage: the AI-amendment membership `CAN-LAM-AI-090` and 20
  component-decision dependency edges lacked `REVIEWED_CONFIRMED` rows.
- Pass B independent evidence: contract/schema, test, and exit-gate rows
  lacked an `Item-specific rationale` column; 465 rows were enriched with
  per-package rationales.
- Persisted readiness: the Pass 3 certification pipeline still wrote the old
  declaration and hardcoded pre-amendment counts; both were corrected.
- Final certification false-pass path: the previous
  `tools/final_certification.py` wrote `status: PASS` unconditionally before
  any gate ran, silently skipped missing Layer 3 files (`if path.exists()`),
  hardcoded `missingFiles: []` / `mismatchedFiles: []` /
  `unexplainedExclusions: []`, did not bind authoritative
  `semantic-plan-source/` inputs to the proof, and L20 trusted the saved PASS
  text without independently checking any evidence. The certification is now
  gated, all required files are hashed, Layer 3 membership is verified
  file-by-file, authoritative sources are bound through the full Graphify
  manifest, and L20 independently re-verifies every artifact from raw
  evidence.

## Amendments added

- `CAN-LAM-AI-090` (AI model override): weaker hardware may select stronger
  compatible models; slow estimates never block; hard compatibility gates and
  exact block reasons; estimates, scheduling, selected-folder scope,
  pause/resume, no silent substitution, distinct quantized variants, and
  provenance are planned obligations.

## Claims intentionally deferred

- Exact AI checkpoint names are not selected at planning time; the plan pins
  model-card/checksum obligations and defers exact model selection to the
  model-registry work packages (`WP-I10-003`, `WP-I10-004`, `WP-I10-009`,
  `WP-I10-010`, `WP-I7-001`).
- Final serialized IPC field names for amendment concepts are planned as
  concepts; Phase 1 owns exact serialized naming.
- Exact third-party crate/version resolution is deferred to I0 repository
  inventory packages (`WP-I0-004`, `WP-I0-005`).

## Constraints for the reviewer

- `Codebase/` is strictly read-only during planning review.
- Only `graphify/` may change, and only planning evidence.
- No builds, installs, lockfile changes, backups, archives, Git rewrites, or
  force pushes.
- Implementation must not start. The administrative review status is
  `DEEPSEEK PRE-GPT PLANNING REVIEW COMPLETE — AWAITING GPT-5.6 INDEPENDENT REVIEW`,
  which blocks implementation pending this review.

## Instructions to the reviewer

Do not trust the DeepSeek PASS result. Attempt to disprove the certification:

1. Rebuild from committed sources and re-run every validator and fixture.
2. Try to find a requirement without a review, membership, test, or exit gate.
3. Try to find a package packet that disagrees with its membership.
4. Try to find a dependency without a Pass B review row.
5. Try to find a component whose consumers lack decision dependencies or whose
   decision package is its own consumer.
6. Try to break determinism by running the certification twice.
7. Try to find any active file still carrying the old readiness declaration.
8. Try to find a generated output that disagrees with its authoritative source.
9. Try to find any write, build, cache, or Git mutation outside `graphify/`.
10. Report every successful disproof as a genuine blocking defect.
11. Try to break the corrected certification again: remove a required Layer 3
    file, add a nonexistent Layer 3 entry, mutate a validator or adversarial
    report, change an authoritative source without rebuilding, force a
    non-zero external-integrity field, tamper with any recorded hash, delete
    or alter `gpt-review-sha-manifest.json`, add an unexplained exclusion, or
    hand-write a PASS certification with empty evidence arrays. Each attempt
    must fail the certification with a non-zero exit code.

The internal certification declaration is:

```text
FULL IMPLEMENTATION PLANNING 100% COMPLETE — WP-I0-001 MAY BEGIN
```

The administrative handoff declaration is:

```text
DEEPSEEK PRE-GPT PLANNING REVIEW COMPLETE — AWAITING GPT-5.6 INDEPENDENT REVIEW
```
