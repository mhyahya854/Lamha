# WP-I0-010 adversarial review

- Review method: independent read-only adversarial review over two separated rounds by an independent reviewer agent that did not author or modify package files; the first round attempted to disprove completion and returned seven findings, the second round re-reviewed the repaired state.
- Stable evidence generation: `3848217d732741f2efb63a3637f422d8d006fc42a3501d6698d8ce765c0c81a9`.
- Final verdict: **PACKAGE REVIEW PASS**.

## Defects found and repaired

Round-one findings, each verified repaired in round two:

- a JSX text-node URL (`license.email.tsx:40`) was silently masked as a `//` line comment and absent from the inventory; the `//`-after-`:` rule now keeps scheme separators, and the record (and its `jsx-text-node-url-not-comment` fixture) exists;
- configuration/manifest surfaces were fingerprint-only despite a "text-scanned" scope claim: `.tf`/`.hcl`, `.sql`/`.patch`/`.resolved`, `.entitlements`/`.xcsettings`, `.gitmodules`, `_redirects`, `Podfile`, `Podfile.lock`, and `LICENSE` are now scanned (70 additional text-scanned files, 43 additional records, including SwiftPM `github.com` pointers, `applinks:my.immich.app`, `_redirects` `awesome.immich.app`, and `LICENSE` `fsf.org`);
- Apple property-list `www.apple.com` DTD identifiers were recorded as outbound hosts; they are now excluded under `namespace-uri-identifier` while `apps.apple.com` and `developer.apple.com` still record;
- dead `DOC_SUFFIXES` constant removed;
- `completion-evidence.md` referenced this review file before it existed; this document now satisfies the reference;
- the verifier was extended from 18 to 23 required-record anchors covering the new surfaces, and from 32 to 35 required fixtures.

## Final independent verification

- Collector: `python graphify\13-implementation\WP-I0-010\collect_evidence.py` — exit 0.
- Independent verifier: `python graphify\13-implementation\WP-I0-010\verify_evidence.py` — exit 0.
- Corpus: 3,697 committed Codebase files, including 3,181 text-scanned files; full-corpus SHA-256 map equals WP-I0-001 before and after collection.
- Inventory: 2,993 integration records — 2,825 outbound-host, 84 cloud-service, 27 commercial-integration, 44 telemetry, 8 remote-model-path, and 5 update-check records, across ten mechanisms.
- Exclusions are deliberate and ledgered: 91 namespace identifiers, 102 single-label internal addresses, 31 unrecorded schemes, 22 loopback/private addresses, 10 RFC-2606 placeholders, 1 dynamic-userinfo expression.
- Negative/recovery suite: 35/35 PASS, including comment-masked parsers, template hosts, classifier boundaries, import parsing, container registries, pre-validation preservation, and byte-for-byte rollback after an injected mid-publication failure.
- Verifier oracle: full record-set recomputation from raw corpus bytes reconciles with the inventory (0 missing, 0 extra); all 23 required-record anchors confirmed at real Codebase lines (`config.repository.ts:321`, `config.ts:281-282`, `misc.ts:53`, `base.py:8,75-76`, `pyproject.toml:12`, `package.json:50,96`, `NewVersionCheckSettings.svelte:19`, `docker-compose.yml:15`, `install.sh:75`, `svelte.config.js:7-8`, `conftest.py:183`, `license.email.tsx:40`, `.gitmodules:3`, `Package.resolved:6`, `_redirects:31`, `LICENSE:4`).
- Disposition ownership is uniformly and deliberately `REVIEW_REQUIRED`; the inventory is descriptive baseline evidence, not a disposal decision.
- Scope: only `graphify/13-implementation/WP-I0-010/**` contains package implementation, test, and evidence files; Codebase remained read-only.

No remaining blocker or nonblocking concern was retained by the final reviewer.
