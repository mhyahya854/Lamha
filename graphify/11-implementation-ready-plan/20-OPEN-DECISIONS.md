# Open decisions and implementation spikes

## Blocking product decisions

None. Product behaviour is sufficiently locked for Phase 0 implementation to begin.

## Time-boxed implementation spikes (not permission to guess)

| Spike | Phase | Decision output | Required comparison |
|---|---:|---|---|
| Worker packager | 10 | PyInstaller/Nuitka/alternative selection | Startup, size, signing/AV, clean machine, crash/cancel, model loading, licence. |
| Rust media metadata stack | 4/11 | Native crates vs ExifTool boundary | Format coverage, write safety, XMP support, licensing, failure isolation. |
| RAW/HEIF/video preview stack | 4/5 | Decoder/tool matrix | Cross-platform coverage, quality, performance, binary/legal cost. |
| SQLite access/migrations | 4 | Crate and migration tooling | Transactions, FTS/vector strategy, backup/rebuild, compile/platform support. |
| Linux package baseline | 15 | Supported distributions/package formats | WebView/runtime requirements, sidecars, codecs, clean install. |
| macOS architecture | 10/15 | Universal vs split packages | Worker/model architecture, size, signing/notarization, performance. |

A spike must end in an ADR amendment, evidence, and updated component manifest. It cannot quietly change user-visible behaviour or safety invariants.
