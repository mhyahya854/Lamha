# WP-I0-009 adversarial review

- Review method: independent read-only adversarial review by `/root/wp_i0_009_review`; the reviewer did not author or modify package files.
- Stable evidence generation: `11fa8e5669c06aac1685a4a4205953660f4062f4796ba445a20a9eac4943e06f`.
- Final verdict: **PACKAGE REVIEW PASS**.

## Defects found and repaired

Superseded candidates were rejected until the collector, verifier, and evidence repaired:

- database-backup and generic URL-property couplings linked to unrelated Map/Search decisions by broad keyword matching;
- missing Socket.IO and component-emitter imports and package declarations that carry server event state;
- missing `document.cookie` and `immich_is_authenticated` authentication-state couplings;
- truncation of `docs.${info.version}.archive.immich.app` to the nonexistent host `docs`;
- speculative Desktop-shell ownership for the dynamic external host instead of `REVIEW_REQUIRED`;
- verification that checked owner existence without independently checking semantic support;
- a pre-validation-only recovery fixture that did not exercise mid-publication failure;
- completion evidence without the exact changed-file and validation-command record.

## Final independent verification

- Collector: `python graphify\13-implementation\WP-I0-009\collect_evidence.py` — exit 0.
- Independent verifier: `python graphify\13-implementation\WP-I0-009\verify_evidence.py` — exit 0.
- Corpus: 736 frontend files, including 711 text-scanned files and tests/mocks.
- Inventory: 1,976 couplings; 1,560 linked to one reviewed decision; 416 explicitly `REVIEW_REQUIRED`.
- Categories: 305 authentication, 810 generated-client, 101 runtime-host, 559 server-owned-state, and 201 server-route records.
- Negative/recovery suite: 26/26 PASS, including semantic-owner regressions, Socket.IO, authentication cookie, complete dynamic template host, pre-validation preservation, and byte-for-byte rollback after an injected mid-publication failure.
- Regression: 3,697/3,697 Codebase paths and SHA-256 values match the WP-I0-001 baseline.
- Evidence consistency: all artifact generation IDs and semantic hashes reconcile to `11fa8e5669c06aac1685a4a4205953660f4062f4796ba445a20a9eac4943e06f`.
- Scope: only `graphify/13-implementation/WP-I0-009/**` contains package implementation, test, and evidence files; Codebase remained read-only.

No remaining blocker or nonblocking concern was retained by the final reviewer.
