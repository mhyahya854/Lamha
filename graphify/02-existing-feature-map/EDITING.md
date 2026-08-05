# Editing

Non-destructive edits, derivatives, exports, snapshots, privacy transforms, and restore.

## Current verified evidence

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/web/src/lib/components/asset-viewer/editor/EditorPanel.svelte:L1-L1` | `EditorPanel.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_editor_editorpanel_svelte` | REWRITE |
| `Codebase/web/src/lib/components/asset-viewer/face-editor/FaceEditor.svelte:L1-L1` | `lib/components/asset-viewer/face-editor/FaceEditor.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_face_editor_faceeditor_svelte` | REWRITE |
| `Codebase/web/src/lib/components/asset-viewer/editor/transform-tool/CropArea.svelte:L1-L1` | `CropArea.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_editor_transform_tool_croparea_svelte` | REWRITE |
| `Codebase/web/src/lib/components/asset-viewer/editor/transform-tool/CropPreset.svelte:L1-L1` | `CropPreset.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_editor_transform_tool_croppreset_svelte` | REWRITE |
| `Codebase/web/src/lib/components/asset-viewer/editor/transform-tool/TransformTool.svelte:L1-L1` | `TransformTool.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_editor_transform_tool_transformtool_svelte` | REWRITE |
| `Codebase/server/src/dtos/editing.dto.ts:L1-L1` | `editing.dto.ts` | EXTRACTED | `ext_codebase_server_src_dtos_editing_dto_ts` | REWRITE |
| `Codebase/server/src/repositories/asset-edit.repository.ts:L1-L1` | `asset-edit.repository.ts` | EXTRACTED | `ext_codebase_server_src_repositories_asset_edit_repository_ts` | REWRITE |

## Current dependency boundary

- Complete pattern-matched production file set: **7**.
- Complete pattern-matched existing test file set: **4**.
- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.

## Target decision

- Classification: **REWRITE**.
- Assigned implementation phase: **Phase 11 — Metadata mutation, editing, and privacy**.
- Target modules: `src-tauri/src/assets/edits.rs`, `src-tauri/src/commands/editing.rs`, `web/src/lib/components/editing/`.
- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.
