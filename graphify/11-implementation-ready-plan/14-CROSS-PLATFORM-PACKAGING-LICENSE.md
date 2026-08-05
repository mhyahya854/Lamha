# Cross-platform packaging, dependencies, and legal plan

## Package targets

- Windows x64 first; ARM64 only after dependency support is proven. Produce a signed installer and an unpacked/internal diagnostic build.
- macOS universal or separate arm64/x64 artifacts based on sidecar/model feasibility; code-sign and notarize release artifacts.
- Linux x64 package set selected after clean-machine proof; at minimum one portable format and one native package for the supported distribution baseline.

## Bundled components

Tauri/Rust app, static web assets, AI worker, model files, FFmpeg/ffprobe where needed, ExifTool or a validated replacement, image/video/RAW decoders, fonts/icons, and licence/notice files. Every component has version, source, checksum, licence, redistribution decision, platform/architecture, and update owner in the component manifest.

## Dependency policy

- Pin direct dependencies and commit lockfiles.
- Prefer mature, maintained libraries with clear licences and cross-platform support.
- New dependencies require purpose, alternatives considered, binary-size/security/legal impact, and owner.
- CI performs vulnerability, licence, secret, and forbidden-network/listener scans.
- A dependency cannot remain merely because Immich used it; it must serve a retained Lamha capability.

## AGPL and attribution

Preserve the original licence and required copyright notices. Record modifications, source availability obligations, third-party notices, model licences, codec/binary licences, and font/icon attribution. A legal checklist blocks public distribution until every shipped component has a redistributable status.

## Update policy

Lamha 1.0 does not silently check for updates. Manual update installation must preserve roots, transparent records, journals, and database migrations. Any future opt-in update checker requires a separate privacy/network ADR.
