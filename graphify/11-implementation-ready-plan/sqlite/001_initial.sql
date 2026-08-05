PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = FULL;

CREATE TABLE IF NOT EXISTS schema_migrations (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  checksum TEXT NOT NULL,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS library_root (
  root_id TEXT PRIMARY KEY,
  canonical_path TEXT NOT NULL,
  normalized_path TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  drive_identity TEXT,
  access_mode TEXT NOT NULL CHECK (access_mode IN ('managed','linked-read-write','linked-read-only','detached')),
  availability TEXT NOT NULL CHECK (availability IN ('online','offline','permission-denied','missing','conflict')),
  last_seen_at TEXT,
  source_revision INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS asset_index (
  asset_id TEXT PRIMARY KEY,
  root_id TEXT NOT NULL REFERENCES library_root(root_id) ON DELETE RESTRICT,
  relative_path TEXT NOT NULL,
  normalized_relative_path TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  media_kind TEXT NOT NULL CHECK (media_kind IN ('photo','video','audio','other')),
  mime_type TEXT,
  size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
  content_hash TEXT,
  quick_fingerprint TEXT,
  capture_time TEXT,
  capture_time_source TEXT,
  timezone_offset_minutes INTEGER,
  event_id TEXT,
  record_revision INTEGER NOT NULL,
  record_fingerprint TEXT NOT NULL,
  availability TEXT NOT NULL DEFAULT 'online',
  indexed_at TEXT NOT NULL,
  UNIQUE(root_id, normalized_relative_path)
);
CREATE INDEX IF NOT EXISTS idx_asset_capture_time ON asset_index(capture_time DESC, asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_event ON asset_index(event_id, capture_time DESC);
CREATE INDEX IF NOT EXISTS idx_asset_hash ON asset_index(content_hash) WHERE content_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_asset_availability ON asset_index(availability) WHERE availability <> 'online';

CREATE TABLE IF NOT EXISTS asset_companion (
  asset_id TEXT NOT NULL REFERENCES asset_index(asset_id) ON DELETE CASCADE,
  companion_asset_id TEXT NOT NULL REFERENCES asset_index(asset_id) ON DELETE CASCADE,
  relation_type TEXT NOT NULL,
  source_revision INTEGER NOT NULL,
  PRIMARY KEY(asset_id, companion_asset_id, relation_type),
  CHECK(asset_id <> companion_asset_id)
);

CREATE TABLE IF NOT EXISTS event_index (
  event_id TEXT PRIMARY KEY,
  root_id TEXT REFERENCES library_root(root_id) ON DELETE SET NULL,
  relative_folder_path TEXT,
  normalized_folder_path TEXT,
  name TEXT NOT NULL,
  start_time TEXT,
  end_time TEXT,
  date_confidence TEXT NOT NULL,
  folder_state TEXT NOT NULL,
  record_revision INTEGER NOT NULL,
  record_fingerprint TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_start ON event_index(start_time DESC, event_id);

CREATE TABLE IF NOT EXISTS person_index (
  person_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  visibility TEXT NOT NULL,
  record_revision INTEGER NOT NULL,
  record_fingerprint TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_person_name ON person_index(normalized_name);

CREATE TABLE IF NOT EXISTS face_index (
  face_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES asset_index(asset_id) ON DELETE CASCADE,
  person_id TEXT REFERENCES person_index(person_id) ON DELETE SET NULL,
  region_json TEXT NOT NULL,
  embedding_ref TEXT,
  model_id TEXT,
  model_version TEXT,
  source_fingerprint TEXT NOT NULL,
  hidden INTEGER NOT NULL DEFAULT 0 CHECK(hidden IN (0,1))
);
CREATE INDEX IF NOT EXISTS idx_face_asset ON face_index(asset_id);
CREATE INDEX IF NOT EXISTS idx_face_person ON face_index(person_id) WHERE person_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS group_index (
  group_id TEXT PRIMARY KEY,
  parent_group_id TEXT REFERENCES group_index(group_id) ON DELETE RESTRICT,
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  record_revision INTEGER NOT NULL,
  record_fingerprint TEXT NOT NULL,
  CHECK(group_id <> parent_group_id)
);
CREATE INDEX IF NOT EXISTS idx_group_parent ON group_index(parent_group_id);

CREATE TABLE IF NOT EXISTS group_membership_index (
  group_id TEXT NOT NULL REFERENCES group_index(group_id) ON DELETE CASCADE,
  person_id TEXT NOT NULL REFERENCES person_index(person_id) ON DELETE CASCADE,
  start_time TEXT,
  end_time TEXT,
  source_revision INTEGER NOT NULL,
  PRIMARY KEY(group_id, person_id, start_time),
  CHECK(end_time IS NULL OR start_time IS NULL OR end_time >= start_time)
);

CREATE TABLE IF NOT EXISTS relationship_index (
  edge_id TEXT PRIMARY KEY,
  from_person_id TEXT NOT NULL REFERENCES person_index(person_id) ON DELETE CASCADE,
  to_person_id TEXT NOT NULL REFERENCES person_index(person_id) ON DELETE CASCADE,
  relationship_type TEXT NOT NULL,
  custom_type INTEGER NOT NULL CHECK(custom_type IN (0,1)),
  certainty TEXT NOT NULL CHECK(certainty IN ('sure','not-sure')),
  start_time TEXT,
  end_time TEXT,
  projection_json TEXT NOT NULL DEFAULT '[]',
  record_revision INTEGER NOT NULL,
  record_fingerprint TEXT NOT NULL,
  CHECK(from_person_id <> to_person_id),
  CHECK(end_time IS NULL OR start_time IS NULL OR end_time >= start_time)
);
CREATE INDEX IF NOT EXISTS idx_relationship_from ON relationship_index(from_person_id);
CREATE INDEX IF NOT EXISTS idx_relationship_to ON relationship_index(to_person_id);
CREATE INDEX IF NOT EXISTS idx_relationship_active ON relationship_index(start_time, end_time);

CREATE TABLE IF NOT EXISTS tag_index (
  tag_id TEXT PRIMARY KEY,
  namespace TEXT NOT NULL,
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  record_revision INTEGER NOT NULL,
  record_fingerprint TEXT NOT NULL,
  UNIQUE(namespace, normalized_name)
);

CREATE TABLE IF NOT EXISTS asset_tag_index (
  asset_id TEXT NOT NULL REFERENCES asset_index(asset_id) ON DELETE CASCADE,
  tag_id TEXT NOT NULL REFERENCES tag_index(tag_id) ON DELETE CASCADE,
  assignment_state TEXT NOT NULL CHECK(assignment_state IN ('approved','candidate','rejected','suppressed')),
  provenance_json TEXT NOT NULL,
  source_revision INTEGER NOT NULL,
  PRIMARY KEY(asset_id, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_asset_tag_tag ON asset_tag_index(tag_id, assignment_state);

CREATE TABLE IF NOT EXISTS album_index (
  album_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  cover_asset_id TEXT REFERENCES asset_index(asset_id) ON DELETE SET NULL,
  record_revision INTEGER NOT NULL,
  record_fingerprint TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS album_asset_index (
  album_id TEXT NOT NULL REFERENCES album_index(album_id) ON DELETE CASCADE,
  asset_id TEXT NOT NULL REFERENCES asset_index(asset_id) ON DELETE CASCADE,
  position INTEGER,
  PRIMARY KEY(album_id, asset_id)
);

CREATE TABLE IF NOT EXISTS review_queue (
  review_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  state TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 0,
  candidate_fingerprint TEXT NOT NULL,
  source_fingerprint TEXT,
  model_id TEXT,
  model_version TEXT,
  config_fingerprint TEXT,
  subject_ids_json TEXT NOT NULL,
  record_path TEXT NOT NULL,
  record_revision INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_review_pending ON review_queue(priority DESC, created_at) WHERE state IN ('pending','conflict','reconsidered');
CREATE INDEX IF NOT EXISTS idx_review_fingerprint ON review_queue(candidate_fingerprint, state);

CREATE TABLE IF NOT EXISTS job_state (
  task_id TEXT PRIMARY KEY,
  asset_id TEXT REFERENCES asset_index(asset_id) ON DELETE CASCADE,
  task_kind TEXT NOT NULL,
  state TEXT NOT NULL,
  model_id TEXT,
  model_version TEXT,
  source_fingerprint TEXT,
  config_fingerprint TEXT,
  progress_completed INTEGER NOT NULL DEFAULT 0,
  progress_total INTEGER,
  attempt INTEGER NOT NULL DEFAULT 0,
  last_error_json TEXT,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_job_runnable ON job_state(state, task_kind, updated_at) WHERE state IN ('queued','running','paused','failed','rerun-required');

CREATE TABLE IF NOT EXISTS ocr_index (
  asset_id TEXT PRIMARY KEY REFERENCES asset_index(asset_id) ON DELETE CASCADE,
  text_content TEXT NOT NULL,
  language_json TEXT NOT NULL DEFAULT '[]',
  regions_json TEXT NOT NULL DEFAULT '[]',
  model_id TEXT NOT NULL,
  model_version TEXT NOT NULL,
  source_fingerprint TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS search_document (
  asset_id TEXT PRIMARY KEY REFERENCES asset_index(asset_id) ON DELETE CASCADE,
  title TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '',
  people TEXT NOT NULL DEFAULT '',
  event_name TEXT NOT NULL DEFAULT '',
  location_text TEXT NOT NULL DEFAULT '',
  ocr_text TEXT NOT NULL DEFAULT '',
  source_fingerprint TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
  asset_id UNINDEXED, title, description, tags, people, event_name, location_text, ocr_text,
  tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS embedding_index (
  asset_id TEXT NOT NULL REFERENCES asset_index(asset_id) ON DELETE CASCADE,
  model_id TEXT NOT NULL,
  model_version TEXT NOT NULL,
  vector_ref TEXT NOT NULL,
  dimensions INTEGER NOT NULL CHECK(dimensions > 0),
  source_fingerprint TEXT NOT NULL,
  PRIMARY KEY(asset_id, model_id, model_version)
);

CREATE TABLE IF NOT EXISTS thumbnail_index (
  asset_id TEXT NOT NULL REFERENCES asset_index(asset_id) ON DELETE CASCADE,
  variant TEXT NOT NULL,
  cache_path TEXT NOT NULL,
  width INTEGER NOT NULL,
  height INTEGER NOT NULL,
  source_fingerprint TEXT NOT NULL,
  PRIMARY KEY(asset_id, variant)
);

CREATE TABLE IF NOT EXISTS operation_index (
  operation_id TEXT PRIMARY KEY,
  operation_kind TEXT NOT NULL,
  state TEXT NOT NULL,
  journal_path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_operation_recovery ON operation_index(state, updated_at) WHERE state IN ('prepared','staging','ready-to-commit','committing','recovery-required','conflict');

CREATE TABLE IF NOT EXISTS map_graph_index (
  graph_id TEXT PRIMARY KEY,
  scope_kind TEXT NOT NULL,
  scope_id TEXT,
  draft_state TEXT NOT NULL,
  record_path TEXT NOT NULL,
  record_revision INTEGER NOT NULL,
  record_fingerprint TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS map_node_index (
  graph_id TEXT NOT NULL REFERENCES map_graph_index(graph_id) ON DELETE CASCADE,
  node_id TEXT NOT NULL,
  node_kind TEXT NOT NULL,
  domain_id TEXT,
  node_state TEXT NOT NULL,
  position_json TEXT NOT NULL,
  PRIMARY KEY(graph_id, node_id)
);
CREATE TABLE IF NOT EXISTS map_edge_index (
  graph_id TEXT NOT NULL REFERENCES map_graph_index(graph_id) ON DELETE CASCADE,
  edge_id TEXT NOT NULL,
  from_node_id TEXT NOT NULL,
  to_node_id TEXT NOT NULL,
  edge_type TEXT NOT NULL,
  PRIMARY KEY(graph_id, edge_id),
  FOREIGN KEY(graph_id, from_node_id) REFERENCES map_node_index(graph_id, node_id) ON DELETE CASCADE,
  FOREIGN KEY(graph_id, to_node_id) REFERENCES map_node_index(graph_id, node_id) ON DELETE CASCADE,
  CHECK(from_node_id <> to_node_id)
);
