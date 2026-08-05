# Sidecar and schema map

| Domain | Selected Phase 1 representation | Validation/migration rule |
|---|---|---|
| All authoritative JSON | `schemaVersion` string | initial `1.0.0`; formal JSON Schema; tolerant read/preserve unknown fields; reject unsupported future write |
| Asset | `media.ext.asset.json` | stable ID, source/original filename concepts, hashes, metadata, people/attribution, AI task states, derivative/companion links |
| Event | `event.json` + `event.xmp` mirror | stable ID, approved name/start/end, attendees, folder/materialization state |
| Person/group/relationship | domain records in root-scoped `.app-data` | stable IDs, aliases, effective dates, history, multi-edge type/certainty/notes, projection rules |
| Map/tag/album | domain-scoped records | saved drafts/approved state remain transparent authority |
| Operation/review/overlay | root-scoped or OS-app-data records by authority | UUID, provenance, state transitions, decisions, conflict/recovery data |
| AI task state | `status`, `modelId`, `modelVersion`, `sourceFingerprint`, `configFingerprint`, `processedAt`, `staleReason` | Seven required concepts; legacy `aiChecked` prohibited |

Every writer validates before durable replacement, fsyncs through the transaction layer, keeps a recoverable prior copy where mutation risk exists, and preserves exact corrupt/future-version bytes for review. JSON key selections live here rather than in the pre-mapping Master Plan.
