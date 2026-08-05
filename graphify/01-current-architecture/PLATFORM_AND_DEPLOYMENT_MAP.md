# Platform and deployment map

| Area | Current paths | Target disposition |
|---|---|---|
| Docker/Compose | docker/; docker-compose*.yml; e2e/docker-compose.yml | Remove after desktop replacement and parity proof |
| OpenTofu/Terragrunt | deployment/ | Remove cloud/server deployment |
| CI | .github/workflows/ | Rewrite for desktop builds/tests/signing |
| Mobile | mobile/ | Remove after retained local behaviors are represented |
| Docs | docs/; README.md; readme_i18n/ | Retain legal/build-required docs; rewrite/remove obsolete workflows |
| Packaging | fastlane/; mobile/android; mobile/ios | Replace with Windows/macOS/Linux Tauri packaging |

All paths remain untouched during planning.
