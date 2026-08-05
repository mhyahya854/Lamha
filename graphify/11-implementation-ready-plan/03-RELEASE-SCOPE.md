# Product and release scope

## Non-negotiable final product

Lamha manages a private local photo/video library with event-first physical organization, stable identities, transparent recoverable metadata, review-first AI, people/group/relationship knowledge, global and scoped mind maps, non-destructive edits, external-drive resilience, backup/Trash/rebuild, and desktop packages for Windows, macOS, and Linux.

## Explicit non-goals

- Multi-user accounts, permissions, invitations, public sharing, remote uploads, phone backup/sync, SaaS, subscription logic, server administration, cloud storage, or a required network service.
- Automatic physical folders for people, groups, relationships, tags, albums, or smart views.
- Silent AI approval, silent metadata conflict resolution, or silent destructive filesystem mutation.
- Mobile apps in the Lamha release line.
- Continuous upstream Immich merges after the desktop architecture cutover.

## Release ladder

| Release | Included phases | User-visible outcome | Ship gate |
|---|---:|---|---|
| R0 Developer Foundation | 0–4 | Reproducible Git baseline, branded desktop shell, selected roots, safe scan, sidecars, SQLite rebuild, transaction engine. | Internal only; all Phase 4 data-safety gates pass. |
| R1 Local Library | 5 | Offline gallery, timeline, viewer, folders, albums, favorites, memories, basic search, metadata inspector, Review shell. | A real copied library can be browsed with no server and no authoritative data loss. |
| R2 Organization | 6–9 | Manage Later, events, people/groups, relationships/tags/attribution, global + scoped mind maps. | Reversible organization and graph operations pass. |
| R3 Intelligence & Editing | 10–11 | Local AI, OCR, semantic search, duplicates, review-first suggestions, non-destructive edits and privacy tools. | No listener; AI authority and edit recovery gates pass. |
| R4 Resilient Desktop | 12–14 | External drives, overlays, crash recovery, backup/Trash/rebuild, performance and accessibility. | 100k reference-library and failure-injection gates pass. |
| R5 Public-Quality 1.0 | 15–16 | Clean cross-platform packages, legal inventory, parity sign-off, obsolete stack eradicated. | Signed release manifest and final absence/traceability proof. |

## Scope-change rule

New feature ideas go to a post-1.0 backlog unless they are required to satisfy an existing locked requirement, safety gate, legal obligation, or cross-platform parity defect.
