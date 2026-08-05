# Settings

System/user preferences that survive as local desktop, library, AI, privacy, and appearance settings.

## Current verified evidence

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/web/src/routes/(user)/user-settings/+page.ts:L1-L1` | `user-settings/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_user_user_settings_page_ts` | REWRITE |
| `Codebase/web/src/routes/(user)/user-settings/+page.svelte:L1-L1` | `user-settings/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_user_settings_page_svelte` | REWRITE |
| `Codebase/web/src/routes/(user)/user-settings/DeviceList.svelte:L17-L17` | `currentSession` | EXTRACTED | `c_users_mhyah_downloads_code_lamha_codebase_web_src_routes_user_user_settings_devicelist_currentsession` | REWRITE |
| `Codebase/web/src/routes/(user)/user-settings/AppSettings.svelte:L47-L47` | `if()` | EXTRACTED | `c_users_mhyah_downloads_code_lamha_codebase_web_src_routes_user_user_settings_appsettings_if` | REWRITE |
| `Codebase/web/src/routes/(user)/user-settings/OauthSettings.svelte:L21-L21` | `catch()` | EXTRACTED | `c_users_mhyah_downloads_code_lamha_codebase_web_src_routes_user_user_settings_oauthsettings_catch` | REWRITE |
| `Codebase/web/src/routes/(user)/user-settings/UserApiKeyList.svelte:L53-L53` | `#each()` | EXTRACTED | `c_users_mhyah_downloads_code_lamha_codebase_web_src_routes_user_user_settings_userapikeylist_each` | REWRITE |
| `Codebase/web/src/routes/(user)/user-settings/FeatureSettings.svelte:L1-L1` | `./FeatureSettings.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_user_settings_featuresettings_svelte` | REWRITE |
| `Codebase/web/src/routes/(user)/user-settings/PartnerSettings.svelte:L1-L1` | `./PartnerSettings.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_user_settings_partnersettings_svelte` | REWRITE |
| `Codebase/web/src/routes/(user)/user-settings/PinCodeSettings.svelte:L1-L1` | `./PinCodeSettings.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_user_settings_pincodesettings_svelte` | REWRITE |
| `Codebase/web/src/routes/(user)/user-settings/SettingCombobox.svelte:L1-L1` | `SettingCombobox.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_user_settings_settingcombobox_svelte` | REWRITE |

## Current dependency boundary

- Complete pattern-matched production file set: **26**.
- Complete pattern-matched existing test file set: **5**.
- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.

## Target decision

- Classification: **REWRITE**.
- Assigned implementation phase: **Phase 4 — Local data foundation**.
- Target modules: `src-tauri/src/settings/`, `src-tauri/src/commands/settings.rs`, `web/src/routes/(user)/user-settings/`.
- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.
