# People and faces

Face detection/recognition, identity curation, people views, grouping, merge/split, and history.

## Current verified evidence

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/web/src/routes/(user)/people/+page.ts:L1-L1` | `people/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_user_people_page_ts` | REWRITE |
| `Codebase/web/src/routes/(user)/people/+page.svelte:L1-L1` | `people/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_people_page_svelte` | REWRITE |
| `Codebase/web/src/routes/(user)/people/manage/+page.ts:L1-L1` | `manage/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_user_people_manage_page_ts` | REWRITE |
| `Codebase/web/src/routes/(user)/people/PeopleCard.svelte:L1-L1` | `PeopleCard.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_people_peoplecard_svelte` | REWRITE |
| `Codebase/web/src/routes/(user)/people/manage/+page.svelte:L63-L63` | `if()` | EXTRACTED | `c_users_mhyah_downloads_code_lamha_codebase_web_src_routes_user_people_manage_page_if` | REWRITE |
| `Codebase/web/src/lib/components/faces-page/PeopleSearch.svelte:L1-L1` | `lib/components/faces-page/PeopleSearch.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_faces_page_peoplesearch_svelte` | REWRITE |
| `Codebase/web/src/lib/components/faces-page/PersonSidePanel.svelte:L1-L1` | `PersonSidePanel.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_faces_page_personsidepanel_svelte` | REWRITE |
| `Codebase/web/src/routes/(user)/people/PeopleInfiniteScroll.svelte:L31-L31` | `index()` | EXTRACTED | `c_users_mhyah_downloads_code_lamha_codebase_web_src_routes_user_people_peopleinfinitescroll_index` | REWRITE |
| `Codebase/web/src/lib/components/faces-page/AssignFaceSidePanel.svelte:L52-L52` | `searchFaces` | EXTRACTED | `c_users_mhyah_downloads_code_lamha_codebase_web_src_lib_components_faces_page_assignfacesidepanel_searchfaces` | REWRITE |
| `Codebase/web/src/routes/(user)/people/manage/ManagePeopleVisibility.test-wrapper.svelte:L1-L1` | `ManagePeopleVisibility.test-wrapper.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_people_manage_managepeoplevisibility_test_wrapper_svelte` | REWRITE |

## Current dependency boundary

- Complete pattern-matched production file set: **22**.
- Complete pattern-matched existing test file set: **7**.
- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.

## Target decision

- Classification: **REWRITE**.
- Assigned implementation phase: **Phase 7 — Faces, people, and groups**.
- Target modules: `src-tauri/src/people/`, `src-tauri/src/groups/`, `src-tauri/src/relationships/`, `ai-worker/faces/`.
- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.
