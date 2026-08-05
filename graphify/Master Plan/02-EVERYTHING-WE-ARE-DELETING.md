# LAMHA — EVERYTHING WE ARE DELETING

## Authoritative Master Plan File 2 of 3

**Application name:** Lamha  
**Document role:** Complete definition of every Immich product feature, server subsystem, dependency, workflow, architectural assumption, and rejected design that must not remain in the finished Lamha application  
**Authority:** This file is authoritative together with:

1. `01-EVERYTHING-WE-ARE-KEEPING.md`
2. `03-HOW-WE-WILL-KEEP-DELETE-AND-CHANGE.md`

This file defines the final removal target. It does not authorize premature deletion. Every removal must follow the dependency-aware process in File 3.

### Final-state and migration-state contract

- A `DELETE` requirement describes the final Lamha state, not permission to remove code before its evidence-backed replacement and verification prerequisites pass.
- Keeping legacy source available for evidence or isolated parity comparison does not make it part of the Lamha desktop runtime.
- The desktop launch/build path must become server-independent before the legacy source tree is removed.
- “Delete” never includes user media, user metadata, legal material, reusable neutral code, or retained behaviour without a proven replacement.

---

# 1. Deletion Principle

Lamha is not a stripped server hidden behind a desktop window.

The final product must not require or expose:

- Self-hosting
- Docker
- PostgreSQL server administration
- Redis
- User accounts
- Remote server URLs
- Browser-to-server architecture
- Public network APIs
- Cloud synchronization
- Mobile backup infrastructure
- Remote machine learning

The unwanted architecture must be removed after its retained behaviours are replaced.

Deleting a visible page while leaving the underlying server dependency is not completion.

> [!WARNING]
> **Scope Protection & Zero Feature-Loss Guardrail (`LAM-REMOVE-001`)**
> A weaker coding model MUST NEVER treat the deletion of a server subsystem (PostgreSQL, Redis, REST APIs, Docker, account services) as permission to delete or drop the underlying user-facing feature (gallery browsing, search, albums, sharing/export, AI processing, thumbnail generation, memories). Every user capability defined in `01-EVERYTHING-WE-ARE-KEEPING.md` MUST have a fully functioning local desktop equivalent in the target architecture before any corresponding server or database code is removed.

---

# 1.1 Replacement-Before-Removal Lifecycle Guardrail

> [!CAUTION]
> **PREMATURE DELETION PROHIBITION (`LAM-INV-COMP-03`)**  
> No legacy subsystem may be removed until its exact dependencies and retained behaviours are mapped, its local replacement is implemented, callers are migrated, applicable tests/build/desktop-launch checks pass, Graphify and Ponytail evidence agree that it is no longer load-bearing, and rollback or immutable baseline evidence exists.

### 1.1.1 Lifecycle Timing Rules
- **Phase 0 and Phase 1:** No source is removed; planning maps safe removal phases and prerequisites only.
- **Assigned safe implementation phase:** A subsystem may be removed when every file, symbol, caller, consumer, route, import, test, generated binding, build reference, configuration entry, and runtime dependency is mapped; retained behaviour has a working replacement; callers are migrated; focused/regression/build/desktop-launch checks pass; Graphify and Ponytail agree it is no longer load-bearing; baseline/rollback evidence exists; and removal proof is recorded.
- **Baseline preservation:** Git history, a recorded commit, signed inventory, verified archive, disposable snapshot, behaviour logs, Graphify graph hashes, or recorded test results may preserve baseline evidence. Obsolete files do not need to remain active solely for ceremony.
- **Phase 16:** Final cleanup removes remaining obsolete server, Docker, PostgreSQL, Redis, auth, sharing, mobile-backup, administration, dependency, generated-client, environment, documentation, and runtime-launch remnants, then performs repository-wide scans and packaging proof. It does not postpone already safe removals merely because of phase numbering.

---

# 1.2 Objective 4-Prerequisite Definition of "Removed"

Weaker coding models regularly delete files blindly without checking whether desktop modules still import them. A server subsystem or legacy module is marked `Verified Removed` ONLY when all four objective criteria are met:
1. **Runtime Execution Isolation:** The compiled desktop application launches and operates with zero background server daemon spawning.
2. **Import Tree Eradication:** Zero SvelteKit, TypeScript, or Rust source files contain `import` or `use` statements referencing the target module or package.
3. **Clean Autonomous Build:** The repository-derived release build and package commands succeed with the legacy server directories absent from disk.
4. **Automated Dependency Rescan:** The verified dependency scanner defined during Phase 1 returns zero final-state server violations across source, manifests, installers, and runtime launch paths.

The exact commands and scanner paths are not assumed by this Master Plan. Phase 0 records current commands; Phase 1 defines any missing target verification command and its owner phase. A command name shown later is a planned interface until the mapping tracker proves it exists.

---

# 1.3 Rejected Terminology Linter Registry

To prevent lower-capability coding models from re-introducing server-centric or ambiguous concepts, the planned terminology linter applies to final target production identifiers, target UI text, and target architecture prose. It must allow documented legacy/removal contexts, quoted upstream text, tests that assert rejected wording, legal notices, generated/vendored exclusions, and the Master Plan itself. The exact linter path is established during mapping rather than assumed here.

| Prohibited Term / Pattern | Why It Is Banished | Mandatory Replacement Vocabulary | Linter Enforcement Target |
|---|---|---|---|
| `aiChecked` | Insufficient single boolean; ignores models, hashes, and task invalidation. | Per-task status, invalidation/staleness, model identity/version, source identity/hash, configuration identity/hash, and processing-time concepts; exact serialization is selected during target-schema mapping. | All `.ts`, `.svelte`, `.rs`, `.json` files. |
| `sync to cloud` / `cloud storage`| Violates local-first, offline-only architectural invariant. | `local library root`, `offline storage`, `external drive`. | All UI text, documentation, comments. |
| Lamha `server URL` / internal Lamha `api endpoint`| Refers to a legacy HTTP application server slated for deletion. | `Tauri IPC command` for UI-to-core; mapped non-network local IPC for Rust-to-worker. | Target UI-to-core client utilities. Explicit opt-in outbound provider clients (for example map tiles) require separate allowlisting and disclosure. |
| `user account` / `login session`| Violates single-user desktop application identity. | `local desktop user`, `library profile`. | All UI authentication stubs and stores. |
| PostgreSQL `database migration` in the target runtime | Confuses embedded SQLite index initialization with PG migrations. | `SQLite index initialization`, `index schema upgrade`, `rebuildable index sync`. | Target Rust index modules; documented legacy PG contexts are allowed. |
| `tag folder` / `person folder`| Implies illegal physical directory creation on disk for virtual views. | `tag view`, `person gallery tab`, `virtual smart view`. | All filesystem organizer scripts. |

---

# 1.4 Low-Capability Model Failure Modes & Defensive Blocks (`FAIL-01` to `FAIL-32`)

To inoculate the specification against predictable shortcuts by weaker coding models, the following 32 failure modes are cataloged alongside their binding defensive prohibitions and automated linter blocks:

| Failure Mode ID | Predictable Weaker Model Shortcut / Mistake | Why Unhardened Plan Allowed It | Exact Binding Hardening Prohibition & Defensive Block | Verification Gate / Linter Rule That Blocks It |
|---|---|---|---|---|
| **FAIL-01** | Skipping video, HEIF, supported RAW, or companion-media handling during ingestion. | Narrative mentioned “photos and videos” without a verified format/pairing matrix. | The local media layer MUST decode/preview and extract metadata for File 3 Section 24 formats. Derived previews may transcode through bundled tooling; originals are never silently transcoded/overwritten; Live Photo and RAW+JPEG containers remain linked independent bundles. | Mapped cross-format ingestion/preview and Companion Set tests; exact command recorded in Phase 1. |
| **FAIL-02** | Writing stub functions (`todo!()` or empty `Ok(())`) or mock data arrays to pass compilation. | Lacked explicit prohibition against stubbing and prototyping. | **Anti-Prototype Rule (`LAM-INV-COMP-02`)**: Zero stubs, TODO macros, or dummy mock JSON arrays are permitted as completed production behaviour. | Mapped placeholder-production scan plus symbol review. |
| **FAIL-03** | Building Svelte UI screens with hardcoded mock data without wiring Tauri IPC or SQLite. | Allowed marking frontend done separately from backend logic. | **Gate 5 (Tauri IPC Wiring)**: Completed target screens must invoke live mapped Tauri commands and display real local data. | Mapped UI/IPC end-to-end test; exact runner and test path recorded in Phase 1. |
| **FAIL-04** | Silently dropping XMP sidecar generation to save disk I/O. | JSON sidecars were emphasized over XMP. | **LAM-INV-ASSET-03**: Every writable managed asset must converge to co-located `.asset.json` and `.xmp`; degraded/read-only states remain visible until repaired/reconciled. | Mapped sidecar coexistence, degraded-state, and reconciliation tests. |
| **FAIL-05** | Creating physical directories on disk for People, Groups, Albums, or Tags. | Lacked explicit distinction between physical placement classes and virtual views. | Category folders are forbidden. Valid physical classes are dated or unknown-date normalized Event Folders, Manage Later, Linked Folders, and explicit system-controlled backup/Trash/staging/cache/overlay/export locations. | Mapped zero-category-copy safety test. |
| **FAIL-06** | Automatically merging face clusters without user review in Review Centre. | AI section didn't specify human-in-the-loop gating for cluster merges. | **LAM-INV-AI-01**: Workers return typed results to Rust; consequential candidates enter Review; only the Rust core may persist approved JSON after user action/approved narrow rule. | Mapped AI zero-authority and cluster-review tests. |
| **FAIL-07** | Exposing the local AI worker through HTTP, WebSocket, TCP, UDP, or another listener available to unrelated clients. | “Worker” was underspecified and models default to service processes. | **LAM-AI-001**: Svelte-to-Rust transport is Tauri IPC. Rust-to-worker transport is a non-network local IPC mechanism chosen after Phase 1 maps existing ML transport, lifecycle, streaming, cancellation, Windows/macOS/Linux compatibility, packaging, and security. Standard input/output, named pipes, Unix-domain sockets, Tauri sidecar communication, or another validated local mechanism may be used, but no listening TCP/UDP port or HTTP/WebSocket service is permitted. | Mapped process/listener isolation and IPC lifecycle tests. |
| **FAIL-08** | Overwriting original filename when renaming or moving assets into Event folders. | Filename preservation rule was not marked immutable. | **LAM-INV-ASSET-05**: Original filename at ingestion must be permanently saved in `.asset.json` under the Phase 1-mapped schema field and never overwritten. | Mapped original-filename immutability and restore test. |
| **FAIL-09** | Deleting Docker, PostgreSQL, Redis, or server code before exact callers and retained behaviour are mapped and replaced. | Deletion list did not specify objective lifecycle prerequisites. | **Replacement-Before-Removal Guardrail**: Phase 0/1 perform no source deletion. Later removal occurs only in the assigned safe phase after mapping, replacement, caller migration, focused/regression/build/desktop-launch proof, Graphify/Ponytail agreement, baseline/rollback evidence, and recorded removal proof. | Assigned-phase dependency scan, affected gates, and final Phase 16 repository-wide rescan. |
| **FAIL-10** | Treating SQLite as authoritative and failing to persist saved user decisions transparently. | SQLite speed was highlighted without defining durable JSON authority. | **LAM-INV-META-03**: Delete SQLite/rebuildable caches and rebuild from filesystem state plus authoritative asset/event/person/group/relationship/map/tag/album/operation JSON; saved decisions must survive. | Mapped destructive-cache-loss rebuild test on a test copy. |
| **FAIL-11** | Modifying assets in Linked Folders during event organization or deduplication. | Linked folders were not explicitly protected from automated restructuring. | **LAM-INV-EVENT-03**: Linked assets are indexed in place and automated event/deduplication workflows must never move or rename them, regardless of filesystem writability. | Mapped linked-folder immobility test. |
| **FAIL-12** | Conflating hardware Camera Owner with Photographer in metadata schemas. | Both terms appeared in metadata discussions without separation rules. | **LAM-REMOVE-002**: Hardware camera owner and photographer are distinct fields and must never silently inherit from one another. | Mapped role-separation unit and workflow tests. |
| **FAIL-13** | Auto-populating asset visible faces from event attendee lists. | “Attendees” and “People in Photo” were assumed equivalent. | **LAM-REMOVE-003**: Event attendees in the event record and visible people in the asset record must never auto-populate each other; serialized key spellings are selected by the Phase 1 target-schema map. | Mapped attendee/visible separation tests. |
| **FAIL-14** | Dropping historical group membership dates and keeping only current active members. | Group schema didn't enforce temporal membership interval records. | **LAM-INV-PERSON-03**: Removing a person closes the active interval at the user-approved effective end date; the serialized key spelling is selected by the Phase 1 target-schema map, and historical photos retain prior membership. | Mapped temporal-interval and historical-query tests. |
| **FAIL-15** | Flattening nested group hierarchies into single-level tag lists. | Recursive subgroup relationships were not strictly enforced. | **LAM-GROUP-001**: Groups preserve stable parent-group nesting and cycle-safe tree traversal in the derived index; the serialized key name is selected during target-schema mapping. | Mapped group-nesting and cycle-rejection tests. |
| **FAIL-16** | Throwing unhandled write exceptions or claiming edits reached a read-only drive. | Lacked a provisional-authority rule for read-only external storage. | **LAM-EDGE-05**: Activate Detached Index Mode; persist versioned Pending Overlays in OS application data; reconcile only after identity/version/conflict checks. | Mapped read-only overlay and reconciliation test. |
| **FAIL-17** | Splitting continuous midnight-spanning celebrations into two separate event folders. | Date-based naming assumed midnight cutoff without user event authority. | **LAM-EDGE-06**: Midnight or gap heuristics may suggest a split but never execute it; the approved event start date and user decision control unity. | Mapped midnight unity and suggestion-only test. |
| **FAIL-18** | Re-suggesting an equivalent rejected candidate because of score drift or a routine rerun. | Rejection identity and scope were underspecified. | **LAM-INV-AI-02**: Persist task/candidate/model/source/configuration provenance and suppression scope. Equivalent automatic reruns respect the decision. An explicit user reopen/reanalysis request or a material source, model/version, relevant-configuration, candidate-identity, or evidence change may create a new Review candidate while preserving the prior decision. | Mapped rejection-persistence, controlled-reconsideration, provenance-history, and score-drift tests. |
| **FAIL-19** | Checking off requirement TODOs after running only syntax/type checks. | Definition of complete lacked applicable-gate proof. | **Gate 8 (Tracker Proof Linkage)**: `[x]` requires exact changed symbols, commit/worktree reference, outputs for every applicable gate, and reasoned `N/A` entries for non-applicable gates. | Verified tracker-proof validation defined during Phase 1. |
| **FAIL-20** | Leaving partial file moves or corrupted sidecars when the app crashes/disconnects during a batch transfer. | Transaction preparation and durable recovery authority were not enforced. | **LAM-TRANSACTION-001**: Before mutation, fsync a transparent PREPARED coordinator manifest in OS application data plus mirrors on affected writable roots; reconcile by transaction UUID; verify before commit/source removal. | Mapped failure-injection, disconnect, SQLite-loss, and restart-recovery test. |
| **FAIL-21** | Hardcoding Windows `C:\` or macOS `/Users/` paths in filesystem utilities. | Cross-platform path resolution was not tested against simulated roots. | **Gate 4**: Path utilities must use OS-native path APIs and pass Windows/macOS/Linux root, permission, and separator cases. | Mapped cross-platform path/permission test matrix. |
| **FAIL-22** | Inventing cloud backup, S3 sync, or multi-user login screens to make the app feature-rich. | Scope limits were not enforced against creative expansion. | **Scope Drift Prohibition**: Zero cloud, remote sync, multi-user accounts, or server listening sockets are permitted. Local desktop only. | Linter & architectural dependency review. |
| **FAIL-23** | Asking the user in chat output to write Rust code or complete UI component TODOs. | Autonomous execution rules did not ban homework requests. | **Autonomous Codex Rules (`LAM-INV-COMP-01`)**: Model must fully implement and verify every requirement autonomously without prompting user for code. | Execution monitoring & transcript audit. |
| **FAIL-24** | Guessing file paths or inventing simplified schemas when encountering ambiguity. | Lacked strict fallback protocols for underspecified items. | **Anti-Guessing Guardrail**: If an item is ambiguous, model must halt on that item, log in `BLOCKED_OR_UNKNOWN.md`, and continue independent tasks. | Tracker audit & execution control verification. |
| **FAIL-25** | Reintroducing a closed one-category-per-person enum or guessing composition from relationship labels. | Detailed edges, certainty, and view projection were conflated. | **LAM-REL-001**: People may have multiple simultaneous/historical built-in and custom relationship edges. Certainty is orthogonal. Three composition buckets—Family, Friends, Family Friends—derive the nine views through explicit approved projection rules; Spouse contributes to Family and Classmate does not automatically mean Friend. | Mapped multi-edge, certainty, history, custom-type, projection, and nine-view tests. |
| **FAIL-26** | Modifying physical media files when applying non-destructive crop, rotate, or color edits. | Non-destructive editing rules didn't explicitly forbid container mutation. | **LAM-INV-ASSET-01**: Normal edits store instructions in `.asset.json` and mirror compatible fields to XMP; export/derivative creation never silently overwrites the primary media. | Mapped primary-immutability and derivative-UUID tests. |
| **FAIL-27** | Creating a 4th Master Plan file or placing Lamha planning notes inside `Codebase/`. | Workspace boundary rules were not enforced. | **Directory Separation Invariant**: `Codebase/` is for repository/runtime artifacts; Lamha planning/mapping resides in `Graphify/`; exactly three authoritative Master Plan files exist. | Mapped workspace-boundary structural validation. |
| **FAIL-28** | Silently resolving metadata conflicts between EXIF, JSON, XMP, overlays, or event/person/group records. | Directional authority was not treated as domain-scoped. | **Directional Source-of-Truth Matrix**: Apply File 1 Section 1.3; external mirror changes become Review candidates and never silently overwrite JSON authority. | Mapped metadata-conflict and overlay-conflict tests. |
| **FAIL-29** | Using the legacy single `aiChecked` boolean instead of tracking per-task model versions and hashes. | Lacked schema enforcement for AI processing invalidation tracking. | **LAM-INV-AI-04**: AI task state represents the seven required concepts and canonical state semantics in File 1 Section 22.3; serialized key spellings are selected by the Phase 1 target-schema map. | Mapped schema/terminology validation and invalidation tests. |
| **FAIL-30** | Materializing Mind Map draft nodes directly to media folders without user confirmation. | Saved draft persistence and physical execution were conflated. | **Mind Map State Machine**: Unsaved working state may use SQLite; saved drafts persist to map JSON; neither mutates media folders until explicit simulation, validation, confirmation, and durable transaction. | Mapped draft-persistence and sandbox-immutability tests. |
| **FAIL-31** | Permanently deleting files immediately when a user moves them to Trash. | Trash recovery and placement were inconsistent. | **LAM-TRASH-001**: Trash stores the complete bundle under root-scoped `.app-data/trash/` when possible; a cross-drive fallback is reviewed and verified; permanent deletion requires an explicit empty/permanent-delete action. | Mapped Trash staging, restore, and cross-drive test. |
| **FAIL-32** | Stopping implementation after a phase without a genuine blocker or user stop instruction. | Sequential workflow did not define transition evidence. | **Autonomous Codex Workflow**: When Phase N satisfies its phase gate plus every applicable verification gate and proof is recorded, proceed to Phase N+1. | Completion tracker transition audit. |

---

# 2. Server Product Architecture to Delete

The final Lamha application must delete the requirement for:

- Immich server runtime
- Standalone backend server process
- Externally accessible HTTP API
- REST server used by the desktop frontend
- WebSocket server used as a remote service
- Server-hosted asset APIs
- Server-hosted metadata APIs
- Server-hosted search APIs
- Server-hosted people APIs
- Server-hosted album APIs
- Server-hosted sharing APIs
- Server-hosted administration APIs
- Remote job-control APIs
- Remote machine-learning APIs
- Server URL configuration
- Reverse-proxy assumptions
- Network deployment configuration
- Domain and certificate setup
- Multi-host deployment assumptions
- Self-hosting instructions in the final user experience

A bundled local worker using local IPC is not considered a retained server, provided it exposes no network listener and exists only to support the desktop app.

---

# 3. Docker and Container Deployment to Delete

The final Lamha application must not require:

- Docker
- Docker Compose
- Container orchestration
- Container volumes
- Container networking
- Docker Desktop
- WSL2 for ordinary Windows use
- Linux-only self-hosting setup
- Container health checks
- Container startup scripts
- Container deployment variables
- User-facing Docker troubleshooting
- Docker administration controls

> [!CAUTION]
> **Docker & Server Dependency Timing Guardrail**
> During Phase 0 and Phase 1, Docker files, database container scripts, and server deployment configs remain untouched while dependencies and baseline evidence are mapped. In a later assigned safe phase, an item may be removed only after the replacement-before-removal prerequisites in Section 1.1 pass. Any remaining obsolete material is removed in Phase 16, followed by repository-wide dependency and packaging proof.

---

# 4. PostgreSQL Server Dependency to Delete

The final app must delete the requirement for:

- PostgreSQL server
- PostgreSQL service setup
- PostgreSQL network connection
- PostgreSQL credentials
- PostgreSQL administration
- PostgreSQL migrations as the sole product data store
- PostgreSQL extensions required for core use
- VectorChord or equivalent server extension requirements
- Server database backups as the only backup method
- Database-only user metadata

The retained search and indexing behaviours are replaced by a local SQLite/index architecture and transparent sidecars.

Do not delete PostgreSQL-dependent code until Graphify has mapped and replaced every retained caller.

---

# 5. Redis and Server Queue Dependencies to Delete

The final app must delete the requirement for:

- Redis service
- Redis network connection
- Redis credentials
- Redis-backed job queues
- Distributed worker assumptions
- Server queue dashboards
- Cross-machine job processing
- Server queue retry infrastructure that exists only for distributed deployment

The required behaviour is replaced by a local desktop job manager with:

- Pause
- Resume
- Recovery
- Progress
- Local persistence
- Per-task state
- No network service

---

# 6. Authentication and Account Systems to Delete

Lamha is single-user and local.

Delete:

- Registration
- Login
- Logout
- Password authentication
- Password reset
- Email verification
- OAuth
- OpenID Connect
- Session cookies
- Access tokens
- Refresh tokens
- Account recovery
- User invitations
- User onboarding for multiple accounts
- User profile switching
- User role management
- Admin roles
- User permission tables
- Per-user storage ownership
- User quota enforcement
- Account deletion flows
- User audit tools
- Authentication middleware
- Authentication guards
- Login route redirection
- Remote session management

A local optional app lock may be considered later, but it is not the existing Immich authentication system and must not preserve the server account architecture.

---

# 7. Multi-User Features to Delete

Delete:

- Multi-user accounts
- Per-user libraries
- Partner sharing
- User-to-user asset visibility
- Shared ownership
- Shared album permissions
- User invite workflows
- User-level quotas
- User administration
- User activity dashboards
- User-scoped server storage
- Cross-user face data
- Cross-user album collaboration
- Multi-user API permissions

Lamha retains one user’s local library only.

---

# 8. Public and Remote Sharing to Delete

Delete:

- Public sharing links
- Remote asset links
- Remote album links
- Expiring server links
- Link passwords
- Public download pages
- Public presentation pages
- Remote guest access
- Internet-based shared albums
- Partner sharing
- Public API exposure
- External client API keys
- Remote webhook delivery
- Remote integrations that require Lamha to run as a server

Local export of files or metadata may remain, but that is not remote sharing.

---

# 9. Mobile Backup and Phone Synchronization to Delete

Delete the Immich server-side mobile backup product:

- Phone auto-upload
- Mobile backup endpoints
- Background phone synchronization
- Upload queues from mobile devices
- Remote camera roll backup
- Mobile-device server pairing
- Server-side upload sessions
- Remote deduplication for phone uploads
- Mobile backup status pages
- Phone device management
- Server notifications for mobile backup
- Remote media ingestion from the mobile app

Lamha may import files that the user manually places in a local folder, including `Manage Later`, but it is not a phone backup server.

---

# 10. Remote Upload and Ingestion to Delete

Delete:

- Browser upload to remote server
- Network upload endpoints
- Chunked remote upload
- Remote multipart upload
- Remote upload sessions
- Server ingestion paths
- Upload authentication
- Remote storage ownership
- Upload quotas
- Remote background import jobs

Local file selection, local folder scanning, and local filesystem import are retained.

---

# 11. Email and Invitation Infrastructure to Delete

Delete:

- SMTP configuration
- Email templates for accounts
- Email verification
- Password-reset emails
- Invitation emails
- Sharing emails
- Server notification emails
- Email delivery jobs
- Email administration
- Mail-provider dependencies

Lamha does not need email to function.

---

# 12. Server Administration to Delete

Delete final-user access to:

- Server dashboard
- User administration
- Server statistics
- Server health administration
- Queue administration
- Storage quota administration
- Remote machine-learning administration
- Server version management
- Remote worker management
- Network configuration
- API-key management
- SMTP management
- OAuth management
- Reverse-proxy configuration
- Container management
- Database administration
- Server logs intended for self-hosting operations

Lamha may retain a local diagnostics page for:

- Local index health
- Sidecar health
- AI job state
- Drive state
- Backup state
- Local logs

That local diagnostics page is not the old server administration product.

---

# 13. Storage Quotas and Server Ownership to Delete

Delete:

- Per-user storage quotas
- Server-managed asset ownership
- Server upload allocation
- Server-owned media root assumptions
- Remote storage quota warnings
- Admin quota overrides
- User storage reports
- Storage limits tied to accounts

Lamha uses user-selected local filesystem roots.

---

# 14. Cloud and Remote Storage to Delete

Delete:

- Cloud synchronization
- Cloud backup
- SaaS storage
- Remote storage accounts
- Cloud-provider credentials
- Automatic off-device upload
- Cloud-only metadata
- Cloud-hosted thumbnails
- Cloud-hosted embeddings
- Cloud-hosted face data
- Remote AI result storage
- Cloud dependency for memories or search

Local external drives and local backups remain supported.

---

# 15. Remote Machine Learning to Delete

Delete:

- Remote machine-learning URL
- Network ML requests
- HTTP ML service exposed as a server
- Cloud face recognition
- Cloud semantic search
- Cloud OCR
- Cloud object detection
- Remote embeddings
- Remote model processing
- Third-party upload of media for AI

The AI capability itself is retained and replaced with a bundled local worker.

---

# 16. Network Dependency to Delete

The final app must not require:

- A local browser connecting to a server
- A configured hostname
- A server IP address
- An open TCP port
- LAN discovery
- Internet discovery
- TLS certificates
- Remote API availability
- Internet access for core media functions
- Network database access
- Network cache access
- Remote worker availability

Optional online map tiles or manually triggered updates may be offered later, but they must remain optional and disabled by default.

---

# 17. Telemetry and Unrequested External Communication to Delete

Delete or disable by default:

- Usage telemetry
- Product analytics
- Remote error reporting
- Automatic media analysis by third parties
- Automatic external model calls
- Hidden update checks
- Advertising identifiers
- Remote feature flags required for core behaviour
- Background internet communication not explicitly initiated by the user

Local logs remain.

Any optional diagnostics submission must be explicit, visible, and user-controlled if ever added.

---

# 18. SaaS and Subscription Logic to Delete

Delete:

- Subscription tiers
- SaaS billing
- Cloud storage plans
- Account upgrade prompts
- Paid remote features
- Server licensing screens unrelated to open-source obligations
- Usage-based remote quotas
- Cloud entitlement checks
- Online account gating

Lamha remains a local application.

---

# 19. Server-Only Notification Infrastructure to Delete

Delete:

- Remote push infrastructure
- Server event broadcasting to remote clients
- User-targeted server notifications
- Mobile push dependencies
- Network notification brokers
- Distributed event buses used only for server clients

Replace retained notification behaviour with:

- Local desktop notifications
- In-app Review Centre
- Local job progress
- Local warnings
- Local operation completion messages

---

# 20. Database-Only Metadata Model to Delete

Delete the design assumption that the database is the only authoritative copy of:

- Person names
- Face assignments
- Relationships
- Groups
- Event membership
- Tags
- Albums
- Favorites
- Photographer
- Map layouts
- Review decisions
- Suppression decisions
- History
- User metadata corrections

The local SQLite database remains a rebuildable index/working-state store only. Saved user decisions, durable operation history, and unresolved read-only overlays must survive SQLite loss through transparent JSON records.

---

# 21. Automatic Event Detection to Delete

Delete automatic event creation and automatic event claims based on:

- Time gaps
- GPS proximity
- Same day
- Same people
- Same camera
- Similar content
- Folder-name guesses
- Burst grouping

Lamha may summarize these facts to help the user manually create an event.

It must not create an event, rename a folder, merge folders, or move media based on an automatic event guess.

---

# 22. Person-Based Physical Folder Design to Delete

Delete the idea of physically organizing media under:

```text
Friends/
Family/
Family Friends/
Person Name/
```

as the primary ownership model.

This design fails when:

- Several people appear
- Family and friends appear together
- Relationships change
- A person belongs to several groups
- An event contains many relationship categories
- One asset would need several copies

People remain metadata and virtual views.

> [!IMPORTANT]
> **Physical Folders vs. Virtual Views Reinforcement**
> As defined in File 1, Lamha-normalized managed storage is event-first (`Year/YYYY-MM-DD_Event-Name/` or `Unknown Date/Unknown-Date_Event-Name/`). The only other valid placement classes are Manage Later, Linked Folders, and explicit system-controlled backup/Trash/staging/cache/overlay/export locations. A weaker coding model MUST NEVER create category folders for People, Groups, Relationships, Albums, or Tags or copy authoritative media to simulate categorization.

---

# 23. Relationship-Composition Physical Root Folders to Delete

Delete physical root folders such as:

```text
Family Only/
Friends Only/
Family + Friends/
Mixed Relationships/
Unknown Group/
```

These remain smart views only.

Physical storage remains:

```text
Year/
└── YYYY-MM-DD_Event-Name/
```

---

# 24. Physical Duplication for Tags or People to Delete

Delete:

- Copying an asset into every person folder
- Copying an asset into every group folder
- Copying an asset into every album
- Copying an asset into every relationship view
- Copying an asset into every tag folder
- Copying an asset into every event-attendee folder

Virtual references must be used instead.

---

# 25. Silent AI Finalization to Delete

Delete behaviour where AI silently:

- Names a person
- Confirms a face
- Applies a final relationship
- Applies a final group
- Applies a final photographer
- Creates an event
- Changes a date
- Moves a file
- Changes a location
- Removes metadata
- Deletes a duplicate

Consequential AI findings enter Review unless the user has explicitly approved a narrowly defined reusable rule. Rebuildable machine data such as embeddings, thumbnails, hashes, OCR indexes, and similarity vectors may be generated automatically but never becomes approved user metadata by implication.

---

# 26. Single `aiChecked` Boolean to Delete

Delete the design:

```json
{
  "aiChecked": true
}
```

It is insufficient because models, settings, files, and tasks may change independently.

Lamha uses per-task state concepts across the SQLite working store and local cache (matching File 1 Section 22.3 and File 3 Section 18.3): task status, model identity, model version, source identity or hash, relevant configuration identity or hash, processing time, and invalidation/staleness state. Phase 1 target-schema mapping selects the exact serialized field names and internal database representation.

---

# 27. Camera Owner Equals Photographer Assumption to Delete

Delete any rule that assumes:

```text
Camera owner = photographer
```

The app must preserve separate fields for:

- Camera owner
- Photographer
- Uploader/importer
- Visible people

> [!IMPORTANT]
> **Asset Roles Disambiguation Reinforcement**
> As mandated by the Disambiguation Matrix in File 1 (Section 17), these four entities are completely separate and must never be merged or substituted for one another in code, schemas, or UI tags:
> 1. `Camera Owner`: The hardware owner of the capture device.
> 2. `Photographer`: The entity (human, self-timer, tripod, screenshot, scanner) that captured the frame.
> 3. `Visible Person`: A human visually appearing inside the image frame.
> 4. `Event Attendee`: A person present at the event (who may not appear in the photo at all).

---

# 28. Event Attendee Equals Visible Person Assumption to Delete

Delete any rule that marks every attendee as visible in every asset.

Use separate tags:

```text
Event Attendee/Ali
Visible Person/Ali
Photographer/Ali
```

---

# 29. Group Presence Equals Visible Group Assumption to Delete

Delete any rule that gives every event asset:

```text
Visible Group/The Gooners
```

merely because The Gooners attended the event.

Visible-group tags require at least one relevant visible confirmed person.

---

# 30. Retroactive Historical Erasure to Delete

Delete behaviour that rewrites history merely because a current relationship or membership changed.

Examples of behaviour to reject:

- Removing old Gooners context because Ali later left
- Changing historical active membership to current former-member status
- Erasing old relationship context because a person became Family
- Removing old event participation after a group rename

Current state and state-at-event-time must remain distinguishable.

---

# 31. Text-Only Group Identity to Delete

Delete a group identity model based only on editable text:

```json
{
  "group": "Gooners"
}
```

Lamha uses a stable group ID.

The current name may change without destroying references.

---

# 32. Destructive Metadata Removal Defaults to Delete

Delete:

- Removing embedded metadata without a snapshot
- Removing GPS silently
- Rewriting media without backup
- Overwriting metadata without preview
- Batch stripping without scope display
- Deleting app metadata and embedded metadata through one ambiguous action
- Treating privacy export and original mutation as the same action

Lamha keeps separate reviewed operations.

Clearing selected Lamha fields retains the minimal identity sidecar for a managed asset. Removing all Lamha sidecars is the separate **Unmanage Asset** operation and changes the asset to unmanaged state; it must not leave a falsely healthy index record.

---

# 33. Automatic Original Overwrite to Delete

Delete:

- Automatic image overwrite after editing
- Automatic video overwrite
- Automatic recompression
- Automatic transcoding of originals
- Automatic pixel changes
- Automatic container rewrite
- Automatic metadata rewrite without backup

Non-destructive edited copies remain.

---

# 34. Automatic Permanent Deletion to Delete

Delete:

- Automatic duplicate deletion
- Automatic Trash purge
- Fixed 30-day purge
- Silent permanent deletion
- Permanent-delete button enabled by default
- Deleting sidecars while leaving media
- Deleting media while leaving orphan sidecars

Permanent deletion remains disabled unless deliberately enabled. Even when enabled, it requires an explicit scoped action and must remove the complete bundle only after identity/path verification.

---

# 35. Silent File Movement and Folder Materialization to Delete

Delete:

- Moving a file after a map drag without confirmation
- Creating folders immediately while the user is drafting
- Renaming a folder without preview
- Merging event folders without review
- Splitting an event automatically
- Moving files after an AI suggestion
- Moving files merely because a date conflict was detected
- Changing external-drive content without an explicit transaction

Draft / Safe map mode remains non-mutating.

---

# 36. Filename-Only Asset Matching to Delete

Delete matching external moves based only on filename.

Lamha must use multiple signals:

- Asset ID
- Hash
- Partial hash
- Size
- Dates
- Sidecar references
- Original filename

---

# 37. Three Identical Confirmation Dialogs to Delete

The user requires strong confirmation for Sure relationship changes.

Delete the poor implementation of showing the same popup three times.

Use:

1. Change selection
2. Impact review
3. Final explicit confirmation

---

# 38. Automatic Event-Based Group Tagging to Delete

Delete automatic visible-group tagging based solely on event group membership.

Event metadata may still record groups present.

Visible-group tags require visible people.

---

# 39. Server-Specific UI to Delete

Delete or replace user-facing UI for:

- Login
- Registration
- Server selection
- Server URL
- Account management
- User administration
- Partner sharing
- Public links
- Mobile backup
- Remote upload
- API keys
- SMTP
- OAuth
- Server storage quotas
- Server jobs
- Server health
- Container management
- Database management
- Remote ML configuration
- Self-hosting setup

Do not delete reusable visual components merely because they appear on an unwanted page. Graphify must classify shared components first.

---

# 40. Unneeded Code and Dependencies to Delete After Mapping

Graphify must identify every item below, assign its safe removal phase and prerequisites, and ensure Phase 16 removes any remaining obsolete remnants:

- Dead server controllers
- Dead services
- Dead repositories
- Dead database entities
- Dead migrations
- Dead API clients
- Dead generated API bindings
- Dead auth middleware
- Dead account stores
- Dead sharing modules
- Dead mobile-backup modules
- Dead email modules
- Dead admin modules
- Dead Docker scripts
- Dead server deployment configs
- Dead Redis clients
- Dead PostgreSQL clients
- Dead server-only tests
- Dead server-only fixtures
- Dead dependencies
- Dead exports
- Dead routes
- Dead environment variables
- Dead documentation for removed user workflows
- Obsolete architecture
- Duplicate implementations

> [!IMPORTANT]
> **Deterministic Deletion Prerequisites**
> Deletion must occur only after: (1) every caller, consumer, import, and route is mapped in Graphify; (2) a local desktop replacement in Rust/Tauri/SQLite is implemented; and (3) focused and regression tests prove the replacement passes without relying on the legacy dependency.

---

# 41. Planning Markdown Inside Codebase to Delete or Prevent

Lamha planning, mapping, tracking, audit, status, completion, handoff, and Graphify-generated Markdown must not be scattered through `Codebase/`.

They belong under:

```text
Graphify/
```

README files, licences, copyright and AGPL text, third-party notices, security and contribution documentation, source-repository architecture documentation, build-required/package/generated-source/vendored/upstream technical documentation, and documentation required by CI, packaging, or release workflows may remain in `Codebase/` when required. Graphify must classify every meaningful Markdown file. No Markdown file may be deleted merely because of its extension.

The rule is:

```text
No Lamha planning, mapping, tracking, audit, status, completion, handoff, or Graphify-generated Markdown inside Codebase.
```

---

# 42. Old Branding to Delete

Delete visible Immich branding from the final Lamha product:

- Product name
- App title
- Executable display name
- User-visible package references
- User-facing icons
- User-facing descriptions
- Server-oriented wording
- Self-hosting wording

Required legal attribution and copyright notices must remain.

---

# 43. Premature Deletion Is Forbidden

The following behaviour is itself rejected:

- Deleting all server code before replacing frontend APIs
- Deleting shared types before creating local equivalents
- Deleting database models before mapping retained data
- Deleting ML code because it currently runs as a service
- Deleting thumbnail/video processing before local replacement
- Deleting tests merely because they target old architecture
- Deleting docs that contain needed behaviour knowledge
- Deleting generated API clients before every caller is migrated
- Deleting authentication before the app can boot without it
- Deleting Docker before a baseline is captured, when Docker is temporarily needed to prove the current app

> [!CAUTION]
> **Anti-Premature Deletion Guardrail**
> Replacement must precede removal in all circumstances. If a test fails after deleting a module, it is illegal to delete or disable the failing test unless Graphify explicitly proves the test targeted an exclusively server-only workflow that has no retained desktop equivalent.

---

# 44. Material That Must Not Be Deleted

Do not delete:

- User media
- User sidecars
- User metadata
- Original filenames
- Metadata snapshots
- Required legal notices
- Required source licence text
- Required attribution
- Reusable UI without dependency analysis
- Useful tests that can be adapted
- Useful AI logic that can be ported
- Useful media-processing logic that can be ported
- Current code before Graphify maps it
- Uncommitted user work
- Repository history

---

# 45. Graphify Deletion Mapping Requirements

For every deletion target, Graphify must record:

- Deletion requirement ID
- Source section and atomic deletion text
- Graph node/edge/query provenance, direction, and evidence class
- Current file path
- Current line range
- Symbol
- Current purpose
- Every caller
- Every import
- Every route
- Every API endpoint
- Every shared type
- Every database dependency
- Every worker dependency
- Every test
- Retained behaviour relying on it
- Replacement requirement
- Safe removal phase
- Proof required
- Current status
- Final absence/dependency-scan proof scope

No deletion may be described only as:

```text
Remove server.
```

It must be mapped file by file and symbol by symbol.

---

# 46. Definition of “Deleted”

An unwanted capability or subsystem is considered deleted only when:

- Its user-facing behaviour is absent.
- Its routes are absent.
- Its code is absent or proven required as a neutral shared utility.
- Its dependencies are removed when no longer needed.
- Its environment variables are removed.
- Its tests are removed or adapted appropriately.
- No retained feature imports it.
- No runtime starts it.
- No installer requires it.
- No hidden network service remains.
- Builds pass without Docker, PostgreSQL, or Redis running.
- Focused and regression tests pass cleanly.
- Graphify marks it Verified Removed with explicit proof (commit/test logs).
- A final automated dependency scan confirms the removed subsystem is no longer load-bearing or imported by any retained file in `Codebase/`.
